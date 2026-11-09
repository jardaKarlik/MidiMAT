using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using MidiMAT.Services;

namespace MidiMAT;

/// <summary>
/// Native shell window: a single WebView2 that hosts the React management UI.
/// The web app owns ALL navigation and chrome (its own left sidebar); this class is
/// deliberately thin — it boots WebView2, wires the IPC bridge, and pushes the loaded
/// config to the page. Native-only concerns (tray, dependency checks, sidecar) live in
/// Services/ and are driven from here or from IPC handlers later.
/// </summary>
public sealed partial class MainWindow : Window
{
    private IpcBridge? _ipc;

    public MainWindow()
    {
        InitializeComponent();
        Title = "MidiMAT";

        // Do not await here (ctor cannot be async); the Loaded handler does the async init.
        WebView.Loaded += WebView2_Loaded;
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
            // Fail loudly rather than showing a blank window.
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

        _ipc = new IpcBridge(WebView);
        _ipc.MessageFromWeb += OnMessageFromWeb;

        core.NavigationCompleted += (_, _) =>
        {
            // Push the persisted config so the page can render real state on first paint.
            // (The page itself decides which screen is active.)
            _ipc?.PostToWeb(IpcMessageTypes.ConfigLoaded, ConfigStore.Load());
        };

        core.Navigate("https://midimat.local/index.html");
    }

    private void OnMessageFromWeb(object? sender, IpcMessage message)
    {
        // Central place to fan page-originated messages into native services.
        // In this scaffold we only log; real handlers (setup steps, server control,
        // config save, dependency installs) are added later.
        System.Diagnostics.Debug.WriteLine($"[ipc] {message.Type}: {message.PayloadJson}");
    }
}
