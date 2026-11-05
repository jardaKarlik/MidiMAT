"""mapping/controls.csv -> cc_map.json entries + layout.json widgets (single source of truth).

One row = one Traktor out-mapping on the loopMIDI port:
  id          widget id (unique)
  physical    free text, for you (which hardware control)
  traktor_out the Traktor Out assignment, for you (e.g. "Deck A > High Adjust")
  channel     MIDI channel 1-16 as shown in Traktor (Ch01 = 1)
  cc          CC number as shown in Traktor (blank = row skipped for MIDI)
  label/deck  HUD text + color key (A, B, C, D, FX, AB)
  shape       circle | rect
  x,y,w,h     box in Traktor-screenshot pixels (= overlay canvas = OBS capture)

Usage:  python scripts/build_maps.py [--port loopMIDI]
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build(csv_path: str | Path = ROOT / "mapping" / "controls.csv",
          port: str = "loopMIDI", quiet: bool = False) -> dict:
    """CSV -> cc_map.json + layout.json. Returns a small summary dict."""
    with open(csv_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    ids = [r["id"] for r in rows]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise SystemExit(f"duplicate ids: {sorted(dupes)}")

    entries, widgets, seen_keys, skipped = [], [], {}, []
    for r in rows:
        w = {"id": r["id"], "label": r["label"], "deck": r["deck"] or None,
             "shape": r["shape"] or "circle"}
        if all(r.get(k, "").strip() for k in "xywh"):
            w["box"] = {k: int(float(r[k])) for k in "xywh"}
        widgets.append(w)
        if not r["cc"].strip():
            skipped.append(r["id"])
            continue
        ch, cc = int(r["channel"] or 1), int(r["cc"])
        key = (ch, cc)
        if key in seen_keys:
            raise SystemExit(f"ch{ch} cc{cc} used by both {seen_keys[key]} and {r['id']}")
        seen_keys[key] = r["id"]
        label = f"Deck {r['deck']} · {r['label']}" if r["deck"] in ("A", "B", "C", "D") else r["label"]
        entries.append({"port": port, "channel": ch - 1, "kind": "cc", "number": cc,
                        "label": label, "deck": r["deck"] or None, "widget": r["id"]})

    cc_path = ROOT / "cc_map.json"
    cc = json.loads(cc_path.read_text(encoding="utf-8")) if cc_path.exists() else {}
    cc.update({"port_hint": port, "entries": entries,
               "_generated": "by scripts/build_maps.py from mapping/controls.csv — edit the CSV"})
    cc_path.write_text(json.dumps(cc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lay_path = ROOT / "layout.json"
    lay = json.loads(lay_path.read_text(encoding="utf-8"))
    old = {w["id"]: w for w in lay.get("widgets", [])}
    for w in widgets:  # keep an existing box if the CSV row has none
        if "box" not in w and w["id"] in old and "box" in old[w["id"]]:
            w["box"] = old[w["id"]]["box"]
    lay["widgets"] = [w for w in widgets if "box" in w]
    colors = lay.setdefault("theme", {}).setdefault("deck_colors", {})
    for deck, col in {"A": "#33ccff", "B": "#3dff9e", "C": "#c084fc", "D": "#ff8a65",
                      "FX": "#ffcc33", "AB": "#ffffff"}.items():
        colors.setdefault(deck, col)  # 4-deck setups: C/D need their own colors
    lay_path.write_text(json.dumps(lay, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    unplaced = [w["id"] for w in widgets if "box" not in w]
    if not quiet:
        print(f"cc_map.json: {len(entries)} entries (port ~{port!r})")
        print(f"layout.json: {len(lay['widgets'])} widgets with a screen box"
              f" ({len(unplaced)} HUD-only: place them in the editor)")
        if skipped:
            print(f"no CC yet (HUD/glow inactive): {', '.join(skipped)}")
    return {"entries": len(entries), "widgets": len(lay["widgets"]),
            "unplaced": unplaced, "no_cc": skipped}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(ROOT / "mapping" / "controls.csv"))
    ap.add_argument("--port", default="loopMIDI", help="port substring Traktor sends to")
    args = ap.parse_args()
    build(args.csv, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
