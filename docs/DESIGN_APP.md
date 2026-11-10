# MidiMAT — Desktop Application Architecture

> **Status:** IMPLEMENTED — describes the shipped shell, UI and build pipeline
> **Target:** Single-file Windows EXE (`MidiMAT.exe`, ~148 MB), no separate installer

## 1. Overview

MidiMAT ships as a single `MidiMAT.exe` that:
1. Detects and auto-installs missing dependencies (loopMIDI, Traktor config)
2. Runs the Python sidecar (MIDI → WebSocket → overlay server)
3. Presents a modern management UI (setup wizard, status, editor, device mapper, help)
4. Sits in the system tray when the window is closed — closing hides to the tray (so the
   sidecar keeps serving the OBS Browser Source) instead of exiting; login auto-start is
   not implemented yet

The EXE is a **.NET 10 single-file publish** of a **Windows App SDK (WinUI 3)** app whose
window contains **only a WebView2** — there is no native navigation or chrome; the React app
owns all of it. The Python sidecar is bundled as a **PyInstaller onedir** payload in the app's
`sidecar/` folder, spawned as a child process, and installed to `%LOCALAPPDATA%` on first run.

```
┌─────────────────────────────────────────────────────────────────────┐
│  MidiMAT.exe  (.NET 10 / Windows App SDK / WinUI 3, single file)    │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Native shell: MainWindow.xaml is ONE <WebView2/> control.      │ │
│  │  No native NavigationView/titlebar — the React app owns the     │ │
│  │  sidebar, logo and routing.                                     │ │
│  └───────────────────────────────┬────────────────────────────────┘ │
│                                  │ window.chrome.webview (IPC)        │
│                                  ▼                                   │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  React + Tailwind app  (virtual host https://midimat.local/)    │ │
│  │                                                                │ │
│  │  Sidebar:  Setup Summary │ Status │ Editor │ Map New Device    │ │
│  │            │ Help        (+ footer: Support, Settings)          │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Python Sidecar  (PyInstaller onedir, spawned as subprocess)    │ │
│  │                                                                │ │
│  │  HTTP :8080  →  overlay/index.html  (OBS browser source)       │ │
│  │  HTTP :8080  →  overlay/edit.html   (legacy editor, kept)      │ │
│  │  WS   :8787  →  MIDI/NHL events → overlay                      │ │
│  │  REST :8080  →  /api/controls, /api/suggest, /api/refit        │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

> **Why the shell is bare:** the first scaffold shipped **both** a native `NavigationView`
> *and* a React sidebar, which rendered as a **double sidebar**. The shell was reduced to a
> window + `WebView2` (see `app/MainWindow.xaml`), and the React app became the single owner of
> navigation and chrome.

## 2. Component Breakdown

### 2.1 Native shell (C# / .NET 10 / WinUI 3)

**Responsibilities:**
- Single native window hosting one **WebView2** — the shell owns the window plus service
  plumbing only. It has **no native navigation/chrome**; the React app owns the sidebar, logo
  and routing (see the note under the diagram above).
- Dependency detection (registry + filesystem probes; no WMI)
- loopMIDI install (artifact-gated download + SHA-256 verify) and port provisioning
  (HKCU registry value + `loopMIDI.exe` restart)
- Traktor out-port + out-mapping injection (surgical TSI edit; see §5.1)
- Python sidecar lifecycle (install on first run, start, monitor, restart, stop)
- WebView2 ↔ C# IPC bridge (via `window.chrome.webview`)
- Application state persistence (`midimat.config.json`)
- **System tray icon** (`H.NotifyIcon.WinUI`, `TaskbarIcon` in `MainWindow.xaml`) —
  close-to-tray (the sidecar must outlive the window), left-click reopens, context menu =
  Show / Open overlay in browser / Quit. Image from `Assets\MidiMAT.ico`, generated from
  `ui/public/midimat-logo.svg`.
- **Not yet implemented:** auto-start on Windows login (later task)

**Key files (new):**
```
app/
├── MidiMAT.csproj              # net10.0-windows, WinUI 3, x64, unpackaged
├── app.manifest                # PerMonitorV2 DPI; asInvoker
├── App.xaml / App.xaml.cs      # Application entry point
├── MainWindow.xaml             # ONE <WebView2/> — no native chrome
├── MainWindow.xaml.cs          # Boots WebView2, wires IPC, runs probes, supervises sidecar
├── Services/
│   ├── DependencyChecker.cs    # Registry/file probes: loopMIDI, Traktor, OBS, WebView2
│   ├── LoopMidiInstaller.cs    # Download+verify install, provision port (HKCU), restart
│   ├── TraktorConfig.cs        # Newest TSI finder; DDPT out-port + CMAI/DCBM injection
│   ├── ObsDetector.cs          # Locates OBS Studio / Streamlabs; Browser Source guide
│   ├── SidecarManager.cs       # Launch/monitor/restart the sidecar
│   ├── SidecarExtractor.cs     # Install the bundled sidecar\ payload to %LOCALAPPDATA%
│   ├── SetupService.cs         # Runs the six wizard steps; raises setup:progress
│   ├── ConfigStore.cs          # Read/write midimat.config.json (atomic)
│   └── IpcBridge.cs            # WebView2 ↔ C# message passing
├── Resources/
│   └── ui/                     # Built React app (Vite outDir); globbed by the .csproj
│       ├── index.html
│       ├── midimat-logo.svg
│       └── assets/…
└── Assets/
    ├── MidiMAT.ico             # Tray icon + <ApplicationIcon> (16–256)
    └── MidiMAT-icon-1024.png   # 1024² master raster the .ico is built from
```

The PyInstaller sidecar bundle travels in the publish output as `sidecar/` next to
`MidiMAT.exe` (see §7); `SidecarExtractor` copies it to
`%LOCALAPPDATA%\MidiMAT\sidecar\` on first run.

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
- Tailwind CSS 4 (CSS-first `@theme` oklch tokens in `src/styles/globals.css`; no `tailwind.config.ts`)
- Vite 8 (bundler; relative `base: "./"` for the WebView2 virtual host)
- shadcn-style primitives (`components/ui/{button,switch}.tsx`, built on Radix) plus MidiMAT's
  own `components/midimat/*` — the earlier "Aceternity UI (Evervault/Wobble Card)" plan was dropped
- Framer Motion 14 (page transitions, micro-animations; `prefers-reduced-motion` aware)
- lucide-react icons
- Inter + JetBrains Mono shipped **offline** via `@fontsource/*` (imported in `main.tsx`) —
  not a CDN and not `public/fonts/`
- `@` → `src` import alias (declared in both `vite.config.ts` and `tsconfig.json`)

**Key files (new):**
```
ui/
├── package.json
├── vite.config.ts              # base "./", outDir ../app/Resources/ui, "@" → src alias
├── tsconfig.json               # "@/*" → "src/*"
├── index.html                  # Entry point loaded by WebView2
├── public/
│   └── midimat-logo.svg        # Approved knob-mark logo
└── src/
    ├── main.tsx                # React root + @fontsource imports
    ├── App.tsx                 # Nav + host messages (deps/log/config) + page transitions
    ├── components/
    │   ├── layout/
    │   │   └── PageTransition.tsx    # Framer Motion wrapper
    │   ├── midimat/
    │   │   ├── app-shell.tsx         # Sidebar + scrollable content shell
    │   │   ├── app-sidebar.tsx       # 5 nav entries + footer (Support, Settings)
    │   │   ├── midimat-logo.tsx      # Knob logo glyph + wordmark
    │   │   ├── server-log.tsx        # Live log pane
    │   │   ├── server-status-card.tsx# Server URL/uptime/events + buttons
    │   │   ├── setup-card.tsx        # Component status card
    │   │   ├── status-dot.tsx        # Status indicator
    │   │   └── switch-row.tsx        # Toggle row (Radix Switch)
    │   ├── setup/
    │   │   ├── SetupWizard.tsx       # 6-step wizard (full-screen overlay)
    │   │   ├── setup-wizard-context.tsx
    │   │   ├── setup-step-card.tsx
    │   │   ├── wizard-steps.ts       # Step metadata + ids
    │   │   ├── step-status.ts
    │   │   ├── StepLoopMidi.tsx
    │   │   ├── StepTraktor.tsx
    │   │   ├── StepRuntime.tsx
    │   │   ├── StepServer.tsx
    │   │   ├── StepObs.tsx
    │   │   ├── StepSave.tsx
    │   │   └── types.ts
    │   └── ui/
    │       ├── button.tsx            # shadcn-style button (Radix Slot + cva)
    │       └── switch.tsx            # shadcn-style switch (Radix)
    ├── hooks/
    │   └── usePrefersReducedMotion.ts
    ├── lib/
    │   ├── ipc.ts              # Typed IPC protocol (mirrors IpcBridge.cs)
    │   ├── constants.ts        # Ports, URLs, repo/donate links
    │   ├── navigation.tsx      # NavContext (page tags)
    │   ├── status-context.tsx  # App-level log + config context (consumed by Status)
    │   └── utils.ts            # cn() class merge
    ├── screens/
    │   ├── index.ts            # PAGES registry (title/subtitle/component)
    │   ├── SetupSummary.tsx
    │   ├── Status.tsx
    │   ├── Editor.tsx
    │   ├── MapDevice.tsx
    │   └── Help.tsx
    └── styles/
        └── globals.css         # Tailwind 4 @theme tokens + utilities
```

### 2.3 Python Sidecar (existing, bundled via PyInstaller)

**No major changes needed.** The existing `sidecar/server.py` already provides:
- HTTP static server (overlay + editor)
- WebSocket broadcaster (MIDI events)
- REST API (`/api/controls`, `/api/suggest`, `/api/refit`)
- MIDI tap + NHL tap + mapping resolver

**Additions — what actually shipped (the sidecar itself is unchanged):**

- `server.py` accepts only `--http-port`, `--ws-port`, `--no-demo`, `--midi`,
  `--midi-ports`, `--nhl`, `--config`. The shell streams its **stdout/stderr line by line**
  to the UI as `server:log`; the level is parsed out of the text because Python's `logging`
  writes INFO to stderr too ("came from stderr" ≠ "is an error").
- Health/status is **pushed, not polled**: the shell builds a `deps:status` snapshot from
  `DependencyChecker` + `SidecarManager.State` and posts it over IPC whenever either changes.
- **Not implemented:** a `--managed` flag and a `GET /api/health` endpoint. Both were planned
  here; passing `--managed` today would make argparse exit, which is exactly why
  `SidecarManager.PassManagedFlag` is hard-coded `false` (§4, step 4).

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
- ~~`GET http://127.0.0.1:8080/api/health`~~ — **not implemented**; health is pushed to the UI as `deps:status` instead (§3.3)

### 3.3 C# -> Python (stdout parsing + process management)

C# spawns the sidecar and reads its stdout:
```
[SidecarManager] spawns: midimat-server.exe --http-port 8080 --ws-port 8787 --midi [--nhl] [--no-demo]
[SidecarManager] reads stdout line by line:
  → 14:32:01.234 INFO  sidecar.server | overlay: http://127.0.0.1:8080/...
  → 14:32:01.456 INFO  sidecar.server | WebSocket ready on ws://127.0.0.1:8787
  → 14:32:05.789 INFO  sidecar.midi_tap | midi| connected: TRAKTOR X1 MK3
[SidecarManager] forwards to React as server:log messages
[SidecarManager] pushes deps:status whenever StateChanged fires (no HTTP health polling)
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
| **1. loopMIDI** | Check installed (`HKCU`/`HKLM` `SOFTWARE\Tobias Erichsen`, `…\loopMIDI`, or the `Uninstall\loopMIDI` entry). Ports are **DWORD values under `HKCU\SOFTWARE\Tobias Erichsen\loopMIDI\Ports`** (`<PortName> = 1`). The older `HKLM\SOFTWARE\TOBIAS-ERICHSEN\loopMIDI` key **does not exist**; the driver lives at `HKLM\SOFTWARE\Tobias Erichsen\teVirtualMIDI64`. | **Download** the vendor archive from **tobias-erichsen.de** (pinned: `…/2020/01/loopMIDISetup_1_0_16_27.zip`, SHA-256 `975399eb…4e0d5`), verify the hash, extract, and run the `.exe` with `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART` (a UAC prompt; the app itself stays `asInvoker`). **Do not redistribute** the installer — download at setup time. Then write the port value (**HKCU — no admin needed**) and **restart `loopMIDI.exe`**: the registry change does nothing until the process re-reads it at startup. Liveness is verified by enumerating Win32 `midiOutGetDeviceCaps` (the native shell cannot use `mido`). Expected archive: ~7.9 MB (a single `loopMIDISetup.exe`). |
| **2. Traktor** | Scan `<Documents \| OneDrive\Documents>\Native Instruments\Traktor*\Traktor Settings.tsi`, taking the **newest** file across all `Traktor*` version folders (picking the first folder alphabetically reported an ancient Traktor 3.10 on a machine running 4.5). | **Primary (proven):** surgically edit the existing `Generic MIDI` device — set its **out-port** (`DDPT`) to the shipped port name **`MidiMAT`**, and inject the out-mappings (`CMAI` + `DCBM`) — see §5.1; both operations live in `app/Services/TraktorConfig.cs`. **Fallback:** if the file is absent/locked, guide a manual import. Never overwrite the whole settings file; a hard guard refuses any write while a `Traktor*` process is running. |
| **3. Python** | Not needed — the bundled PyInstaller sidecar embeds Python | Show info card: "Python runtime is embedded in the sidecar. No installation required." Expected disk: already included. |
| **4. Server** | Start the bundled sidecar (`midimat-server.exe --http-port 8080 --ws-port 8787 --midi`, plus `--nhl` when NHL mode is on and `--no-demo` when demo mode is off — see `SidecarManager.BuildArguments`; `--managed` is **not** passed, because `server.py` does not accept it). | Show live status card with server URL, WebSocket status, first log lines. "Starting..." → "Running ✓". Expected disk: installed to `%LOCALAPPDATA%\MidiMAT\sidecar\`. |
| **5. OBS** | Check registry `HKLM\SOFTWARE\OBS Studio` + common paths | **If found:** Show Browser Source config card with visual guide (screenshots of OBS source properties, URL to paste: `http://127.0.0.1:8080/overlay/index.html`). **If not found:** "OBS not detected. [Download OBS](https://obsproject.com) — wait for install, then click Re-check." |
| **6. Save** | Write `midimat.config.json` with all detected paths + `skip_checks: true` | Summary card: "All set! Next launch will skip checks." Toggle: "Always check on startup" (off by default). |

### Expected Disk Space (shown in wizard)

| Component | Size |
|-----------|------|
| `MidiMAT.exe` (single file; self-contained .NET + Windows App SDK) | ~148 MB |
| Python sidecar (installed to `%LOCALAPPDATA%\MidiMAT\sidecar\`) | ~138 MB |
| YOLO model (`models/traktor_yolo.pt`, inside the sidecar) | ~5 MB |
| Overlay assets (inside the sidecar) | ~1 MB |
| loopMIDI (if installed) | ~8 MB |
| **Total installed footprint** | **~295 MB** |

## 5. Traktor configuration

### 5.1. Surgical TSI injection (PROVEN 2026-11-09)

The wizard does **not** overwrite the user's Traktor settings. It injects only the
MidiMAT out-mappings into the existing `Generic MIDI` device.

**Format:** `Traktor Settings.tsi` is XML that holds **two** `DeviceIO.Config.*` entries —
`.Controller` and `.Keyboard`. The device tree lives in the **first** one (`.Controller`), and
that is the only one the writer ever patches. Its `Value` is a base64 TLV tree:
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
   The CMAD is the **knob field layout with `ControlType` patched to `0xFFFF`**
   (`ValueType=2`, `MaxOutput=1.0`, `OutputScale=0.0625`): a **120-byte** payload (30 × u32 BE),
   so each `CMAI` entry is **140 bytes** (12-byte header + 8-byte `CMAD` tag/length + 120).
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
  user to close it before writing. `TraktorConfig` enforces this as a **hard guard**: every
  writer (`SetOutPort`, `InjectMappings`) returns an error while any `Traktor*` process is
  running, before it touches the file.

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
    "traktor_tsi": "C:\\Users\\jaros\\OneDrive\\Documents\\Native Instruments\\Traktor 4.5.1\\Traktor Settings.tsi",
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

`paths.traktor_tsi` is filled in by the finder, not typed by the user: it scans
`<Documents | OneDrive\Documents>\Native Instruments\Traktor*` and picks the **newest**
`Traktor Settings.tsi` across all version folders. (Picking the first folder alphabetically
reported an ancient Traktor 3.10 on a machine that actually runs 4.5.)

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
Developer machine                                  Output
─────────────────                                  ──────

┌─────────────────┐
│ ui/             │ ──→ npm run build ──→ app/Resources/ui/  (React SPA; Vite outDir)
│ (React+Vite)    │     emptyOutDir wipes it first, then re-creates .gitkeep
└─────────────────┘

┌─────────────────┐
│ sidecar/        │ ──→ PyInstaller ──→ build/dist/midimat-server/  (onedir, ~138 MB)
│ (Python)        │     build/midimat-server.spec
└─────────────────┘

┌─────────────────┐
│ app/            │ ──→ dotnet publish ──→ dist/MidiMAT.exe  (~148 MB, single file)
│ (C# WinUI 3)    │     -r win-x64 -p:Platform=x64 -p:PublishSingleFile=true
│                 │     -p:SelfContained=true -p:EnableMsixTooling=true
│  payload:       │     -p:IncludeNativeLibrariesForSelfExtract=true
│  • Resources/ui/│     -p:EnableCompressionInSingleFile=true
│  • sidecar/     │
└─────────────────┘
```

### Build commands (final)

```powershell
# 1. Build the React UI (outputs straight into app/Resources/ui)
npm --prefix ui ci
npm --prefix ui run build

# 2. Build the Python sidecar (onedir)
python -m PyInstaller build/midimat-server.spec --noconfirm --clean
#   → build/dist/midimat-server/   (onedir, ~138 MB; the OpenCV cv2 payload dominates)

# 3. Build the single-file EXE
#    EnableMsixTooling=true is REQUIRED: PublishSingleFile on an unpackaged WinUI 3
#    app errors out without it. The app stays unpackaged (WindowsPackageType=None);
#    this only satisfies the SDK.
dotnet publish app\MidiMAT.csproj -c Release -r win-x64 `
  -p:Platform=x64 `
  -p:PublishSingleFile=true `
  -p:SelfContained=true `
  -p:EnableMsixTooling=true `
  -p:IncludeNativeLibrariesForSelfExtract=true `
  -p:EnableCompressionInSingleFile=true `
  -o dist
#   → dist/MidiMAT.exe   (~148 MB single file)
#   → dist/sidecar/      (the PyInstaller bundle, when it exists at publish time)
```

### How the sidecar reaches a user machine

The published `dist/` carries the PyInstaller bundle **as `sidecar/` next to `MidiMAT.exe`**
(`MidiMAT.csproj` globs `..\build\dist\midimat-server\**\*` into `sidecar\` when that folder
exists). On first run `MainWindow` calls `SidecarExtractor.EnsureInstalled()`, which copies the
payload to `%LOCALAPPDATA%\MidiMAT\sidecar\` (skipping the copy when the `.bundle-version`
stamp already matches). `SidecarManager.ResolveSidecarLaunch` checks that installed path
**first**, then a repo-local `build\midimat-server.exe`, then the venv's `python sidecar\server.py`
(dev) — so the shipped app never needs a repo checkout after the first run.

**Trap (cost a debugging session):** in a single-file app, `AppContext.BaseDirectory` can point
at the native-library **extraction dir**, not the folder holding `MidiMAT.exe`. Resolving the
app's own location must go through `Environment.ProcessPath` — `SidecarManager.FindRepoRoot`
does exactly that (it still also tries `AppContext.BaseDirectory`, since `SidecarExtractor`
reads the `sidecar\` payload from the base directory).

Note: the app no longer embeds `midimat-server.exe`/`overlay/` as resources, and it does **not**
bundle a loopMIDI installer or a `.tsi` — loopMIDI is downloaded+verified at setup, and Traktor
is edited surgically (see §2.1 and §4).

## 8. Screen Designs (Summary)

### 8.1 Setup Summary (default screen after setup)

```
┌──────────────┬──────────────────────────────────────────────┐
│              │                                               │
│  [knob logo] │  SETUP SUMMARY                                │
│              │                                               │
│ ──────────── │  ┌─────────────┐  ┌─────────────┐            │
│ ● Setup      │  │ loopMIDI    │  │ Traktor     │            │
│   Summary    │  │  ✓ Installed│  │  ✓ Configured│            │
│   Status     │  │  Port: MidiM│  │  settings file│           │
│   Editor     │  └─────────────┘  └─────────────┘            │
│   Map New    │                                               │
│   Device     │  ┌─────────────┐  ┌─────────────┐            │
│   Help       │  │ Server      │  │ OBS         │            │
│              │  │  ● Running  │  │  ✓ Detected │            │
│ ──────────── │  │  :8080/:8787│  │  Brow. Src  │            │
│   Support    │  └─────────────┘  └─────────────┘            │
│   Settings   │                                               │
│              │  [Re-run setup]   [Open overlay URL]          │
└──────────────┴──────────────────────────────────────────────┘
```

Sidebar: five entries — **Setup Summary, Status, Editor, Map New Device, Help** — plus a
footer with **Support** (opens the donate link) and **Settings** (a v1 no-op). The logo is the
approved **knob mark** (`ui/public/midimat-logo.svg`, drawn by
`components/midimat/midimat-logo.tsx`); the earlier "logo variant B" placeholder is superseded.

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

**Status screen notes:** the shell streams `deps:status` and `server:log` (and posts
`config:loaded`) from startup, before screens mount. Both are lifted into `App.tsx` state —
`deps` directly, and the log plus the last config snapshot via a `StatusContext` — because a
screen that only subscribed on mount would miss everything posted earlier (the original
late-mount bug left the wizard showing "not detected"). The Status screen reads the log and the
server flags from that context rather than subscribing itself; the log starts empty (no mock rows).

## 9. Technology Choices

Versions actually installed / pinned in this build:

| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| Desktop shell | Windows App SDK (WinUI 3) | 2.6.5 | Native Windows; unpackaged, runtime self-contained |
| Tray / taskbar icon | H.NotifyIcon.WinUI | 2.4.1 | Pure WinUI `TaskbarIcon` (no WinForms `NotifyIcon`); menu via `ContextFlyout` |
| Runtime | .NET | 10 (`net10.0-windows10.0.26100.0`) | Single-file publish |
| Web runtime | WebView2 SDK | 1.0.4314.35 | Evergreen Chromium; `CoreWebView2` APIs |
| Management UI | React | 19 | — |
| Styling | Tailwind CSS | 4 | CSS-first `@theme` tokens (no config file) |
| Animations | Framer Motion | 14 | Page transitions, micro-interactions |
| Bundler | Vite | 8 | Fast HMR, optimized builds |
| Python bundle | PyInstaller | 6.22 | onedir Python executable |
| Python runtime | CPython | 3.14 | Embedded in the PyInstaller bundle |
| Packaging | .NET single-file | — | No separate installer needed |

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
| `sidecar/server.py` | Standalone | Bundled in EXE | **No changes** — only bundled (`None` in the csproj). `--managed` / `/api/health` were planned but never added (§3) |
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
- .NET 10 SDK (the TFM is `net10.0-windows10.0.26100.0`)
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

# Terminal 3: Start the WinUI 3 app (serves the built bundle; see app/README for the dev-server tip)
cd app && dotnet run
```
