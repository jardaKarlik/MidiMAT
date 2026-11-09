using System.Diagnostics;

namespace MidiMAT.Services;

public enum SidecarState
{
    Stopped,
    Starting,
    Running,
    Restarting,
    Failed,
}

public sealed class SidecarLogEventArgs : EventArgs
{
    public SidecarLogEventArgs(string line, bool isError)
    {
        Line = line;
        IsError = isError;
    }

    /// <summary>One line of sidecar output (stdout or stderr), without trailing newline.</summary>
    public string Line { get; }

    /// <summary>True when the line came from stderr.</summary>
    public bool IsError { get; }
}

/// <summary>
/// Spawns and supervises the Python sidecar executable (PyInstaller bundle produced by
/// the build pipeline; see DESIGN_APP.md §7). Captures stdout/stderr line-by-line and
/// restarts with exponential backoff on unexpected exit.
///
/// NOTHING is spawned automatically in this scaffold: <see cref="AutoStartEnabled"/> is
/// false so a build/test/run never launches a child process. Call <see cref="Start"/>
/// explicitly once the sidecar artifact exists.
/// </summary>
public sealed class SidecarManager : IDisposable
{
    /// <summary>
    /// Scaffold safety switch. When false, <see cref="StartIfAutoStartEnabled"/> is a no-op
    /// so the app never spawns a child process during build/test.
    ///
    /// It is TRUE now: the sidecar can be launched either from the bundled PyInstaller EXE
    /// (release) or from the repo's venv via python (dev) — see <see cref="ResolveSidecarLaunch"/>.
    /// Auto-start is still additionally gated on <c>config.server.auto_start</c>.
    /// </summary>
    public const bool AutoStartEnabled = true;

    // Restart-with-backoff tuning (DESIGN_APP.md §10).
    private const int MaxRestartAttempts = 5;
    private static readonly TimeSpan BaseBackoff = TimeSpan.FromSeconds(1);
    private static readonly TimeSpan MaxBackoff = TimeSpan.FromSeconds(30);

    // server.py does not implement --managed yet (DESIGN_APP.md §11 "Additions").
    // Passing an unknown flag would crash argparse, so keep this off until it lands.
    // (static readonly, not const, so the guard below stays valid when flipped to true.)
    private static readonly bool PassManagedFlag = false;

    private readonly object _gate = new();
    private readonly MidiMatConfig _config;

    private Process? _process;
    private int _restartAttempts;
    private bool _stopping;
    private CancellationTokenSource? _restartCts;

    public SidecarManager(MidiMatConfig config)
    {
        _config = config;
    }

    /// <summary>Raised for every stdout/stderr line from the sidecar.</summary>
    public event EventHandler<SidecarLogEventArgs>? LogLine;

    /// <summary>Raised whenever the lifecycle state changes.</summary>
    public event EventHandler<SidecarState>? StateChanged;

    public SidecarState State { get; private set; } = SidecarState.Stopped;

    /// <summary>
    /// Human-readable description of the resolved launch target (the bundled EXE path, or
    /// "python server.py"), or "&lt;not found&gt;" when nothing could be located.
    /// </summary>
    public string ExecutablePath => ResolveSidecarLaunch(_config)?.Description ?? "<not found>";

    /// <summary>
    /// Start only if the compile-time <see cref="AutoStartEnabled"/> flag and the user's
    /// config both allow it. Safe no-op otherwise.
    /// </summary>
    public bool StartIfAutoStartEnabled()
    {
        if (!AutoStartEnabled || !_config.Server.AutoStart)
        {
            return false;
        }

        Start();
        return true;
    }

    /// <summary>Launch the sidecar. No-op if already running.</summary>
    public void Start()
    {
        lock (_gate)
        {
            if (_process is { HasExited: false })
            {
                return;
            }

            var spec = ResolveSidecarLaunch(_config);
            if (spec is null)
            {
                SetState(SidecarState.Failed);
                RaiseLog("[SidecarManager] sidecar not found — no midimat-server.exe and no "
                         + "sidecar/server.py reachable from " + AppContext.BaseDirectory, isError: true);
                return;
            }

            _stopping = false;
            SetState(_restartAttempts > 0 ? SidecarState.Restarting : SidecarState.Starting);
            LaunchProcess(spec);
        }
    }

    /// <summary>Stop the sidecar (graceful kill of the process tree).</summary>
    public void Stop()
    {
        Process? proc;
        lock (_gate)
        {
            _stopping = true;
            _restartCts?.Cancel();
            _restartAttempts = 0;
            proc = _process;
            _process = null;
        }

        KillProcess(proc);
        SetState(SidecarState.Stopped);
    }

    /// <summary>Stop then start.</summary>
    public void Restart()
    {
        Stop();
        lock (_gate)
        {
            _restartAttempts = 0;
        }
        Start();
    }

    private void LaunchProcess(SidecarLaunchSpec spec)
    {
        var psi = new ProcessStartInfo
        {
            FileName = spec.FileName,
            WorkingDirectory = spec.WorkingDirectory,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };

        foreach (var arg in spec.Arguments)
        {
            psi.ArgumentList.Add(arg);
        }

        var process = new Process { StartInfo = psi, EnableRaisingEvents = true };
        process.OutputDataReceived += (_, e) => { if (e.Data is not null) RaiseLog(e.Data, isError: false); };
        process.ErrorDataReceived += (_, e) => { if (e.Data is not null) RaiseLog(e.Data, isError: true); };
        process.Exited += (_, _) => OnProcessExited(process);

        _process = process;

        try
        {
            process.Start();
            process.BeginOutputReadLine();
            process.BeginErrorReadLine();
            RaiseLog($"[SidecarManager] started pid={process.Id}: {spec.Description}", isError: false);
            SetState(SidecarState.Running);
        }
        catch (Exception ex)
        {
            RaiseLog($"[SidecarManager] failed to start sidecar: {ex.Message}", isError: true);
            SetState(SidecarState.Failed);
            _process = null;
        }
    }

    private void OnProcessExited(Process process)
    {
        bool expected;
        lock (_gate)
        {
            expected = _stopping || _process != process;
            if (_process == process)
            {
                _process = null;
            }
        }

        if (expected)
        {
            SetState(SidecarState.Stopped);
            return;
        }

        RaiseLog($"[SidecarManager] sidecar exited (code {process.ExitCode}); scheduling restart", isError: true);
        ScheduleRestart();
    }

    private void ScheduleRestart()
    {
        int attempt;
        lock (_gate)
        {
            if (_stopping)
            {
                return;
            }

            if (_restartAttempts >= MaxRestartAttempts)
            {
                SetState(SidecarState.Failed);
                RaiseLog($"[SidecarManager] giving up after {MaxRestartAttempts} restart attempts", isError: true);
                return;
            }

            attempt = ++_restartAttempts;
            _restartCts = new CancellationTokenSource();
        }

        // Exponential backoff, capped: 1s, 2s, 4s, 8s, 16s (max 30s).
        var delayMs = Math.Min(
            BaseBackoff.TotalMilliseconds * Math.Pow(2, attempt - 1),
            MaxBackoff.TotalMilliseconds);

        SetState(SidecarState.Restarting);
        RaiseLog($"[SidecarManager] restart attempt {attempt}/{MaxRestartAttempts} in {delayMs / 1000.0:0.#}s", isError: false);

        var token = _restartCts!.Token;
        _ = Task.Run(async () =>
        {
            try
            {
                await Task.Delay((int)delayMs, token).ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
                return;
            }

            if (!token.IsCancellationRequested)
            {
                Start();
            }
        });
    }

    /// <summary>
    /// Build the sidecar command line from config. Mirrors the flags accepted by
    /// sidecar/server.py's argparse: --http-port, --ws-port, --midi, --nhl, --no-demo.
    /// </summary>
    internal static IReadOnlyList<string> BuildArguments(MidiMatConfig config)
    {
        var args = new List<string>
        {
            "--http-port", config.Server.HttpPort.ToString(),
            "--ws-port", config.Server.WsPort.ToString(),
        };

        if (PassManagedFlag)
        {
            args.Add("--managed");
        }

        // --midi reads midi_ports from the config file passed via --config.
        args.Add("--midi");

        if (config.Server.NhlMode)
        {
            args.Add("--nhl");
        }

        if (!config.Server.DemoMode)
        {
            args.Add("--no-demo");
        }

        return args;
    }

    /// <summary>
    /// Resolve how to launch the sidecar:
    ///   1. the bundled PyInstaller EXE in %LOCALAPPDATA%\MidiMAT\sidecar (release), or
    ///   2. a repo-local build\midimat-server.exe (dev, post-PyInstaller), or
    ///   3. the repo's venv python running sidecar/server.py (dev, source).
    /// Returns <c>null</c> when none of these exist.
    /// </summary>
    internal static SidecarLaunchSpec? ResolveSidecarLaunch(MidiMatConfig config)
    {
        var bundled = Path.Combine(ConfigStore.AppDataDirectory, "sidecar", "midimat-server.exe");
        if (File.Exists(bundled))
        {
            return new SidecarLaunchSpec(
                bundled, BuildArguments(config),
                Path.GetDirectoryName(bundled)!, bundled);
        }

        var repoRoot = FindRepoRoot();
        if (repoRoot is not null)
        {
            var built = Path.Combine(repoRoot, "build", "midimat-server.exe");
            if (File.Exists(built))
            {
                return new SidecarLaunchSpec(built, BuildArguments(config), repoRoot, built);
            }

            var serverPy = Path.Combine(repoRoot, "sidecar", "server.py");
            if (File.Exists(serverPy))
            {
                var python = ResolvePython(repoRoot);
                if (python is not null)
                {
                    var args = new List<string> { serverPy };
                    args.AddRange(BuildArguments(config));
                    return new SidecarLaunchSpec(
                        python, args, repoRoot, $"{python} {serverPy}");
                }
            }
        }

        return null;
    }

    /// <summary>Prefer the repo venv interpreter; fall back to "python" on PATH.</summary>
    private static string? ResolvePython(string repoRoot)
    {
        var venv = Path.Combine(repoRoot, ".venv", "Scripts", "python.exe");
        return File.Exists(venv) ? venv : "python";
    }

    /// <summary>
    /// Walk up from the running EXE looking for the repo root (identified by
    /// <c>sidecar\server.py</c>). Returns null when the app is not running from a checkout.
    /// </summary>
    private static string? FindRepoRoot()
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        for (var i = 0; i < 12 && dir is not null; i++, dir = dir.Parent)
        {
            if (File.Exists(Path.Combine(dir.FullName, "sidecar", "server.py")))
            {
                return dir.FullName;
            }
        }

        return null;
    }

    private static void KillProcess(Process? process)
    {
        if (process is null)
        {
            return;
        }

        try
        {
            if (!process.HasExited)
            {
                process.Kill(entireProcessTree: true);
                process.WaitForExit(2000);
            }
        }
        catch (InvalidOperationException)
        {
            // Already exited between the check and the kill.
        }
        catch (System.ComponentModel.Win32Exception)
        {
            // Access denied or already gone — nothing more we can safely do.
        }
        finally
        {
            process.Dispose();
        }
    }

    private void RaiseLog(string line, bool isError)
        => LogLine?.Invoke(this, new SidecarLogEventArgs(line, isError));

    private void SetState(SidecarState state)
    {
        if (State == state)
        {
            return;
        }

        State = state;
        StateChanged?.Invoke(this, state);
    }

    public void Dispose()
    {
        Stop();
        _restartCts?.Dispose();
    }
}

/// <summary>A concrete way to start the sidecar (bundled EXE, or python + server.py).</summary>
public sealed record SidecarLaunchSpec(
    string FileName,
    IReadOnlyList<string> Arguments,
    string WorkingDirectory,
    string Description);
