# MidiMAT — Desktop Application Architecture

> **Status:** DRAFT — awaiting review before implementation
> **Target:** Single-file Windows EXE, ~35MB, zero prerequisites

## 1. Overview

MidiMAT ships as a single `MidiMAT.exe` that:
1. Detects and auto-installs missing dependencies (loopMIDI, Traktor config)
2. Runs the Python sidecar (MIDI → WebSocket → overlay server)
3. Presents a modern management UI (setup wizard, status, editor, device mapper, help)
4. Sits in the system tray when minimized

The EXE is a **.NET 8 single-file publish** of a **WinApp SDK (WinUI 3)** app that hosts a
**WebView2** control rendering a **React + Tailwind** management UI. The Python sidecar is
bundled as a **PyInstaller** executable in the app's resources and spawned as a child process.

```
┌─────────────────────────────────────────────────────────────────────┐
│  MidiMAT.exe  (.NET 8 / WinApp SDK / WinUI 3)                      │
│                                                                     │
│  ┌──────────────┐  ┌────────────────────────────────────────────┐   │
│  │  XAML Shell  │  │  WebView2 (Chromium)                       │   │
│  │              │  │                                            │   │
│  │  • Sidebar   │  │  ┌──────────────────────────────────────┐  │   │
│  │  • SysTray   │  │  │  React + Tailwind + Aceternity UI    │  │   │
│  │  • Titlebar  │  │  │                                      │  │   │
│  │  • Deps      │  │  │  Setup Summary │ Status │ Editor     │  │   │
│  │    checker   │◄─┼──┤  Map Device    │ Help                │  │   │
│  │              │  │  │                                      │  │   │
│  └──────────────┘  │  └──────────────┬───────────────────────┘  │   │
│                    │                 │ window.chrome.webMessage   │   │
│                    └─────────────────┼────────────────────────────┘   │
│                                      │                                │
│  ┌───────────────────────────────────▼────────────────────────────┐   │
│  │  Python Sidecar  (PyInstaller bundle, spawned as subprocess)   │   │
│  │                                                                │   │
│  │  HTTP :8080  →  overlay/index.html  (OBS browser source)       │   │
│  │  HTTP :8080  →  overlay/edit.html   (legacy editor, kept)      │   │
│  │  WS   :8787  →  MIDI/NHL events → overlay                     │   │
│  │  REST :8080  →  /api/controls, /api/suggest, /api/refit       │   │
│  │                                                                │   │
│  │  midi_tap.py  │  nhl_tap.py  │  mapping.py  │  suggest.py     │   │
│  └────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## 2. Component Breakdown

### 2.1 WinApp SDK Shell (C# / .NET 8)

**Responsibilities:**
- Native window with sidebar navigation
- System tray icon (shows server running/stopped status)
- Dependency detection (registry, filesystem, process checks)
- Silent loopMIDI installation
- Python sidecar lifecycle (start, monitor, stop)
- WebView2 ↔ C# IPC bridge (via `window.chrome.webmessage`)
- Application state persistence (`midimat.config.json`)
- Auto-start on Windows login (optional, via registry)

**Key files (new):**
```
app/
├── MidiMAT.csproj              # .NET 8, WinApp SDK, WebView2
├── App.xaml / App.xaml.cs      # Application entry point
├── MainWindow.xaml             # Shell: sidebar + WebView2
├── MainWindow.xaml.cs          # Sidecar lifecycle, IPC bridge
├── Services/
│   ├── DependencyChecker.cs    # loopMIDI, Traktor, OBS, Python detection
│   ├── LoopMidiInstaller.cs    # Silent install loopMIDI + create port
│   ├── TraktorConfig.cs        # Find/copy TSI, detect Traktor version
│   ├── ObsDetector.cs          # Find OBS, generate Browser Source config
│   ├── SidecarManager.cs       # Spawn/monitor/kill Python sidecar
│   ├── ConfigStore.cs          # Read/write midimat.config.json
│   └── IpcBridge.cs            # WebView2 ↔ C# message passing
├── Resources/
│   ├── midimat-server.exe      # PyInstaller bundle (embedded resource)
│   ├── loopmidi-setup.exe      # Bundled loopMIDI installer (~2MB)
│   ├── traktor-mapping.tsi     # Bundled Traktor out-mapping
│   └── overlay/                # Copied from repo root at build time
│       ├── index.html
│       ├── overlay.js
│       └── edit.html
└── Assets/
    ├── MidiMAT.ico             # App icon (logo variant B)
    └── SplashScreen.png        # Startup splash
```

### 2.2 React Management UI (in WebView2)

**Responsibilities:**
- Setup wizard (first-run experience, 6 steps)
- Setup summary dashboard (component status cards)
- Server status with live log output
- Visual editor (screenshot upload, box placement, AI suggest)
- Device mapping wizard (step-by-step with live MIDI signal display)
- Help screen (switches, limitations, credits, donate link)

**Technology:**
- React 19 + TypeScript
- Tailwind CSS 4
- Vite (bundler)
- Aceternity UI components (Evervault Card, Wobble Card)
- Framer Motion (page transitions, micro-animations)
- Inter font (UI text) + JetBrains Mono (logs, technical values)

**Key files (new):**
```
ui/
├── package.json
├── vite.config.ts
├── tailwind.config.ts
├── index.html                  # Entry point loaded by WebView2
├── src/
│   ├── main.tsx                # React root
│   ├── App.tsx                 # Router + layout (sidebar)
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx         # Navigation sidebar
│   │   │   ├── TitleBar.tsx        # Custom title bar
│   │   │   └── PageTransition.tsx  # Framer Motion wrapper
│   │   ├── setup/
│   │   │   ├── SetupWizard.tsx     # 6-step wizard
│   │   │   ├── StepLoopMidi.tsx
│   │   │   ├── StepTraktor.tsx
│   │   │   ├── StepPython.tsx
│   │   │   ├── StepServer.tsx
│   │   │   ├── StepObs.tsx
│   │   │   └── StepSave.tsx
│   │   ├── dashboard/
│   │   │   ├── SetupSummary.tsx    # Component status cards
│   │   │   ├── StatusCard.tsx      # Wobble Card for server
│   │   │   └── ComponentCard.tsx   # Evervault Card for deps
│   │   ├── editor/
│   │   │   ├── EditorScreen.tsx    # Wrapper around existing editor
│   │   │   └── EditorGuide.tsx     # Screenshot + instructions
│   │   ├── mapper/
│   │   │   ├── MapDevice.tsx       # Device mapping wizard
│   │   │   ├── SignalCapture.tsx   # Live MIDI signal display
│   │   │   └── MappingSteps.tsx    # Step-by-step guide
│   │   ├── help/
│   │   │   └── HelpScreen.tsx      # All-in-one help
│   │   └── ui/                     # Aceternity-inspired primitives
│   │       ├── evervault-card.tsx
│   │       ├── wobble-card.tsx
│   │       ├── glowing-card.tsx
│   │       ├── pulse-dot.tsx
│   │       └── animated-border.tsx
│   ├── hooks/
│   │   ├── useIpc.ts              # C# ↔ React message bridge
│   │   ├── useServerStatus.ts     # WebSocket to sidecar
│   │   └── useSetupState.ts       # Setup wizard state
│   ├── lib/
│   │   ├── ipc.ts                 # Typed IPC protocol
│   │   └── constants.ts           # Ports, URLs, paths
│   └── styles/
│       └── globals.css            # Tailwind + design tokens
└── public/
    └── fonts/                     # Inter + JetBrains Mono (WOFF2)
```

### 2.3 Python Sidecar (existing, bundled via PyInstaller)

**No major changes needed.** The existing `sidecar/server.py` already provides:
- HTTP static server (overlay + editor)
- WebSocket broadcaster (MIDI events)
- REST API (`/api/controls`, `/api/suggest`, `/api/refit`)
- MIDI tap + NHL tap + mapping resolver

**Additions:**
- `--managed` flag: tells sidecar it's running under the desktop app
  - Logs go to a file the C# shell reads and displays in the Status screen
  - JSON status messages on stdout for the C# shell to parse
- Health endpoint: `GET /api/health` returns `{status: "ok", uptime, midi_ports, ...}`

**PyInstaller spec (new):**
```
build/
└── midimat-server.spec    # PyInstaller config
                            # Entry: sidecar/server.py
                            # Includes: overlay/, mapping/, models/
                            # Hidden imports: websockets, mido, rtmidi,
                            #   opencv, numpy, ultralytics, hidapi
```

## 3. IPC Protocol (C# -> React -> Python)

Three layers of communication:

### 3.1 C# -> React (WebView2 webmessage)

```typescript
// React → C#
window.chrome.webview.postMessage({
  type: "navigate",        // or "setup:complete", "server:restart", etc.
  payload: { page: "status" }
});

// C# → React
window.chrome.webview.addEventListener("message", (e) => {
  // { type: "deps:status", payload: { loopMidi: true, traktor: false, ... } }
  // { type: "server:log", payload: { line: "14:32:01 INFO | MIDI on port..." } }
  // { type: "setup:step", payload: { step: 2, status: "running" } }
});
```

**Message types:**
| Direction | Type | Payload |
|-----------|------|---------|
| R→C | `navigate` | `{ page }` |
| R→C | `setup:start` | `{ step }` |
| R→C | `setup:complete` | `{ step }` |
| R→C | `server:restart` | `{}` |
| R→C | `server:stop` | `{}` |
| R→C | `config:save` | `{ skipChecks: bool }` |
| C→R | `deps:status` | `{ loopMidi, traktor, obs, python, server }` |
| C→R | `server:log` | `{ line, level, ts }` |
| C→R | `setup:progress` | `{ step, status, detail }` |
| C→R | `config:loaded` | `{ ...midimat.config.json }` |

### 3.2 React -> Python (HTTP + WebSocket, unchanged)

The React UI talks to the Python sidecar exactly as the existing overlay does:
- `GET http://127.0.0.1:8080/api/controls` — load control list
- `POST http://127.0.0.1:8080/api/controls` — save editor boxes
- `POST http://127.0.0.1:8080/api/suggest` — AI placement
- `POST http://127.0.0.1:8080/api/refit` — detect & re-fit
- `WS ws://127.0.0.1:8787` — live MIDI events (for SignalCapture in Map Device)
- `GET http://127.0.0.1:8080/api/health` — server health check (new)

### 3.3 C# -> Python (stdout parsing + process management)

C# spawns the sidecar and reads its stdout:
```
[SidecarManager] spawns: midimat-server.exe --managed --midi --nhl
[SidecarManager] reads stdout line by line:
  → 14:32:01.234 INFO  sidecar.server | overlay: http://127.0.0.1:8080/...
  → 14:32:01.456 INFO  sidecar.server | WebSocket ready on ws://127.0.0.1:8787
  → 14:32:05.789 INFO  sidecar.midi_tap | midi| connected: TRAKTOR X1 MK3
[SidecarManager] forwards to React as server:log messages
[SidecarManager] polls GET /api/health every 5s for status
```

## 4. Setup Wizard Flow

First launch triggers the wizard. Subsequent launches skip to the summary
(unless `skip_checks` is false in config).

```
┌──────────────────────────────────────────────────────────┐
│  SETUP WIZARD                                            │
│                                                          │
│  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐ │
│  │  1  │→│  2  │→│  3  │→│  4  │→│  5  │→│  6  │ │
│  │loop │  │Trak │  │Pyth │  │Srvr │  │ OBS │  │Save │ │
│  │MIDI │  │tor  │  │on   │  │er   │  │     │  │     │ │
│  └─────┘  └─────┘  └─────┘  └─────┘  └─────┘  └─────┘ │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │                                                    │  │
│  │  [Step content area — see details below]          │  │
│  │                                                    │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│                              [← Back]  [Next →]  [Skip] │
└──────────────────────────────────────────────────────────┘
```

### Step Details

| Step | Check Logic | If Missing |
|------|------------|------------|
| **1. loopMIDI** | Query registry `HKLM\SOFTWARE\TOBIAS-ERICHSEN\loopMIDI` | Show "Installing..." card, **download** the official installer from loopmidi.se (verify SHA-256), run `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART` (needs UAC), then create the port and poll `mido.get_input_names()`. **Do not redistribute** the installer inside our EXE — download at setup time (EULA-clean). Show expected size: ~2 MB. |
| **2. Traktor** | Scan `%USERPROFILE%\Documents\Native Instruments\Traktor <ver>\Traktor Settings.tsi` | **Primary (proven):** surgically inject out-mappings into the existing `Generic MIDI` device — see §5.1. **Fallback:** if the file is absent/locked, guide a manual import. Never overwrite the whole settings file. |
| **3. Python** | Not needed — bundled PyInstaller sidecar includes embedded Python | Show info card: "Python runtime is embedded (~60MB). No installation required." Expected disk: already included in EXE. |
| **4. Server** | Start `midimat-server.exe --managed --midi --nhl` | Show live status card with server URL, WebSocket status, first log lines. "Starting..." → "Running ✓". Expected disk: sidecar is embedded. |
| **5. OBS** | Check registry `HKLM\SOFTWARE\OBS Studio` + common paths | **If found:** Show Browser Source config card with visual guide (screenshots of OBS source properties, URL to paste: `http://127.0.0.1:8080/overlay/index.html`). **If not found:** "OBS not detected. [Download OBS](https://obsproject.com) — wait for install, then click Re-check." |
| **6. Save** | Write `midimat.config.json` with all detected paths + `skip_checks: true` | Summary card: "All set! Next launch will skip checks." Toggle: "Always check on startup" (off by default). |

### Expected Disk Space (shown in wizard)

| Component | Size |
|-----------|------|
| MidiMAT.exe (extracted to %LOCALAPPDATA%\MidiMAT) | ~35MB |
| Python sidecar (extracted alongside) | ~60MB |
| YOLO model (yolo11n.pt) | ~5MB |
| Overlay assets | ~1MB |
| loopMIDI (if installed) | ~2MB |
| **Total** | **~103MB** |

## 5. Traktor configuration

### 5.1. Surgical TSI injection (PROVEN 2026-11-09)

The wizard does **not** overwrite the user's Traktor settings. It injects only the
MidiMAT out-mappings into the existing `Generic MIDI` device.

**Format:** `Traktor Settings.tsi` is XML whose `DeviceIO.Config.*` entry holds a base64
TLV tree:
```
DIOM > DEVS > DEVI(name) > DDAT > DDCB{ CMAS{ CMAI... }, DCBM{ DCBM... } }
```
Each controller is one `DEVI`. MidiMAT's mappings live in the `Generic MIDI` device.

**Algorithm:**
1. Back up `Traktor Settings.tsi` (timestamped, next to the original).
2. Parse the base64 blob; locate the `Generic MIDI` `DEVI`.
3. Read its `DDCB` → list of `CMAI` payloads + `(idx, key)` `DCBM` bindings.
4. Drop any MidiMAT-owned entries already present (idempotency), then append the pack:
   for each control — `CMAI(midi_idx=new idx, mapping_type=1, cmd_id, CMAD{ControlType=0xFFFF, InteractionMode=8, Target=deck})`
   plus `DCBM(new idx, "Ch01.CC.nnn")`.
5. Rebuild the DDCB with updated counts; rebuild DEVI→DEVS→DIOM.
6. Write back with a **surgical regex replace of the `Value="…"` attribute only** —
   never re-serialize the XML (ElementTree rewrites `<Entry></Entry>` to `<Entry />`).

**Constraints (learned the hard way):**
- MIDI **CC range is 0..127** — a key outside Traktor's 4112-control catalog is rejected:
  Traktor keeps the `CMAI` but **silently drops the `DCBM` binding**, and the row shows
  `Mapped to: n/a`.
- `idx` is **device-local and arbitrary** (same control → different idx across factory
  files), so a fresh `max(idx)+2` is valid. `CMAI.midi_idx` resolves via `DCBM[stored_idx]`,
  not array position.
- The library `py-ni-traktor-tsi` `rebuild_tsi()` rewrites **every** DEVI — do not use it;
  write a targeted rebuild.
- Traktor rewrites the file on exit — the wizard must detect a running Traktor and ask the
  user to close it before writing.

**Verification done:** injected one output mapping into a live 100-mapping config —
508 XML entries unchanged, 0 diff outside the blob, all four non-target devices
byte-identical, existing 100 mappings intact, new row correct in Controller Manager.
Reference scripts: `scripts/inspect_tsi_generic.py`, `scripts/prototype_tsi_inject.py`.

### 5.2. NHL / direct-HID (future, not v1)

Reading NI controllers' native vendor-HID stream (usage page `0xFF01`) would remove the
loopMIDI dependency entirely. It is **not a shipping path yet**: `sidecar/nhl_tap.py`
streams reports and the Z1 MK2 is partially decoded (`nhl_map.json`, 10 controls), but the
**X1 MK3 is not decoded at all**. Tracked as a ClickUp follow-up ("Path B"); see
`docs/NHL_PROTOCOL.md`.

## 6. Configuration & State

### `midimat.config.json` (user-editable, in app data folder)

```json
{
  "version": 2,
  "setup_completed": "2026-11-09T14:30:00Z",
  "skip_checks": true,
  "paths": {
    "loopmidi_port": "MidiMAT",
    "traktor_tsi": "C:\\Users\\jaros\\AppData\\Roaming\\Native Instruments\\Traktor 4.5.1\\Traktor Settings.tsi",
    "obs_exe": "C:\\Program Files\\obs-studio\\bin\\64bit\\obs64.exe"
  },
  "server": {
    "http_port": 8080,
    "ws_port": 8787,
    "auto_start": true,
    "demo_mode": false,
    "nhl_mode": true
  },
  "overlay_url": "http://127.0.0.1:8080/overlay/index.html",
  "editor_url": "http://127.0.0.1:8080/overlay/edit.html"
}
```

### State file locations

| File | Location | Purpose |
|------|----------|---------|
| `midimat.config.json` | `%LOCALAPPDATA%\MidiMAT\config.json` | User settings, setup state |
| `midimat-server.exe` | `%LOCALAPPDATA%\MidiMAT\sidecar\` | Extracted sidecar |
| `overlay/` | `%LOCALAPPDATA%\MidiMAT\overlay\` | OBS overlay files |
| `mapping/controls.csv` | `%LOCALAPPDATA%\MidiMAT\mapping\` | Control mappings |
| `cc_map.json` | `%LOCALAPPDATA%\MidiMAT\` | Generated MIDI map |
| `layout.json` | `%LOCALAPPDATA%\MidiMAT\` | Widget positions |
| `logs/` | `%LOCALAPPDATA%\MidiMAT\logs\` | Server + app logs |

**Note:** The `%LOCALAPPDATA%` approach means the EXE is truly portable — user can
put `MidiMAT.exe` on a USB stick, run it on any Windows PC, and all state lives in
`%LOCALAPPDATA%`. First run extracts resources; subsequent runs reuse them.

## 7. Build Pipeline

```
Developer machine                         Output
─────────────────                         ──────

┌─────────────────┐
│ ui/             │ ──→ npm run build ──→ ui/dist/  (React SPA, ~500KB)
│ (React+Vite)    │
└─────────────────┘

┌─────────────────┐
│ sidecar/        │ ──→ pyinstaller ──→ build/midimat-server.exe  (~60MB)
│ (Python)        │     build/midimat-server.spec
└─────────────────┘

┌─────────────────┐
│ app/            │ ──→ dotnet publish ──→ MidiMAT.exe  (~35MB)
│ (C# WinApp SDK) │     -r win-x64 -p:PublishSingleFile=true
│                 │     -p:IncludeNativeLibrariesForSelfExtract=true
│  embeds:        │     -p:EnableCompressionInSingleFile=true
│  • ui/dist/     │
│  • sidecar.exe  │
│  • overlay/     │
│  • loopmidi.exe │
│  • *.tsi        │
└─────────────────┘

                                    ──→ MidiMAT.exe  (single file, ~35MB)
```

### Build commands (final)

```powershell
# 1. Build React UI
cd ui && npm ci && npm run build

# 2. Build Python sidecar
pyinstaller build/midimat-server.spec --clean

# 3. Build single EXE
cd app
dotnet publish -c Release -r win-x64 `
  -p:PublishSingleFile=true `
  -p:SelfContained=true `
  -p:IncludeNativeLibrariesForSelfExtract=true `
  -p:EnableCompressionInSingleFile=true `
  -o ../dist/
```

## 8. Screen Designs (Summary)

### 8.1 Setup Summary (default screen after setup)

```
┌──────────┬─────────────────────────────────────────────────┐
│          │                                                 │
│  LOGO    │  SETUP SUMMARY                                 │
│          │                                                 │
│ ──────── │  ┌─────────────┐  ┌─────────────┐             │
│ ● Setup  │  │ 🎵 loopMIDI │  │ 🎛 Traktor  │             │
│   Status │  │  ✓ Installed│  │  ✓ Configured│             │
│   Editor │  │  Port: MidiM│  │  TSI: v4.5.1│             │
│   Map    │  └─────────────┘  └─────────────┘             │
│   Help   │                                                 │
│          │  ┌─────────────┐  ┌─────────────┐             │
│ ──────── │  │ 🖥 Server   │  │ 📹 OBS      │             │
│ ☕ Support│  │  ● Running │  │  ✓ Detected │             │
│ ⚙ Settings  │  :8080/:8787│  │  Browser Src│             │
│          │  └─────────────┘  └─────────────┘             │
│          │                                                 │
│          │  [Re-run Setup]  [Open Overlay URL]            │
└──────────┴─────────────────────────────────────────────────┘
```

### 8.2 Status Screen

```
┌──────────┬─────────────────────────────────────────────────┐
│          │  SERVER STATUS                                   │
│          │                                                  │
│          │  ┌────────────────────────────────────────────┐  │
│          │  │  ● Running     http://127.0.0.1:8080       │  │
│          │  │  WebSocket:   ws://127.0.0.1:8787          │  │
│          │  │  Uptime: 2h 14m    Events: 1,247           │  │
│          │  │  MIDI ports: TRAKTOR X1 MK3, Z1 MK2        │  │
│          │  │                                            │  │
│          │  │  [Restart Server]  [Stop]  [Open Overlay]  │  │
│          │  └────────────────────────────────────────────┘  │
│          │                                                  │
│          │  SWITCHES                                         │
│          │  ┌────────────────────────────────────────────┐  │
│          │  │  🎮 Demo Mode        [○] Generate fake     │  │
│          │  │                        MIDI events for      │  │
│          │  │                        testing overlay      │  │
│          │  │                                            │  │
│          │  │  🔌 NHL Native Mode  [●] Listen to HID     │  │
│          │  │                        reports from NI      │  │
│          │  │                        controllers in       │  │
│          │  │                        native Traktor mode  │  │
│          │  │                                            │  │
│          │  │  🚀 Auto-start       [●] Launch server     │  │
│          │  │                        when MidiMAT starts  │  │
│          │  └────────────────────────────────────────────┘  │
│          │                                                  │
│          │  SERVER LOG                                       │
│          │  ┌────────────────────────────────────────────┐  │
│          │  │ 14:32:01 INFO  overlay: http://127.0.0.1.. │  │
│          │  │ 14:32:01 INFO  WebSocket ready on ws://... │  │
│          │  │ 14:32:05 INFO  midi| connected: X1 MK3    │  │
│          │  │ 14:33:12 INFO  midi| ch=1 cc=16 val=64    │  │
│          │  └────────────────────────────────────────────┘  │
└──────────┴─────────────────────────────────────────────────┘
```

## 9. Technology Choices

| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| Desktop shell | WinApp SDK (WinUI 3) | 1.6+ | Native Windows, small footprint, system tray |
| Runtime | .NET | 8.0 LTS | Single-file publish, AOT-ready |
| Web runtime | WebView2 | Pre-installed | Same Chromium as Electron, zero bundling |
| Management UI | React | 19 | Aceternity UI compatibility |
| Styling | Tailwind CSS | 4 | Utility-first, design tokens |
| Animations | Framer Motion | 11+ | Page transitions, micro-interactions |
| Bundler | Vite | 6 | Fast HMR, optimized builds |
| Python bundle | PyInstaller | 6.x | Single-file Python executable |
| Installer | .NET single-file | — | No separate installer needed |

## 10. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| WebView2 not installed (rare on Win10+) | App won't render UI | Check on launch, offer to download WebView2 bootloader (~2MB) |
| PyInstaller bundle flagged by antivirus | User can't run sidecar | Sign the EXE with a code signing certificate; use `--onedir` mode if needed |
| Single-file EXE slow first launch (decompression) | 3-5s delay on first run | Use `IncludeNativeLibrariesForSelfExtract` + compression; subsequent launches are cached |
| React + Aceternity in WebView2 | Animation performance | WebView2 is Chromium — same as Electron, same performance. Test on low-end GPU. |
| loopMIDI silent install fails | Setup wizard blocked | Show manual download link as fallback; detect existing installation |
| Traktor TSI format changes | Config import breaks | Bundle a minimal TSI with only out-mappings; guide manual import as primary path |
| Python sidecar crash | Overlay stops | C# monitors process, auto-restarts with exponential backoff, shows error in UI |

## 11. Migration Strategy

What stays vs what changes:

| Component | Current | After | Changes |
|-----------|---------|-------|---------|
| `sidecar/server.py` | Standalone | Bundled in EXE | Add `--managed` flag, `/api/health` endpoint |
| `overlay/index.html` | Standalone HTML | Served by sidecar | **No changes** |
| `overlay/edit.html` | Standalone HTML | Served by sidecar, embedded in Editor screen via WebView2 iframe | **No changes** |
| `overlay/overlay.js` | Static JS | Static JS | **No changes** |
| `scripts/setup_wizard.py` | CLI wizard | Replaced by React setup wizard | **Deprecated** (kept for dev use) |
| `scripts/build_maps.py` | CLI tool | Called by sidecar API | **No changes** |
| `scripts/run.ps1` | Launch script | Replaced by MidiMAT.exe | **Deprecated** |
| `mapping/controls.csv` | Source of truth | Source of truth | **No changes** |
| `layout.json` | Config file | Config file | **No changes** |
| `cc_map.json` | Generated map | Generated map | **No changes** |

**Key principle:** The Python sidecar and overlay are unchanged. We're adding a
native shell around them, not replacing them.

## 12. Development Setup

Prerequisites for building MidiMAT:
- Visual Studio 2022 (with "Windows App SDK" and ".NET desktop" workloads)
- .NET 8 SDK
- Node.js 20+ (for React UI)
- Python 3.14 + venv (for sidecar development)
- PyInstaller (`pip install pyinstaller`)

```powershell
# Clone & setup
git clone https://github.com/jardaKarlik/MidiMAT.git
cd MidiMAT

# Install React UI deps
cd ui && npm install

# Install Python deps
cd .. && python -m venv .venv
.venv\Scripts\activate && pip install -r requirements.txt

# Run in dev mode (C# + hot-reload React + Python sidecar)
# Terminal 1: Start Python sidecar
python sidecar/server.py --midi --nhl

# Terminal 2: Start React dev server
cd ui && npm run dev

# Terminal 3: Start WinApp SDK app (points WebView2 at Vite dev server)
cd app && dotnet run
```
