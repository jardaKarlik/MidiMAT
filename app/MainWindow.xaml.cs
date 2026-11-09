using System.Text.Json;
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

    public MainWindow()
    {
        InitializeComponent();
        Title = "MidiMAT";

        // Do not await here (ctor cannot be async); the Loaded handler does the async init.
        WebView.Loaded += WebView2_Loaded;
        Closed += (_, _) => _sidecar?.Dispose();
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

        _sidecar = new SidecarManager(_config);
        _sidecar.LogLine += OnSidecarLog;
        _sidecar.StateChanged += (_, _) => PostDepsStatus();

        _ipc = new IpcBridge(WebView);
        _ipc.MessageFromWeb += OnMessageFromWeb;

        _setup = new SetupService(_config, _sidecar);
        _setup.ProgressChanged += OnSetupProgress;

        core.NavigationCompleted += (_, _) =>
        {
            // Push persisted config + the first dependency snapshot, then start the sidecar
            // if the user allowed it. (The page decides which screen is active.)
            _ipc?.PostToWeb(IpcMessageTypes.ConfigLoaded, _config);
            PostDepsStatus();
            _sidecar.StartIfAutoStartEnabled();
        };

        core.Navigate("https://midimat.local/index.html");
    }

    /// <summary>Send the current dependency + server snapshot to the UI (<c>deps:status</c>).</summary>
    private void PostDepsStatus()
    {
        var found = DependencyChecker.CheckAll().ToDictionary(d => d.Name, d => d.Found);

        _ipc?.PostToWeb(IpcMessageTypes.DepsStatus, new
        {
            loopMidi = found.GetValueOrDefault(DependencyChecker.LoopMidi),
            traktor = found.GetValueOrDefault(DependencyChecker.Traktor),
            obs = found.GetValueOrDefault(DependencyChecker.Obs),
            // "python" = the sidecar runtime is reachable (bundled EXE, or the dev venv).
            python = _sidecar is not null && SidecarManager.ResolveSidecarLaunch(_config) is not null,
            server = _sidecar?.State == SidecarState.Running,
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
            if (incoming is not null)
            {
                _config.SkipChecks = incoming.SkipChecks;
                ConfigStore.Save(_config);
            }
        }
        catch (JsonException ex)
        {
            System.Diagnostics.Debug.WriteLine($"[ipc] config:save parse failed: {ex.Message}");
        }
    }

    /// <summary>Payload of the <c>config:save</c> message (mirrors ui/src/lib/ipc.ts).</summary>
    private sealed record ConfigSavePayload(bool SkipChecks);

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
}
