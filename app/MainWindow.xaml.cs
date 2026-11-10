using System.Text.Json;
using System.Windows.Input;
using Microsoft.UI.Windowing;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using MidiMAT.Services;

namespace MidiMAT;

/// <summary>
/// Native shell window: a single WebView2 that hosts the React management UI.
/// The web app owns ALL navigation and chrome (its own left sidebar). This class
/// boots WebView2, wires the IPC bridge, runs the dependency probes, and supervises
/// the Python sidecar (spawning it, streaming its log to the UI, restarting on crash).
/// </summary>
public sealed partial class MainWindow : Window
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    private IpcBridge? _ipc;
    private SidecarManager? _sidecar;
    private SetupService? _setup;
    private MidiMatConfig _config = new();

    private AppWindow? _appWindow;

    /// <summary>
    /// Stays false until the tray's Quit is chosen. While false, closing the window
    /// hides it to the tray instead of exiting, so the sidecar keeps serving the
    /// OBS Browser Source.
    /// </summary>
    private bool _reallyQuitting;

    /// <summary>Only explain "still running in the tray" once per session.</summary>
    private bool _explainedTray;

    public MainWindow()
    {
        InitializeComponent();
        Title = "MidiMAT";

        // Window.Closed cannot be cancelled; AppWindow.Closing can, which is how we
        // turn "close" into "hide to tray" without losing the sidecar.
        _appWindow = AppWindow;
        _appWindow.Closing += OnAppWindowClosing;

        // Do not await here (ctor cannot be async); the Loaded handler does the async init.
        WebView.Loaded += WebView2_Loaded;

        Closed += (_, _) =>
        {
            _sidecar?.Dispose();
            DisposeTray();
        };
    }

    private async void WebView2_Loaded(object sender, RoutedEventArgs e)
    {
        // EnsureCoreWebView2Async must complete before we can touch CoreWebView2.
        await WebView.EnsureCoreWebView2Async();

        var core = WebView.CoreWebView2;

        // Dev tools only in Debug builds (never ship a devtools-enabled release).
#if DEBUG
        core.Settings.AreDevToolsEnabled = true;
        core.Settings.AreDefaultContextMenusEnabled = true;
#else
        core.Settings.AreDevToolsEnabled = false;
        core.Settings.AreDefaultContextMenusEnabled = false;
#endif
        core.Settings.IsStatusBarEnabled = false;

        // Serve Resources/ui/ from a virtual HTTPS-style origin so relative paths,
        // fetch() and window.chrome.webview.postMessage all behave like a normal page.
        var uiRoot = Path.Combine(AppContext.BaseDirectory, "Resources", "ui");
        if (!Directory.Exists(uiRoot))
        {
            core.NavigateToString(
                "<html><body style='background:#111;color:#f55;font-family:monospace;padding:24px'>" +
                "<h3>UI assets not found</h3>" +
                $"<p>Expected: {uiRoot}</p>" +
                "<p>Build the React UI (ui/ &rarr; npm run build) so it lands in app/Resources/ui, " +
                "then rebuild this project.</p>" +
                "</body></html>");
            return;
        }

        core.SetVirtualHostNameToFolderMapping(
            "midimat.local",
            uiRoot,
            Microsoft.Web.WebView2.Core.CoreWebView2HostResourceAccessKind.Allow);

        // ---- services --------------------------------------------------------
        _config = ConfigStore.Load();

        // Install the bundled sidecar into %LOCALAPPDATA% on first run, before the
        // supervisor resolves a launch target (it prefers that location).
        var extract = SidecarExtractor.EnsureInstalled();
        LogToFile($"sidecar bundle: ok={extract.Ok} copied={extract.Copied} {extract.Detail}");

        _sidecar = new SidecarManager(_config);
        _sidecar.LogLine += OnSidecarLog;
        _sidecar.StateChanged += (_, _) => PostDepsStatus();

        _ipc = new IpcBridge(WebView);
        _ipc.MessageFromWeb += OnMessageFromWeb;

        _setup = new SetupService(_config, _sidecar);
        _setup.ProgressChanged += OnSetupProgress;

        // Tray as early as practical: it is the only way back once the window is hidden.
        InitTray();

        core.NavigationCompleted += (_, _) =>
        {
            // Push persisted config + the first dependency snapshot, then start the sidecar
            // if the user allowed it. (The page decides which screen is active.)
            try
            {
                _ipc?.PostToWeb(IpcMessageTypes.ConfigLoaded, _config);
                PostDepsStatus();
                var started = _sidecar.StartIfAutoStartEnabled();
                LogToFile($"navigation: config+deps posted; autoStart={started}; "
                          + $"sidecarState={_sidecar.State}; target={_sidecar.ExecutablePath}");
            }
            catch (Exception ex)
            {
                // A throw here would silently skip every later step (deps, sidecar start).
                LogToFile($"navigation FAILED: {ex}");
            }
        };

        core.Navigate("https://midimat.local/index.html");
    }

    /// <summary>Send the current dependency + server snapshot to the UI (<c>deps:status</c>).</summary>
    private void PostDepsStatus()
    {
        var checks = DependencyChecker.CheckAll().ToDictionary(d => d.Name, d => d);
        bool Found(string name) => checks.TryGetValue(name, out var d) && d.Found;
        string Detail(string name) => checks.TryGetValue(name, out var d) ? d.Detail : "";

        var launch = SidecarManager.ResolveSidecarLaunch(_config);

        _ipc?.PostToWeb(IpcMessageTypes.DepsStatus, new
        {
            loopMidi = Found(DependencyChecker.LoopMidi),
            traktor = Found(DependencyChecker.Traktor),
            obs = Found(DependencyChecker.Obs),
            // "python" = the sidecar runtime is reachable (bundled EXE, or the dev venv).
            python = launch is not null,
            server = _sidecar?.State == SidecarState.Running,
            // Real, machine-specific values so the UI never shows invented paths.
            detail = new
            {
                loopMidi = Detail(DependencyChecker.LoopMidi),
                traktor = Detail(DependencyChecker.Traktor),
                obs = Detail(DependencyChecker.Obs),
                runtime = launch?.Description ?? "not found",
                server = ConfigStore.ConfigFilePath,
                port = _config.Paths.LoopmidiPort,
            },
        });
    }

    /// <summary>
    /// Stream one sidecar output line to the UI (<c>server:log</c>).
    ///
    /// Python's <c>logging</c> writes to stderr, so "came from stderr" does NOT mean
    /// "is an error" — we must read the level out of the text. Lines look like
    /// <c>HH:MM:SS.mmm LEVEL     logger | message</c>; we strip that prefix so the UI
    /// owns the timestamp/level columns and does not repeat it.
    /// </summary>
    private void OnSidecarLog(object? sender, SidecarLogEventArgs e)
    {
        string level;
        string text = e.Line;

        var match = SidecarLineRegex.Match(e.Line);
        if (match.Success)
        {
            level = match.Groups["lvl"].Value switch
            {
                "DEBUG" => "debug",
                "WARNING" => "warn",
                "ERROR" or "CRITICAL" => "error",
                _ => "info",
            };
            text = match.Groups["rest"].Value;
        }
        else
        {
            level = e.IsError ? "error" : "info";
        }

        _ipc?.PostToWeb(IpcMessageTypes.ServerLog, new
        {
            line = text,
            level,
            ts = DateTimeOffset.Now.ToString("o"),
        });
    }

    private static readonly System.Text.RegularExpressions.Regex SidecarLineRegex = new(
        @"^(?:\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)\s+(?<lvl>DEBUG|INFO|WARNING|ERROR|CRITICAL)\s+(?<rest>.*)$",
        System.Text.RegularExpressions.RegexOptions.Compiled);

    private void OnMessageFromWeb(object? sender, IpcMessage message)
    {
        switch (message.Type)
        {
            case IpcMessageTypes.ServerRestart:
                _sidecar?.Restart();
                break;

            case IpcMessageTypes.ServerStop:
                _sidecar?.Stop();
                break;

            case IpcMessageTypes.ConfigSave:
                TrySaveConfig(message.PayloadJson);
                break;

            case IpcMessageTypes.SetupStart:
                // Fire-and-forget: the wizard advances on setup:progress, not on a reply.
                _ = RunSetupStepAsync(message.PayloadJson);
                break;

            case IpcMessageTypes.SetupComplete:
                HandleSetupComplete(message.PayloadJson);
                break;

            default:
                System.Diagnostics.Debug.WriteLine($"[ipc] unhandled {message.Type}: {message.PayloadJson}");
                break;
        }
    }

    private void TrySaveConfig(string payloadJson)
    {
        try
        {
            var incoming = JsonSerializer.Deserialize<ConfigSavePayload>(payloadJson, JsonOptions);
            if (incoming is null)
            {
                return;
            }

            // Merge only the fields the caller actually sent. Every field is
            // optional, so the older `{ skipChecks }` shape and a partial update
            // both work; an absent field leaves the current value untouched.
            if (incoming.SkipChecks is bool skipChecks)
            {
                _config.SkipChecks = skipChecks;
            }

            // demo_mode / nhl_mode are sidecar start-up flags (BuildArguments maps
            // them to --nhl / --no-demo), so a live change only takes effect after
            // a restart. Track whether either actually changed on disk.
            var restartNeeded = false;

            if (incoming.DemoMode is bool demoMode && demoMode != _config.Server.DemoMode)
            {
                _config.Server.DemoMode = demoMode;
                restartNeeded = true;
            }

            if (incoming.NhlMode is bool nhlMode && nhlMode != _config.Server.NhlMode)
            {
                _config.Server.NhlMode = nhlMode;
                restartNeeded = true;
            }

            // auto_start only gates launch at startup; no restart required.
            if (incoming.AutoStart is bool autoStart)
            {
                _config.Server.AutoStart = autoStart;
            }

            ConfigStore.Save(_config);

            if (restartNeeded && _sidecar?.State == SidecarState.Running)
            {
                // StateChanged re-posts deps:status; the restart itself streams to
                // the UI via server:log.
                _sidecar.Restart();
            }
        }
        catch (JsonException ex)
        {
            System.Diagnostics.Debug.WriteLine($"[ipc] config:save parse failed: {ex.Message}");
        }
    }

    /// <summary>
    /// Payload of the <c>config:save</c> message (mirrors ui/src/lib/ipc.ts).
    /// All fields are nullable so a caller can send any subset.
    /// </summary>
    private sealed record ConfigSavePayload(
        bool? SkipChecks,
        bool? DemoMode,
        bool? NhlMode,
        bool? AutoStart);

    // ----------------------------------------------------------------------
    // Setup wizard
    // ----------------------------------------------------------------------

    /// <summary>Run one wizard step; progress is streamed via <see cref="OnSetupProgress"/>.</summary>
    private async Task RunSetupStepAsync(string payloadJson)
    {
        if (_setup is null)
        {
            return;
        }

        int step;
        try
        {
            step = JsonSerializer.Deserialize<SetupStartPayload>(payloadJson, JsonOptions)?.Step ?? 0;
        }
        catch (JsonException)
        {
            step = 0;
        }

        if (!Enum.IsDefined(typeof(SetupStep), step))
        {
            System.Diagnostics.Debug.WriteLine($"[ipc] setup:start with unknown step {step}");
            PostDepsStatus();
            return;
        }

        try
        {
            await _setup.RunAsync((SetupStep)step);
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"[ipc] setup step {step} threw: {ex}");
        }

        // Re-probe so the Setup Summary reflects whatever the step changed.
        PostDepsStatus();
    }

    /// <summary>Forward a <see cref="SetupService"/> progress update to the UI.</summary>
    private void OnSetupProgress(object? sender, SetupProgress progress)
        => _ipc?.PostToWeb(IpcMessageTypes.SetupProgress, new
        {
            step = progress.Step,
            status = progress.Status,
            detail = progress.Detail,
        });

    /// <summary>
    /// Handle <c>setup:complete</c>: re-probe, and persist <c>skip_checks: true</c> when the
    /// payload asks for it (accepts either <c>skipChecks</c> or <c>skip_checks</c>).
    /// </summary>
    private void HandleSetupComplete(string payloadJson)
    {
        try
        {
            using var doc = JsonDocument.Parse(payloadJson);
            var root = doc.RootElement;

            if (root.ValueKind == JsonValueKind.Object &&
                (IsTrue(root, "skipChecks") || IsTrue(root, "skip_checks")))
            {
                _config.SkipChecks = true;
                ConfigStore.Save(_config);
            }
        }
        catch (JsonException ex)
        {
            System.Diagnostics.Debug.WriteLine($"[ipc] setup:complete parse failed: {ex.Message}");
        }

        PostDepsStatus();
    }

    private static bool IsTrue(JsonElement element, string name)
        => element.TryGetProperty(name, out var value) && value.ValueKind == JsonValueKind.True;

    /// <summary>Payload of the <c>setup:start</c> message (mirrors ui/src/lib/ipc.ts).</summary>
    private sealed record SetupStartPayload(int Step);

    // ----------------------------------------------------------------------
    // System tray
    // ----------------------------------------------------------------------

    /// <summary>
    /// Create the tray icon. The image comes from <c>Assets\MidiMAT.ico</c> next to the
    /// EXE (copied by MidiMAT.csproj); if that is missing we fall back to the icon
    /// embedded in our own executable by <c>&lt;ApplicationIcon&gt;</c>.
    /// </summary>
    private void InitTray()
    {
        try
        {
            Tray.Icon = LoadTrayIcon();
            Tray.LeftClickCommand = new TrayRelayCommand(ShowFromTray);
            Tray.ForceCreate();
            LogToFile($"tray: created={Tray.IsCreated}");
        }
        catch (Exception ex)
        {
            // A missing tray icon degrades the app; it must not take it down.
            LogToFile($"tray init failed: {ex}");
        }
    }

    private static System.Drawing.Icon? LoadTrayIcon()
    {
        var icoPath = Path.Combine(AppContext.BaseDirectory, "Assets", "MidiMAT.ico");
        if (File.Exists(icoPath))
        {
            return new System.Drawing.Icon(icoPath);
        }

        // Single-file publish keeps the icon inside the EXE rather than on disk.
        var exe = Environment.ProcessPath;
        return exe is null ? null : System.Drawing.Icon.ExtractAssociatedIcon(exe);
    }

    private void DisposeTray()
    {
        try
        {
            Tray.Dispose();
        }
        catch
        {
            // Already torn down by the runtime; nothing useful to do.
        }
    }

    private void OnAppWindowClosing(AppWindow sender, AppWindowClosingEventArgs args)
    {
        if (_reallyQuitting)
        {
            return;
        }

        // Keep the sidecar alive: the overlay in OBS talks to it over localhost, so
        // exiting here would black out the Browser Source mid-set.
        args.Cancel = true;
        _appWindow?.Hide();

        if (!_explainedTray)
        {
            _explainedTray = true;
            try
            {
                Tray.ShowNotification(
                    "MidiMAT is still running",
                    "Your overlay in OBS keeps working. Click the tray icon to reopen, or use Quit MidiMAT.");
            }
            catch (Exception ex)
            {
                LogToFile($"tray notification failed: {ex}");
            }
        }
    }

    private void ShowFromTray()
    {
        try
        {
            _appWindow?.Show();
            Activate();
        }
        catch (Exception ex)
        {
            LogToFile($"tray show failed: {ex}");
        }
    }

    private void TrayShow_Click(object sender, RoutedEventArgs e) => ShowFromTray();

    private void TrayOverlay_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            // Exactly the URL the streaming instructions tell people to add to OBS.
            System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo
            {
                FileName = "http://127.0.0.1:8080/overlay/index.html",
                UseShellExecute = true,
            });
        }
        catch (Exception ex)
        {
            LogToFile($"tray overlay open failed: {ex}");
        }
    }

    private void TrayQuit_Click(object sender, RoutedEventArgs e)
    {
        _reallyQuitting = true;
        Close();
    }

    /// <summary>
    /// Minimal ICommand so the tray's left click works without pulling in an MVVM toolkit.
    /// CanExecute is constant, hence the no-op CanExecuteChanged.
    /// </summary>
    private sealed class TrayRelayCommand(Action action) : ICommand
    {
        public event EventHandler? CanExecuteChanged
        {
            add { }
            remove { }
        }

        public bool CanExecute(object? parameter) => true;

        public void Execute(object? parameter) => action();
    }

    /// <summary>
    /// Minimal file log at %LOCALAPPDATA%\MidiMAT\logs\app.log. The shell is a
    /// single-file WinExe with no console, so without this a startup exception
    /// (which would silently skip the dependency post AND the sidecar start) is invisible.
    /// </summary>
    internal static void LogToFile(string message)
    {
        try
        {
            Directory.CreateDirectory(Path.Combine(ConfigStore.AppDataDirectory, "logs"));
            File.AppendAllText(
                Path.Combine(ConfigStore.AppDataDirectory, "logs", "app.log"),
                $"{DateTimeOffset.Now:O} {message}{Environment.NewLine}");
        }
        catch
        {
            // Logging must never take the app down.
        }
    }
}
