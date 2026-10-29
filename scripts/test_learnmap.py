"""Offline test of learnmap: synthetic Z1 capture -> correct slot assignment.

Run: python scripts/test_learnmap.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def make_report(off: int, v: int) -> str:
    d = [1] + [0] * 34
    d[off] = v & 0xFF
    d[off + 1] = (v >> 8) & 0x0F
    return bytes(d).hex()


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        cap = Path(td) / "cap.jsonl"
        out = Path(td) / "map.json"
        t = 1000.0
        lines = []
        plan = [("Filter A", 3), ("EQ High A", 5), ("Crossfader", 31)]
        for ctl, off in plan:
            t += 10
            lines.append(json.dumps({"type": "marker", "control": ctl,
                                     "widget": f"z1_{ctl}", "t_start": t,
                                     "t_end": t + 7}))
            for k, v in enumerate([100, 300, 900, 2000, 3500, 2000]):
                lines.append(json.dumps({
                    "t": t + 1 + k * 0.5, "serial": "00DDBAB2", "pid": 0x2400,
                    "len": 35, "hex": make_report(off, v)}))
        cap.write_text("\n".join(lines), encoding="utf-8")

        r = subprocess.run(
            [sys.executable, "-m", "sidecar.nhl_tap", "learnmap", "--plan", "z1",
             "--capture", str(cap), "--out", str(out)],
            cwd=ROOT, capture_output=True, text=True)
        print(r.stdout)
        if r.returncode != 0:
            print(r.stderr)
            return 1
        mapping = json.loads(out.read_text(encoding="utf-8"))[str(0x2400)]
        expect = {"knob03": "Filter A", "knob05": "EQ High A", "knob31": "Crossfader"}
        ok = True
        for slot, name in expect.items():
            got = mapping.get(slot, {}).get("name")
            print(("  ok   " if got == name else "  FAIL ")
                  + f"{slot} -> {got!r} (expected {name!r})")
            ok = ok and got == name
        print("ALL PASSED" if ok else "FAILURES")
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())