---
tags: [project, midimat, traktor, obs]
created: 2026-11-05
status: active
repo: https://github.com/jardaKarlik/MidiMAT
---
# MidiMAT - Setup & Run
Back to [[MidiMAT]] · names: [[MidiMAT - Traktor Out-Mapping Names]]

## One-time
1. loopMIDI port; Traktor Controller Manager → Add… › Generic MIDI, In: None, **Out: loopMIDI**.
2. `python -m venv .venv` → `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`
3. OBS: Traktor capture + Browser Source `http://127.0.0.1:8080/overlay/index.html` with **identical** transform/bounding box.

## Map
`.\.venv\Scripts\python.exe scripts\setup_wizard.py --profile z1|z1cd|fx|decks|browser|all`
- `--list` progress · `--redo` · `--only <ids>` · `--fix-shapes`
- Skipped items reappear on the next run.

## Place
1. `.\scripts\run.ps1 --midi --no-demo`
2. OBS → Traktor source → *Screenshot (Source)*
3. `http://127.0.0.1:8080/overlay/edit.html` → paste screenshot → drag boxes
4. Ctrl+A + arrows = shift all · N = next · C = circle/rect · Ctrl+S = save + live push

## Diagnose
- `python -m sidecar.midi_tap list`
- `python -m sidecar.midi_tap watch --port loopMIDI --raw`
