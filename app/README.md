# MidiMAT — Windows Shell (scaffold)

The native desktop shell for MidiMAT: a **C# / WinUI 3 (Windows App SDK)** app that hosts
the management UI in a single **WebView2** control and (later) supervises the Python
sidecar. This is a **scaffold**: it builds and runs, but most behavior is clearly-marked
stubs. Architecture lives in [`../docs/DESIGN_APP.md`](../docs/DESIGN_APP.md).

## What works today

- **NavigationView** (left pane) with the five screens from the design — Setup Summary,
  Status, Editor, Map New Device, Help. Selecting an item does **not** switch native
  pages; it posts an `ipc:navigate` message and the (future) web app routes itself.
- **WebView2** content area loading `Resources/ui/index.html` from a virtual origin
  (`https://midimat.local/`). The placeholder page is dark with a "MidiMAT" wordmark.
- **IpcBridge** — typed `window.chrome.webview` ↔ C# messaging with all §3.1 message
  types centralized as constants.
- **ConfigStore** — atomic read/write of `%LOCALAPPDATA%\MidiMAT\config.json` (§6 schema).
- **DependencyChecker** — registry + filesystem probes for loopMIDI, Traktor, OBS, WebView2.
- **SidecarManager** — spawn/stop/restart with stdout/stderr capture and exponential-backoff
  restart (cap 5). **Nothing spawns by default** (`AutoStartEnabled == false`).

## Build

```powershell
cd app
dotnet build -c Debug -p:Platform=x64
```

Output: `app\bin\x64\Debug\net10.0-windows10.0.26100.0\win-x64\MidiMAT.exe`

Run the shell (it will show the placeholder UI):

```powershell
dotnet run -c Debug -p:Platform=x64
```

Release publish (single-file, matches DESIGN_APP.md §7):

```powershell
dotnet publish C:\_dev\MidiMAT\app\MidiMAT.csproj -c Release -r win-x64 `
  -p:Platform=x64 `
  -p:PublishSingleFile=true `
  -p:IncludeNativeLibrariesForSelfExtract=true `
  -p:EnableCompressionInSingleFile=true `
  -o ..\dist
```

## Prerequisites

- **.NET 10 SDK** (verified with 10.0.401). The TFM is `net10.0-windows10.0.26100.0`.
- **No WinUI workload is required** — WinUI 3 ships via NuGet (`Microsoft.WindowsAppSDK`).
- The **WebView2 Evergreen Runtime** on the target machine (pre-installed on current Win10/11).
- Optional, for editing in VS: Visual Studio 2022/2026 with the **.NET Desktop Development**
  workload + the **Windows App SDK C# templates** component.
- Optional, to regenerate from a template:
  `dotnet new install Microsoft.WindowsAppSDK.WinUI.CSharp.Templates`

## Package versions (pinned)

| Package | Version | Why |
|---|---|---|
| `Microsoft.WindowsAppSDK` | 2.6.5 | Latest stable at scaffold time; provides WinUI 3 + the WinUI `WebView2` control. |
| `Microsoft.Windows.SDK.BuildTools` | 10.0.28000.2957 | Native build tooling the XAML compiler needs. |
| `Microsoft.Web.WebView2` | 1.0.4314.35 | `CoreWebView2` APIs (`SetVirtualHostNameToFolderMapping`, etc.). |

`WindowsPackageType=None` + `WindowsAppSDKSelfContained=true` make the app **unpackaged**
and **runtime-free** (no machine-wide Windows App SDK runtime needed).

## Project layout

```
app/
├── MidiMAT.csproj            # net10.0-windows, WinUI 3, x64, unpackaged
├── app.manifest              # PerMonitorV2 DPI; requestedExecutionLevel=asInvoker
├── App.xaml(.cs)             # entry point
├── MainWindow.xaml(.cs)      # NavigationView + WebView2 (wiring only)
├── Services/
│   ├── DependencyChecker.cs  # REAL — registry/file probes
│   ├── ConfigStore.cs        # REAL — atomic JSON config
│   ├── IpcBridge.cs          # REAL — WebView2 messaging
│   ├── SidecarManager.cs     # REAL-ish — lifecycle (auto-start disabled)
│   ├── LoopMidiInstaller.cs  # STUB
│   ├── TraktorConfig.cs      # STUB
│   └── ObsDetector.cs        # STUB
├── Resources/ui/index.html   # placeholder page (dark + "MidiMAT")
└── Assets/.gitkeep           # app icon added later
```

## Stubbed / not implemented (by design)

- **loopMIDI install** (`LoopMidiInstaller`) — download + SHA-256 verify + elevated
  `/VERYSILENT` install → creates the virtual port. Documented contract in the class.
- **Traktor TSI injection** (`TraktorConfig`) — only *locates* `Traktor Settings.tsi`;
  surgical `Generic MIDI` out-mapping injection (§5.1) is a later task.
- **OBS automation** (`ObsDetector`) — only *locates* OBS; programmatic Browser Source
  config is out of scope for v1.
- **Sidecar auto-start** — off via the `SidecarManager.AutoStartEnabled` const; flip it to
  true once the PyInstaller bundle exists.
- **`--managed` flag** — `sidecar/server.py` does not accept it yet (see DESIGN_APP.md §11),
  so `SidecarManager` keeps `PassManagedFlag = false` to avoid crashing argparse.

## Out of scope (later tasks)

- The real **React + Vite + Tailwind management UI** — the placeholder page stands in.
- **PyInstaller packaging** of the Python sidecar.
- The **system tray** icon and auto-start-on-login.
- Traktor TSI injection, real loopMIDI download/install, real OBS automation.

## Dev tip: point WebView2 at the Vite dev server

When the React UI exists, skip the placeholder by navigating to the dev server instead:
replace the `core.Navigate("https://midimat.local/index.html")` call in
`MainWindow.xaml.cs` with `core.Navigate("http://localhost:5173")` while developing.
