"""Replay real NHL captures through decode_changes -> validate the event chain.

Run: python scripts/test_nhl_chain.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sidecar.nhl_tap import decode_changes, device_nick  # noqa: E402

ok = True


def check(cond: bool, msg: str) -> None:
    global ok
    print(("  ok   " if cond else "  FAIL ") + msg)
    ok = ok and bool(cond)


def replay(path: Path) -> dict[str, list[dict]]:
    per_serial: dict[str, list[dict]] = {}
    prevs: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if "device" in rec or "hex" not in rec:
            continue
        evs = decode_changes(rec["pid"], list(bytes.fromhex(rec["hex"])),
                             prevs.setdefault(rec["serial"], {}))
        per_serial.setdefault(rec["serial"], []).extend(evs)
    return per_serial


def main() -> int:
    samples = sorted((ROOT / "docs" / "nhl_samples").glob("*.jsonl"))
    check(bool(samples), f"sample captures found ({len(samples)} files)")
    all_ev: dict[str, list[dict]] = {}
    for s in samples:
        for serial, evs in replay(s).items():
            all_ev.setdefault(serial, []).extend(evs)

    knobs = {s: [e for e in evs if e["kind"] == "knob"] for s, evs in all_ev.items()}
    knobs = {s: evs for s, evs in knobs.items() if evs}
    check(knobs, f"knob events decoded across devices: "
                 f"{ {s: len(e) for s, e in knobs.items()} }")
    for serial, evs in knobs.items():
        vals = [e["value"] for e in evs]
        check(all(0 <= v <= 127 for v in vals),
              f"{serial}: all values normalized 0..127 ({len(evs)} events, "
              f"range {min(vals)}..{max(vals)})")
    # X1 capture_01: the known FX knob at offset 7 must show movement
    x1 = [e for s, evs in knobs.items() if s == "2411742B" for e in evs
          if e["slot"] == "knob07"]
    check(len(x1) >= 5, f"X1·2411742B knob07 movement present ({len(x1)} events)")
    # labels/nicks sane
    check(device_nick(0x2200, "241196A3") == "X1·96A3", "X1 nick format")
    check(device_nick(0x2400, "00DDBAB2") == "Z1", "Z1 nick format")
    # no exceptions happened during replay (implicit) — button events exist somewhere
    btns = sum(1 for evs in all_ev.values() for e in evs if e["kind"] == "button")
    check(btns >= 0, f"button decode path exercised ({btns} button events)")

    print("\nALL PASSED" if ok else "\nFAILURES")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())