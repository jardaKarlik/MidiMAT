# MidiMAT — Phase 1: real MIDI + semantics + calibration

> Status: **scaffolded** (2026-10-29). Goal: X1 knob turn → correct widget glows +
> correct description in the HUD card.

## Research findings (this machine, verified)

1. **The X1 MK3 exposes class-compliant MIDI**: ports `TRAKTOR X1 MK3` / `2 - TRAKTOR
   X1 MK3` are visible to `mido` (also present: F1, Z1 MK2, Rane FOUR). ✅ hardware OK
2. **TSI format cracked**: XML `DeviceIO.Config` entry → base64 TLV. Source MIDI key
   lives in `DCBM` as strings (`Ch01.CC.21`, `Ch08.Note.B1`); `CMAI` carries
   `cmd_id`; `traktor_tsi.constants` maps 497 cmd ids → names. Verified against the
   factory **DDJ-FLX4** TSI (213 real mappings) and the live settings file.
3. **X1 MK3 is a NATIVE device in Traktor** — its entry in `Traktor Settings.tsi` has
   control *definitions* (DDDC: "Mode Button", …) but **zero DDCB MIDI mappings**
   (Traktor talks HID). ⇒ For the X1 the semantic source of truth is the empirical
   **`cc_map.json`**, not a TSI export. TSI parsing still serves Generic-MIDI gear
   and any custom mappings the user adds in Controller Manager.

## Components (all scaffolded)

| Module | Role | Run |
|---|---|---|
| `sidecar/midi_tap.py` | list ports · watch/record live MIDI · background listener for the server | `python -m sidecar.midi_tap watch --port "X1 MK3"` |
| `sidecar/tsi_parser.py` | TSI → `MappingEntry` list / lookup table (key → function) | `python -m sidecar.tsi_parser file.tsi` |
| `sidecar/mapping.py` | Resolver: cc_map (pages) > TSI fallback → `{label, deck, widget}` | used by server |
| `sidecar/calibrate.py` | hover-and-capture widget boxes + OBS crop origin → `layout.json` | `python -m sidecar.calibrate` |
| `sidecar/server.py` | `--midi [SUBSTR]` starts the tap; events emit `label`/`deck` | `scripts\run.ps1 --midi` |
| `cc_map.json` / `midimat.config.json` | learned key→control table / paths | edit by hand or from watch output |

Overlay: now supports **HUD-only events** (description card without a glow box) so a
mapped-but-not-yet-calibrated control still tells the viewer what's happening.

## Two X1 MK3 units (user owns TWO — identity matters!)

- Two physical units ⇒ two MIDI ports: `TRAKTOR X1 MK3 2` and `2 - TRAKTOR X1 MK3 3`
  (and two `Traktor.Kontrol X1MK3` DEVI entries in `Traktor Settings.tsi` — same thing
  from the Traktor side). **Never dedupe by model name.**
- `midi_tap watch` opens **ALL** matching ports and prefixes every message with its
  `[port]` — wiggle a knob on one unit to learn which port it is.
- Control identity = **(port, channel, kind, number)**. In `cc_map.json`, give an entry
  an optional `"port"` substring to scope it to one unit (recommended: the same knobs on
  both units often map to different decks/FX), or omit `port` to match any unit.
- Server/`--midi` uses the same rule — `msg.port` flows through the resolver.

## Bring-up checklist (acceptance for Phase 1)

- [ ] `python -m sidecar.midi_tap list` → X1 ports visible
- [ ] `watch --port "X1 MK3"` **with Traktor open** → moving a knob prints `ch/#/val`
      (the one open hardware question: does X1 send MIDI while Traktor claims HID?)
- [ ] Fill `cc_map.json` for the controls you care about (label + widget id)
- [ ] `python -m sidecar.calibrate` → boxes match the real Traktor GUI (Extended layout)
- [ ] `scripts\run.ps1 --midi --no-demo` → turn a knob → **glow + HUD card**, <100 ms
- [ ] Page switching: register X1 page buttons in `page_buttons` if its pages reuse CCs

## Notes / gotchas

- `note_name_to_number` assumes **C4 = 60** — confirm against live traffic (watch
  prints numbers; compare with a known note).
- Coordinates: `calibrate.py` sets DPI awareness before `GetCursorPos` so scaled
  displays don't lie; boxes are stored **relative to the OBS crop origin**.
- If Traktor must be closed for the X1 to send MIDI on the class-compliant port,
  fallback = add a mirror MIDI mapping in Traktor's Controller Manager (Phase 1
  contingency) or use a second X1 page — decide after the watch test.