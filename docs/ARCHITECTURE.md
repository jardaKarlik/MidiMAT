# MidiMAT — Architecture

> Captured at project start (Phase 0). Update this file as phases land.

## Goal

During a Traktor DJ set, every physical action on the controller (knob turn, button press,
fader move) produces a glowing outline around the corresponding widget in the Traktor GUI,
composited into the OBS stream recording — so viewers can *see* what the DJ is doing.

## Key design decision: deterministic fast path + one-time vision

The original idea was "a vision model consumes the video feed and recognizes which function
the MIDI signal controls." We split that into two sub-problems:

| Sub-problem | Solution | Frequency |
|---|---|---|
| Which function does this MIDI signal control? | Parse Traktor's **TSI mapping export (XML)** → CC → function name/deck/page | once (deterministic) |
| Where is that function's widget on screen? | Tier A: manual calibration · Tier B: OpenCV `matchTemplate` over ROIs · Tier C: vision grounding model | **once**, then cached |

**A vision model runs only as a bootstrapper** (startup / X1 page change / Traktor resize),
never per frame. This keeps end-to-end latency at ~50 ms instead of 200–1000 ms and avoids
GPU load during a live set.

## Components

```
┌─────────────┐  USB   ┌───────────────────────────────┐
│ Traktor X1  │───────▶│ sidecar (Python)              │
│ mk3         │        │  1. MIDI tap   (phase 1)      │
└─────────────┘        │  2. TSI parser (phase 1)      │
                       │  3. locator    (phase 2/3)    │
                       │  4. WebSocket broadcaster     │
                       └───────────┬───────────────────┘
                                   │ ws://127.0.0.1:8787
                                   ▼
┌──────────────────────────────────────────────────────┐
│ OBS scene                                            │
│  [L1] Window/Display Capture (Traktor, cropped)      │
│  [L2] Browser Source ← overlay/index.html            │
│       transparent canvas: glow outline + label +     │
│       value bar, 60 fps, decays ~600 ms after input  │
└──────────────────────────────────────────────────────┘
```

### 1. Sidecar — `sidecar/server.py`

- **Phase 0 (now):** serves the overlay statically (HTTP :8080), broadcasts *fake* MIDI
  events over WebSocket (:8787) from a demo generator; every event is timestamped and
  logged for latency watching.
- **Phase 1:** replaces the generator with `python-rtmidi`/`mido` input; adds TSI parsing
  (`<MidiKey>` → `<CtrlNMappedTo>` + deck + screen-set/page) and a calibration clicker tool.
- Emits `{type:"midi", id, value(0–127), function, deck, page, ts}`.

### 2. Overlay — `overlay/`

- Plain HTML/JS/canvas; **no OBS plugin** — OBS's built-in Browser Source renders it.
- Glow = rounded-rect stroke + `shadowBlur` bloom + label pill + thin value bar.
- Brightness ∝ CC value; fades over `glow.ttl_ms` (600 ms) after last event (hysteresis
  on ±1–2 value jitter prevents flicker).
- Deck colors: A `#33ccff`, B `#3dff9e`, FX `#ffcc33` (theme editable in `layout.json`).
- Built-in demo mode (`?demo=1`) works with zero server, for taste-testing the visual style.

### 3. Layout profile — `layout.json`

Widget boxes in **canvas coordinates** (1920×1080). Coordinates are stored relative to the
OBS crop rectangle so a window move only needs one recalibration (Phase 1 adds a
"click the four corners" tool). Named profiles support different Traktor skins/window sizes.

### 4. Vision bootstrapper (Phase 3, optional)

Grounding DINO / OWL-ViT / Qwen2-VL. Prompt = list of active mapped functions → bounding
boxes → written into `layout.json`. Triggered by startup or X1 page-change events.

## Latency budget (target < 50 ms total)

| Stage | Cost |
|---|---|
| MIDI device → OS | ~1 ms |
| sidecar resolve (dict lookup) | <1 ms |
| WebSocket hop | <1 ms |
| overlay redraw (next rAF frame) | ≤16 ms |
| OBS composites browser source | 1 frame |

## OBS integration (chosen approach)

Browser Source layer above the capture — chosen over `obs-websocket` scripting and C++
plugins because it needs **zero OBS plugin development** and CSS/canvas makes glow effects
trivial. `obs-websocket` remains a candidate for *scene switching* on X1 page changes later.

## Phases & acceptance criteria

- **Phase 0 — prove the visual idea** (demo): `?demo=1` glows are visible & tasteful in
  OBS at stream bitrate; WS round-trip observable in logs. ← *current*
- **Phase 1 — real MIDI + semantics:** X1 knob turns highlight the right widget; TSI export
  parsed; calibration tool writes `layout.json`.
- **Phase 2 — robustness:** survives window move/resize via template matching; X1 page
  states mapped; decay/intensity polished; value-mirroring mini-widgets.
- **Phase 3 — vision auto-cal:** zero-click re-calibration via grounding model.

## Open questions / risks

1. **Does the X1 mk3 expose class-compliant MIDI to the OS**, or HID-only to Traktor?
   (Test with `mido.get_input_names()` in Phase 1 — the one hardware unknown.)
2. **TSI XML schema details** — confirm exact element names across Traktor Pro 3/4 exports.
3. **Thin bright strokes vs. stream bitrate** — if outlines shimmer at low bitrate, go
   thicker + softer bloom (validate in Phase 0 at real stream settings).
4. **Coordinate drift** — OBS crop must equal the sidecar's grab region; corner-recalibration
   tool planned for Phase 1.

## Stack

Python 3.14 · `websockets` (now) · `mido`/`python-rtmidi`, `opencv-python`, `mss`, `lxml`
(phases 1–2) · HTML/JS canvas overlay · OBS Browser Source · `gh`-managed private GitHub repo.