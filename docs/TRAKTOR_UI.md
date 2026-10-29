# Traktor Pro UI — zone map (reference for MidiMAT overlay)

Source: official NI Traktor Pro manual, *Traktor Overview* page — annotated screenshot
saved at `docs/traktor-ui/uuid-08cd423b-c601-ec4d-ede9-d0818f953a47.jpg`
([online manual](https://docs.native-instruments.com/online-guides/traktor-pro-manual/en/traktor-overview)).
Shows the **Extended** layout (the default full view). *(as of Traktor Pro 4 / manual 2024)*

## Vertical zone map (top → bottom)

| Zone | Content | X1 mk3 relevance |
|---|---|---|
| **Header** (~40 px) | TRAKTOR logo, layout dropdown (Essential/Extended/Browser/Mixer…), search, settings, master CPU meter, REC | low — thin strip, safe to overlap with a slim status element |
| **FX row** | **FX Unit 1** top-LEFT: D/W knob, 3 effect selectors (Delay/Reverb/Flanger), 3 effect knobs + ON buttons · center: SNAP/QUANT/LINK, BPM, AUTO/MASTER, MAIN knob, LIMITER · **FX Unit 2** top-RIGHT: D/W, FILTER/FEEDB/RATE knobs, RST/FRZ/SPR | **heavy** — X1's 4 encoder banks live here (per-deck FX pages) |
| **Decks row** | **Deck A** left (title/artist/time/BPM, SYNC, waveform, pitch fader, transport CUE/CUP/FLX/REV, loop size 2/4/8 + IN/OUT/ACTIVE), **Mixer** center (GAIN, HI/MID/LO, FLTR, FX 1/2 assign, KEY, channel faders, crossfader, cue, deck A/B/C/D), **Deck B** right (mirror of A) | **heavy** — loop, touch strip, deck switch, tempo |
| **Browser** (~bottom 40%) | tree left, playlist tabs, track list, status bar ("Ready…", song count) | browse encoder + load buttons |
| **Status bar** (very bottom) | "Ready…" + collection stats | candidate anchor strip |

## Key observations for the overlay

1. **Everything is dense and labeled already** — Traktor's own labels are tiny, static, and
   grey. A glow outline alone reads well; a text label *on top of* a control would cover
   neighboring controls (especially in the FX row and mixer where knobs sit ~40 px apart).
2. **Traktor only shows a value readout while the mouse drags a control** — MIDI input shows
   *no on-screen text at all*. This is exactly the gap MidiMAT fills: our HUD becomes the
   permanent "what is he touching" readout.
3. **Free screen real estate for a HUD:**
   - **Bottom center, floating over the browser** — a broadcast lower-third; viewers rarely
     need to read the track list. Best eye-flow (same place viewers look for song titles).
   - **Top band under the header** — always visible, but competes with the FX row.
   - **Right-edge vertical rail** — never collides with deck A/mixer, but asymmetric.
   - **Browser status bar line** — zero footprint (text only), but too small for a value bar.
4. **Widget boxes differ hugely in size**: FX knobs ≈ 40–60 px, loop buttons ≈ 30 px wide,
   faders are tall rectangles — the glow style (stroke + corner radius) must scale per box
   (`layout.json` already supports per-widget `box`; radius/stroke should scale with size).
5. **Layout variants matter**: Essential/Browser/Mixer/Parallel layouts move everything —
   `layout.json` profiles must be per-layout (Phase 1 calibration tool writes a named
   profile, e.g. `extended-1920x1080.json`).

## Description placement — decision (IMPLEMENTED)

**Chosen: bottom-center lower-third card over the browser zone** (user pick) — glow stays
on the control, ALL text lives in the card: deck/FX badge + function name + value % +
value bar. Implemented as `drawHud()` in `overlay/overlay.js`, configured via
`layout.json → hud` (enabled, ttl 1600 ms, width 640, height 88, margin 48 — slide-up +
fade in/out). Widget-level label pills were removed.

**Visual QA without OBS:** `overlay/index.html?shot=<widget_id>` renders a deterministic
still-frame (fixed glow + card) — used by headless-Edge screenshots during development.