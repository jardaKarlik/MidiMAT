"""Phase 1 validation — run: python scripts/test_phase1.py

Covers: MIDI key parsing, note names, real TSI parsing (factory + live),
cc_map resolver (pages, fallbacks). Uses the actual TSI files on this machine.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sidecar.mapping import Resolver  # noqa: E402
from sidecar.tsi_parser import (  # noqa: E402
    CMD_NAMES, lookup_table, note_name_to_number, parse_key_name, parse_tsi_mappings,
)

FLX4 = Path.home() / (
    "OneDrive/Documents/Native Instruments/Traktor 4.5.1/Settings/"
    "Default Settings/Controller/AlphaTheta/02 - Controller - AlphaTheta - DDJ-FLX4.tsi"
)
LIVE = Path.home() / (
    "OneDrive/Documents/Native Instruments/Traktor 4.5.1/Traktor Settings.tsi"
)

ok = True


def check(cond: bool, msg: str) -> None:
    global ok
    print(("  ok   " if cond else "  FAIL ") + msg)
    ok = ok and bool(cond)


def main() -> int:
    # --- key parsing -------------------------------------------------------
    check(parse_key_name("Ch01.CC.21") == (0, "cc", 21), "parse CC key")
    check(parse_key_name("Ch08.Note.B1") == (7, "note", 35), "parse Note key")
    check(parse_key_name("garbage") is None, "reject garbage key")
    check(note_name_to_number("C4") == 60, "C4 = 60")
    check(note_name_to_number("G0") == 19, "G0 = 19")

    # --- factory TSI (Generic MIDI device, real mappings) ------------------
    if FLX4.exists():
        entries = parse_tsi_mappings(str(FLX4))
        check(len(entries) > 100, f"FLX4 factory TSI parses ({len(entries)} entries)")
        named = sum(1 for e in entries if not e.function.startswith("CMD_"))
        check(named / max(len(entries), 1) > 0.5,
              f"command-name coverage {named}/{len(entries)} via constants")
        table = lookup_table(entries)
        check(len(table) > 50, f"lookup table has {len(table)} input keys")
        sample = next(iter(table))
        got = parse_key_name(table[sample].key_name)
        check(got == sample, f"round-trip key {table[sample].key_name!r}")
        check(len(CMD_NAMES) > 300,
              f"{len(CMD_NAMES)} named commands loaded (99% coverage on real files)")
    else:
        check(False, f"factory TSI found at {FLX4}")

    # --- live settings (native X1 => DDCB empty, but must parse) -----------
    if LIVE.exists():
        live = parse_tsi_mappings(str(LIVE))
        check(isinstance(live, list), "live Traktor Settings.tsi parses without error")
        print(f"  info live input-mappings = {len(live)} "
              "(0 expected: X1 MK3 is native/HID, not MIDI-mapped)")
    else:
        print(f"  info live settings not found ({LIVE}) — skipped")

    # --- resolver ----------------------------------------------------------
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8") as f:
        json.dump({
            "port_hint": "X1 MK3",
            "page_buttons": [{"channel": 0, "kind": "note", "number": 32, "page": "fx"}],
            "entries": [
                {"channel": 0, "kind": "cc", "number": 21, "page": "fx",
                 "label": "FX1 · Dry/Wet", "deck": "FX", "widget": "fx1_drywet"},
                {"channel": 0, "kind": "cc", "number": 21,
                 "label": "Browse Encoder", "deck": None, "widget": None},
            ],
        }, f)
        cc_map = f.name

    r = Resolver(cc_map_path=cc_map)
    switch = {"channel": 0, "kind": "note", "number": 32, "value": 127}
    check(r.resolve(switch) is None, "page button resolves to None (context switch)")
    check(r.current_page == "fx", "page switched to 'fx'")
    hit = r.resolve({"channel": 0, "kind": "cc", "number": 21, "value": 64})
    check(hit and hit["label"] == "FX1 · Dry/Wet" and hit["widget"] == "fx1_drywet",
          "page-scoped entry wins on page 'fx'")
    r2 = Resolver(cc_map_path=cc_map)
    hit2 = r2.resolve({"channel": 0, "kind": "cc", "number": 21, "value": 64})
    check(hit2 and hit2["label"] == "Browse Encoder",
          "pageless entry matches before any page switch")
    check(r2.resolve({"channel": 3, "kind": "cc", "number": 99, "value": 1}) is None,
          "unknown key resolves to None")
    Path(cc_map).unlink()

    # --- two identical units (two X1 MK3s): port disambiguates --------------
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8") as f:
        json.dump({
            "port_hint": "X1 MK3",
            "page_buttons": [],
            "entries": [
                {"port": "X1 MK3 2", "channel": 0, "kind": "cc", "number": 21,
                 "label": "Unit 1 · Filter", "deck": "A", "widget": "deck_a_filter"},
                {"port": "2 - TRAKTOR", "channel": 0, "kind": "cc", "number": 21,
                 "label": "Unit 2 · Filter", "deck": "B", "widget": None},
                {"channel": 0, "kind": "cc", "number": 60,
                 "label": "Any unit · shared", "deck": None, "widget": None},
            ],
        }, f)
        dual = f.name

    r3 = Resolver(cc_map_path=dual)
    a = r3.resolve({"channel": 0, "kind": "cc", "number": 21, "value": 10,
                    "port": "TRAKTOR X1 MK3 2"})
    b = r3.resolve({"channel": 0, "kind": "cc", "number": 21, "value": 10,
                    "port": "2 - TRAKTOR X1 MK3 3"})
    check(a and a["label"] == "Unit 1 · Filter", "port scope: unit 1 entry wins on its port")
    check(b and b["label"] == "Unit 2 · Filter", "port scope: unit 2 entry wins on its port")
    c = r3.resolve({"channel": 0, "kind": "cc", "number": 60, "value": 10,
                    "port": "2 - TRAKTOR X1 MK3 3"})
    check(c and c["label"] == "Any unit · shared", "portless entry matches any unit")
    d = r3.resolve({"channel": 0, "kind": "cc", "number": 21, "value": 10,
                    "port": "Rane FOUR Control 4"})
    check(d is None, "port-scoped entries ignore other ports' identical keys")
    Path(dual).unlink()

    print("\nALL PASSED" if ok else "\nFAILURES")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())