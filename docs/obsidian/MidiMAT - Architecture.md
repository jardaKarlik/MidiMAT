---
tags: [project, midimat, traktor, obs]
created: 2026-11-05
status: active
repo: https://github.com/jardaKarlik/MidiMAT
---
# MidiMAT - Architecture
Back to [[MidiMAT]]

## Review verdict
- **Right:** OBS Browser Source overlay, WebSocket events, HUD card, no vision model in the hot path.
- **Wrong:** input via reverse-engineered NI HID (NHL) per device + parallel MIDI/TSI/vision-calibration paths. Hardware bytes can't tell what a control means *now* (FX assignment, shift, deck focus, Z1 deck switch).

## Pivot — ask Traktor
Generic MIDI device in Traktor, Out-Port = **loopMIDI**, out-mappings assigned to fixed **Deck A–D / FX Unit 1–4 / Global**. Traktor emits software state on every change, from any controller or the mouse.
- Z1 deck switch (A↔C, B↔D) → no tracking needed.
- Two X1 MK3 (left A/C, right B/D) → no device identity needed.

```
Traktor out-mappings → loopMIDI → sidecar (midi_tap → Resolver) → WS :8787 → overlay (OBS)
```

## Files
- `mapping/controls.csv` — single source of truth (id, physical, traktor_out, channel, cc, label, deck, shape, x/y/w/h, verified)
- `scripts/setup_wizard.py` — guided mapping + live CC verification
- `scripts/build_maps.py` — CSV → `cc_map.json` + `layout.json`
- `overlay/edit.html` — placer editor (sidecar `/api/controls`, live layout push)
- `overlay/overlay.js` — glow + HUD

## Glow
Additive halo, double bloom, ripple on fresh touch, brightness = activity. `?glow=N` / `glow.strength` (default 2). `?bg=` = preview over a screenshot (browser only).

## Shapes
circle = round knobs · rect = faders, crossfader, FX knobs 1–3 (Group-mode sliders), loop size, buttons · hud = card-only (Deck is Loaded, browser).

## Bug fixed
`midi_tap`: `getattr(msg, "control", msg.note)` evaluated `msg.note` eagerly → every CC raised inside the rtmidi thread and vanished.

## Future option
[ErikMinekus/traktor-api-client](https://github.com/ErikMinekus/traktor-api-client) — QML mod reading Traktor properties by name and POSTing JSON. Could replace loopMIDI + CC table. Caveats: reinstall after Traktor updates, Pro 4 unverified, port 8080 clash.
