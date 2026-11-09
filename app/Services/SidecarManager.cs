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
    /// so the app never spawns a child process during build/test. Flip to true once the
    /// PyInstaller sidecar is bundled (see README "Stubbed").
    /// </summary>
    public const bool AutoStartEnabled = false;

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

    /// <summary>Absolute path to the sidecar executable (resolved, may not exist yet).</summary>
    public string ExecutablePath => ResolveSidecarPath(_config);

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

            var exePath = ExecutablePath;
            if (!File.Exists(exePath))
            {
                SetState(SidecarState.Failed);
                RaiseLog($"[SidecarManager] sidecar not found: {exePath}", isError: true);
                return;
            }

            _stopping = false;
            SetState(_restartAttempts > 0 ? SidecarState.Restarting : SidecarState.Starting);
            LaunchProcess(exePath);
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

    private void LaunchProcess(string exePath)
    {
        var psi = new ProcessStartInfo
        {
            FileName = exePath,
            WorkingDirectory = Path.GetDirectoryName(exePath) ?? AppContext.BaseDirectory,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };

        foreach (var arg in BuildArguments(_config))
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
            RaiseLog($"[SidecarManager] started pid={process.Id}: {exePath}", isError: false);
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
    /// Resolve the sidecar EXE: prefer the path inside %LOCALAPPDATA%\MidiMAT\sidecar,
    /// then fall back to a repo checkout next to the running EXE (dev convenience).
    /// </summary>
    internal static string ResolveSidecarPath(MidiMatConfig config)
    {
        var appDataExe = Path.Combine(
            ConfigStore.AppDataDirectory, "sidecar", "midimat-server.exe");
        if (File.Exists(appDataExe))
        {
            return appDataExe;
        }

        // Dev fallback: <repo>\app\bin\<cfg>\<tfm>\win-x64\ -> <repo>\build\midimat-server.exe
        var devExe = Path.GetFullPath(Path.Combine(
            AppContext.BaseDirectory, "..", "..", "..", "..", "..", "build", "midimat-server.exe"));
        if (File.Exists(devExe))
        {
            return devExe;
        }

        // Nothing found: return the canonical location so callers/logs are deterministic.
        return appDataExe;
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
