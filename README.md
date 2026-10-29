# MidiMAT

**MIDI-driven visual highlight overlay for DJ streams.** A sidecar app reads MIDI input
(e.g. Native Instruments Traktor Kontrol X1 mk3 over USB), resolves which Traktor function
the signal controls, and draws a glowing outline around that function's on-screen widget —
composited into your OBS recording in near real time (< 50 ms).

```
X1 mk3 ──USB──▶ sidecar (MIDI → function → screen coords) ──WebSocket──▶ overlay ──▶ OBS Browser Source
                                                                          (glow + label)
```

## Why no vision model in the hot path?

Two sub-problems hide in this idea:

1. **"What function does this MIDI signal control?"** — deterministic: Traktor's mapping is
   exportable **TSI XML**. Parse once → lookup table.
2. **"Where is that widget on screen?"** — static layout. Solved once (calibration /
   OpenCV template match / optional vision-grounding model at startup), then cached.

A vision model is used only as a **bootstrapper** (auto-calibration), never per-frame —
that keeps latency at ~50 ms instead of 200–1000 ms.

## Phases

| Phase | Goal | Status |
|---|---|---|
| **0** | Prove the visual idea: preset coordinates + fake events + glowing overlay in OBS | ✅ scaffolded |
| **1** | Real MIDI + TSI parser + manual calibration tool | ⬜ |
| **2** | Robustness: OpenCV template matching, X1 page states, per-deck colors, decay polish | ⬜ |
| **3** | Vision auto-calibration (Grounding DINO / Qwen2-VL) on startup & page change | ⬜ |

## Quick start (Phase 0)

### Option A — static demo (no server, 10 seconds)

Open `overlay/index.html?demo=1` in a browser — widgets auto-glow in sequence.
Click a widget to pulse it, `Space` pauses the demo.

### Option B — with sidecar server (the real plumbing)

```powershell
.\scripts\run.ps1
```

This creates `.venv`, installs deps, and starts:

- **HTTP** `http://127.0.0.1:8080/overlay/index.html` — the overlay page
- **WebSocket** `ws://127.0.0.1:8787` — fake MIDI event stream (demo generator)

The console logs every event (timestamped), so you can watch latency while testing.

### OBS setup

1. Add a **Window Capture** (Traktor) or **Display Capture** source; crop to the Traktor window.
2. Add a **Browser Source** on top:
   - URL: `http://127.0.0.1:8080/overlay/index.html?debug=1` (drop `debug` once happy)
   - Width/Height: match your canvas (default layout is 1920×1080)
   - ☑ *Refresh browser when scene becomes active*
   - ☐ *Shutdown source when not visible* (leave off)
3. Make the sidecar's screen region (Phase 1+) identical to OBS's crop rectangle.

The overlay background is transparent and click-through in OBS; glows composite over the capture.

## Repository layout

```
MidiMAT/
├── README.md               ← this file
├── docs/ARCHITECTURE.md    ← full design: components, data flow, latency, open questions
├── layout.json             ← widget boxes, colors, glow tuning (the "calibration profile")
├── requirements.txt        ← sidecar deps (websockets now; MIDI/CV deps land in phase 1)
├── sidecar/server.py       ← HTTP static + WebSocket broadcaster + demo event generator
├── overlay/
│   ├── index.html          ← OBS browser source page (transparent canvas)
│   ├── overlay.js          ← WS client, glow renderer, built-in demo mode
│   └── style.css
└── scripts/run.ps1         ← venv bootstrap + launch
```

## Hardware note (verify in Phase 1)

Does the **X1 mk3 expose a class-compliant MIDI input** to the OS, or does it speak HID
directly to Traktor only? Check your OS MIDI device list, or run:

```powershell
.venv\Scripts\python -c "import mido; print(mido.get_input_names())"
```

If it's HID-only, options: a virtual `loopMIDI` port bridged by a small HID reader.

## Stack

- **Sidecar:** Python — `websockets` (now), `python-rtmidi`/`mido`, `opencv-python`, `mss`, `lxml` (phases 1–2)
- **Overlay:** plain HTML/JS/canvas → OBS Browser Source (no C++ OBS plugin needed)
- **Vision (optional, phase 3):** Grounding DINO / Qwen2-VL, bootstrapping only