using System.Text.Json;
using Microsoft.UI.Xaml.Controls;
using Microsoft.Web.WebView2.Core;

namespace MidiMAT.Services;

/// <summary>
/// The IPC message type strings from DESIGN_APP.md §3.1, centralized so C# and the
/// (future) TypeScript client never drift. Keep this in sync with ui/src/lib/ipc.ts.
/// </summary>
public static class IpcMessageTypes
{
    // ---- React  ->  C# -------------------------------------------------------
    public const string Navigate = "navigate";              // { page }
    public const string SetupStart = "setup:start";         // { step }
    public const string SetupComplete = "setup:complete";   // { step }
    public const string ServerRestart = "server:restart";   // {}
    public const string ServerStop = "server:stop";         // {}
    public const string ConfigSave = "config:save";         // { skipChecks: bool }

    // ---- C#  ->  React -------------------------------------------------------
    public const string DepsStatus = "deps:status";         // { loopMidi, traktor, obs, python, server }
    public const string ServerLog = "server:log";           // { line, level, ts }
    public const string SetupProgress = "setup:progress";   // { step, status, detail }
    public const string ConfigLoaded = "config:loaded";     // { ...midimat.config.json }
}

/// <summary>A message received from the web page (already split into type + payload JSON).</summary>
public sealed record IpcMessage(string Type, string PayloadJson);

/// <summary>
/// Real WebView2 &lt;-&gt; C# message bridge. Wraps the raw
/// <c>window.chrome.webview</c> postMessage plumbing behind typed helpers.
/// </summary>
public sealed class IpcBridge
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    private readonly WebView2 _webView;

    /// <summary>Raised for every message the page posts to C#. Fires on the UI thread.</summary>
    public event EventHandler<IpcMessage>? MessageFromWeb;

    public IpcBridge(WebView2 webView)
    {
        _webView = webView;

        if (_webView.CoreWebView2 is null)
        {
            throw new InvalidOperationException(
                "IpcBridge requires CoreWebView2 to be initialized first " +
                "(await WebView.EnsureCoreWebView2Async()).");
        }

        _webView.CoreWebView2.WebMessageReceived += OnWebMessageReceived;
    }

    /// <summary>
    /// Send a typed message to the page as <c>{ "type": "...", "payload": { ... } }</c>.
    /// Safe to call from any thread (marshals to the UI thread).
    /// </summary>
    public void PostToWeb(string type, object? payload = null)
    {
        var json = JsonSerializer.Serialize(new { type, payload }, JsonOptions);

        if (_webView.DispatcherQueue.HasThreadAccess)
        {
            PostNow(json);
        }
        else
        {
            _webView.DispatcherQueue.TryEnqueue(() => PostNow(json));
        }
    }

    private void PostNow(string json)
    {
        // Page may have navigated away / been disposed between enqueue and execution.
        _webView.CoreWebView2?.PostWebMessageAsJson(json);
    }

    private void OnWebMessageReceived(CoreWebView2 sender, CoreWebView2WebMessageReceivedEventArgs args)
    {
        string type;
        string payloadJson;

        try
        {
            using var doc = JsonDocument.Parse(args.WebMessageAsJson);
            var root = doc.RootElement;

            type = root.TryGetProperty("type", out var t) && t.ValueKind == JsonValueKind.String
                ? t.GetString() ?? string.Empty
                : string.Empty;

            payloadJson = root.TryGetProperty("payload", out var p)
                ? p.GetRawText()
                : "null";
        }
        catch (JsonException)
        {
            // Not our protocol (e.g. a bare string postMessage). Surface it as-is.
            type = string.Empty;
            payloadJson = args.WebMessageAsJson;
        }

        MessageFromWeb?.Invoke(this, new IpcMessage(type, payloadJson));
    }
}
