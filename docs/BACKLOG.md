# MidiMAT — backlog / open questions

## Design rule (settled 2026-11-05)
Input = **Traktor out-mappings on loopMIDI**, assigned to a fixed **Deck A–D / FX Unit 1–4 /
Global** — never to "Device Target / Focus". Traktor reports *software* state, so:
- Z1 MK2 deck switch (left A↔C, right B↔D) needs **no tracking**: moving the left HI knob
  while switched to C makes Traktor send *Deck C › High Adjust*.
- Two X1 MK3s (left unit = decks A/C, right unit = B/D, chosen at Traktor start) need **no
  identity handling**: they drive FX Units / deck functions, which is what we map.
- Side effect: mouse edits in Traktor glow too (fine for the stream).

## Open
- [ ] **Deck C/D on screen**: run wizard `--profile z1cd`, then add x,y,w,h for the C/D
      channel strips in `mapping/controls.csv` (Traktor 4-deck mixer shows all four).
- [ ] **Remix deck (D, Kontrol F1)**: decide what to show — F1 sends Remix Deck controls
      (`Remix Deck > Slot …`), not Track Deck ones; add a profile when needed.
- [ ] **Mixer FX selector values → names**: `z1_mfx_sel` sends one CC whose value says which
      FX (1–4 / Filter) is chosen; HUD should print the FX name instead of a %.
- [ ] **Button events in HUD**: show ON/OFF instead of 0/100 % for toggles (cue, FX on, sync…).
- [ ] **Which hardware moved it** (optional, "X1 left" badge): would need the NHL/MIDI
      device tap again; not needed for viewers — park.
- [ ] Cleanup: park `nhl_tap` live mode, `vision_snap`, `calibrate`, stray tracked logs.
