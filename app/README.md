# MidiMAT — Windows Shell

The native desktop shell for MidiMAT: a **C# / WinUI 3 (Windows App SDK)** app that hosts the
management UI in a single **WebView2** control and supervises the Python sidecar. It is
**implemented** (no longer a scaffold). Architecture lives in
[`../docs/DESIGN_APP.md`](../docs/DESIGN_APP.md).

The window contains **only a WebView2** — there is no native navigation/chrome; the React app
owns the sidebar and routing. (An early scaffold also shipped a native `NavigationView`, which
produced a double sidebar; it was removed.)

## What works today

- **WebView2** hosting the built React app from the virtual origin `https://midimat.local/`
  (mapped onto `Resources/ui`; built by `ui/` — see [`../ui/README.md`](../ui/README.md)).
- **IpcBridge** — typed `window.chrome.webview` ↔ C# messaging; all §3.1 message types are
  centralized as constants and mirrored in `ui/src/lib/ipc.ts`.
- **ConfigStore** — atomic read/write of `%LOCALAPPDATA%\MidiMAT\config.json` (§6 schema).
- **DependencyChecker** — registry + filesystem probes for loopMIDI, Traktor, OBS and WebView2;
  the snapshot is pushed to the UI as `deps:status`.
- **LoopMidiInstaller** — REAL: detects the install, downloads the **pinned** vendor archive and
  verifies its SHA-256, runs the silent installer, provisions the port under
  `HKCU\…\Tobias Erichsen\loopMIDI\Ports`, restarts `loopMIDI.exe`, and confirms the port via
  Win32 `midiOutGetDeviceCaps`.
- **TraktorConfig** — REAL: finds the newest `Traktor Settings.tsi` and surgically sets the
  `Generic MIDI` out-port (`DDPT`) and injects out-mappings (`CMAI`+`DCBM`); refuses to write
  while Traktor is running.
- **ObsDetector** — REAL: locates OBS Studio / Streamlabs and describes the Browser Source.
- **SidecarExtractor + SidecarManager** — install the bundled `sidecar\` payload to
  `%LOCALAPPDATA%\MidiMAT\sidecar\` on first run, then launch/monitor/restart the sidecar
  (exponential backoff, cap 5). **Auto-start is ON** (`AutoStartEnabled == true`), additionally
  gated on `config.server.auto_start`.
- **SetupService** — runs the six wizard steps and streams `setup:progress`.

## Build

```powershell
cd app
dotnet build -c Debug -p:Platform=x64
```

Output: `app\bin\x64\Debug\net10.0-windows10.0.26100.0\win-x64\MidiMAT.exe`

Run it (shows the built React UI, or a red "UI assets not found" page if `ui/` has not been
built into `Resources/ui`):

```powershell
dotnet run -c Debug -p:Platform=x64
```

Release publish (single-file; matches DESIGN_APP.md §7):

```powershell
dotnet publish C:\_dev\MidiMAT\app\MidiMAT.csproj -c Release -r win-x64 `
  -p:Platform=x64 `
  -p:PublishSingleFile=true `
  -p:SelfContained=true `
  -p:EnableMsixTooling=true `
  -p:IncludeNativeLibrariesForSelfExtract=true `
  -p:EnableCompressionInSingleFile=true `
  -o ..\dist
```

`EnableMsixTooling=true` is **required** — `PublishSingleFile` on an unpackaged WinUI 3 app
errors out without it. The app itself stays unpackaged (`WindowsPackageType=None`).

## Prerequisites

- **.NET 10 SDK** (the TFM is `net10.0-windows10.0.26100.0`).
- **No WinUI workload is required** — WinUI 3 ships via NuGet (`Microsoft.WindowsAppSDK`).
- The **WebView2 Evergreen Runtime** on the target machine (pre-installed on current Win10/11).
- Optional, for editing in VS: Visual Studio 2022/2026 with the **.NET Desktop Development**
  workload + the **Windows App SDK C# templates** component.

## Package versions (pinned)

| Package | Version | Why |
|---|---|---|
| `Microsoft.WindowsAppSDK` | 2.6.5 | WinUI 3 + the WinUI `WebView2` control. |
| `Microsoft.Windows.SDK.BuildTools` | 10.0.28000.2957 | Native build tooling the XAML compiler needs. |
| `Microsoft.Web.WebView2` | 1.0.4314.35 | `CoreWebView2` APIs (`SetVirtualHostNameToFolderMapping`, etc.). |

`WindowsPackageType=None` + `WindowsAppSDKSelfContained=true` make the app **unpackaged** and
**runtime-free** (no machine-wide Windows App SDK runtime needed).

## Project layout

```
app/
├── MidiMAT.csproj            # net10.0-windows, WinUI 3, x64, unpackaged
├── app.manifest              # PerMonitorV2 DPI; requestedExecutionLevel=asInvoker
├── App.xaml(.cs)             # entry point
├── MainWindow.xaml(.cs)      # one <WebView2/>; boots it, wires IPC, supervises the sidecar
├── Services/
│   ├── DependencyChecker.cs  # REAL — registry/file probes
│   ├── LoopMidiInstaller.cs  # REAL — download+verify, port (HKCU), restart, liveness
│   ├── TraktorConfig.cs      # REAL — newest TSI finder; DDPT out-port + CMAI/DCBM injection
│   ├── ObsDetector.cs        # REAL — locates OBS/Streamlabs; Browser Source guide
│   ├── SidecarManager.cs     # REAL — sidecar lifecycle (auto-start enabled)
│   ├── SidecarExtractor.cs   # REAL — installs the bundled sidecar\ payload on first run
│   ├── SetupService.cs       # REAL — the six wizard steps
│   ├── ConfigStore.cs        # REAL — atomic JSON config
│   └── IpcBridge.cs          # REAL — WebView2 messaging
└── Resources/ui/             # built React app (+ .gitkeep)
```

## Not implemented yet

- **System tray icon** — `H.NotifyIcon.WinUI` in `MainWindow.xaml`; closing the window hides
  to the tray (the sidecar keeps running for OBS), left-click reopens, context menu = Show /
  Open overlay / Quit. Icon: `Assets\MidiMAT.ico` (+ `<ApplicationIcon>` for Explorer).
- **Auto-start on Windows login** — not implemented yet.
- **`--managed` flag** — `sidecar/server.py` does not accept it, so `SidecarManager` keeps
  `PassManagedFlag = false` to avoid crashing argparse (DESIGN_APP.md §11).
- OBS **scene-collection automation** — the wizard shows the Browser Source URL/checkbox guide;
  it does not create the source for you.

## Dev tip: point WebView2 at the Vite dev server

`MainWindow.xaml.cs` always navigates to `https://midimat.local/index.html` (the built bundle).
For UI iteration either re-run `npm run build` and relaunch, or temporarily replace that call
with `core.Navigate("http://localhost:5173")` while `npm run dev` is running.
