# MidiMAT — backlog / open questions

> Refreshed 2026-11-25 (repo audit, `main` @ `9c8e8aa`). See `docs/obsidian/MidiMAT - Backlog.md`
> for the mirrored vault copy and `docs/DESIGN_APP.md` for the shipped shell.

## Design rule (settled 2026-11-05)
Input = **Traktor out-mappings on loopMIDI**, assigned to a fixed **Deck A–D / FX Unit 1–4 /
Global** — never to "Device Target / Focus". Traktor reports *software* state, so:
- Z1 MK2 deck switch (left A↔C, right B↔D) needs **no tracking**: moving the left HI knob
  while switched to C makes Traktor send *Deck C › High Adjust*.
- Two X1 MK3s (left unit = decks A/C, right unit = B/D, chosen at Traktor start) need **no
  identity handling**: they drive FX Units / deck functions, which is what we map.
- Side effect: mouse edits in Traktor glow too (fine for the stream).

## P0 — the app's core screens are still mockups (2026-11-25)
- [ ] **Editor screen** (`ui/src/screens/Editor.tsx`) prints *"Embedded editor placeholder"* →
      embed the sidecar-served `overlay/edit.html` in a WebView2 iframe; fall back to
      "Open in browser" if the sidecar is down.
- [ ] **Map New Device screen** (`ui/src/screens/MapDevice.tsx`) renders hard-coded
      `PLACEHOLDER_SIGNALS` → subscribe to the sidecar's live MIDI feed (ws://127.0.0.1:8787)
      and write the chosen channel/CC into `mapping/controls.csv`.
- [ ] Extend `ui/src/lib/ipc.ts` **and** `app/Services/IpcBridge.cs` in lockstep (the string
      literals are a 1:1 mirror — never rename on one side only).

## P0 — distribution
- [ ] `dist\MidiMAT.exe` is **stale**: built 04:31 on 2026-11-10 → has the tray, **not** the
      taskbar-icon fix (`d3169fc`). Republish.
- [ ] Ship **v0.1.0**: tag, GitHub release with the EXE attached, set versions in
      `app/MidiMAT.csproj` + `ui/package.json` (still `0.1.0`), update CHANGELOG.

## P1 — engineering hygiene
- [ ] **No CI**: `.github/` has templates only. Add GitHub Actions running pytest,
      `tsc --noEmit`, `vite build`, `dotnet build`.
- [ ] **No test runner**: `pytest` is not in `.venv`; the 5 `scripts/test_*.py` are hand-run
      scripts. Add `requirements-dev.txt` and convert them to pytest.
- [ ] `requirements.txt` still comments out Phase 2 (`opencv-python`, `numpy`) although both are
      installed in `.venv` — decide and align.

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

## Cleanup list (2026-11-25)
- [ ] Stray root artifacts: `server.err` (50 KB), `server.log`, `run_test.*`, `hid_test.log`,
      `nhl_*.jsonl`, `yolo11n.pt` (+ `.part`), `layout.json.bak`, `vision_detections.json`,
      `lovable_design.png`, `vision_preview.png` — gitignore / delete.
- [ ] Parked-but-shipped code: `sidecar/nhl_tap.py`, `sidecar/vision_snap.py`,
      `sidecar/calibrate.py` (superseded by the out-mapping decision of 2026-11-05).
- [ ] `models/traktor_yolo.pt` is gitignored ⇒ the trained detector is **not public**; decide
      whether to publish weights + the training dataset recipe (`scripts/train_yolo.py` needs
      `scripts/collect_screens.py` output).

