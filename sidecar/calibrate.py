"""Interactive widget calibration -> writes boxes into layout.json (Tier A).

Windows-only (ctypes cursor capture). Flow:
  1. Capture the OBS crop origin: hover the TOP-LEFT corner of the Traktor
     capture area -> Enter (twice is fine; last position wins).
  2. For each widget: hover the CENTER of that control in the Traktor GUI
     -> Enter. Box keeps its existing size, recentered; coordinates are stored
     RELATIVE to the origin (so the overlay canvas == OBS crop).

Usage:
    python -m sidecar.calibrate [--layout layout.json] [--skip-origin] [--only id1,id2]
"""
from __future__ import annotations

import argparse
import ctypes
import json
import shutil
import sys
from pathlib import Path


def cursor_pos() -> tuple[int, int]:
    # DPI-aware or Windows lies about coordinates on scaled displays
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:  # noqa: BLE001
        pass

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def confirm(msg: str) -> bool:
    ans = input(f"{msg} [Enter=ok, s=skip, q=quit] ").strip().lower()
    if ans == "q":
        raise SystemExit("aborted by user")
    return ans != "s"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="MidiMAT calibrate")
    ap.add_argument("--layout", default="layout.json")
    ap.add_argument("--skip-origin", action="store_true",
                    help="keep existing origin; only recapture widget boxes")
    ap.add_argument("--origin-only", action="store_true",
                    help="recapture ONLY the origin and SHIFT all existing boxes "
                         "by the difference (fixes a wrong-origin run without "
                         "re-hovering every control)")
    ap.add_argument("--only", help="comma-separated widget ids to recapture")
    args = ap.parse_args(argv)

    layout_path = Path(args.layout)
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    only = set(args.only.split(",")) if args.only else None

    origin = layout.get("origin", {"x": 0, "y": 0})

    if args.origin_only:
        print("== Recapture origin ==")
        print(f"current origin = {origin}")
        print("Hover the mouse over the TOP-LEFT corner of the area OBS captures")
        print("(the actual Traktor window — NOT a preview inside Streamlabs/OBS).")
        input("Press Enter there... ")
        ox, oy = cursor_pos()
        dx, dy = origin["x"] - ox, origin["y"] - oy
        for w in layout["widgets"]:
            w["box"]["x"] += dx
            w["box"]["y"] += dy
        layout["origin"] = {"x": ox, "y": oy}
        backup = layout_path.with_suffix(".json.bak")
        shutil.copy2(layout_path, backup)
        layout_path.write_text(json.dumps(layout, indent=2) + "\n", encoding="utf-8")
        print(f"origin {origin} -> ({ox}, {oy}); shifted all boxes by "
              f"({dx}, {dy}) (backup: {backup.name})")
        print("Refresh the OBS/Streamlabs browser source to see the result.")
        return 0

    if not args.skip_origin:
        print("== Step 1: OBS crop origin ==")
        print("Hover the mouse over the TOP-LEFT corner of the area OBS captures")
        print("(the cropped Traktor window).")
        input("Press Enter there... ")
        ox, oy = cursor_pos()
        origin = {"x": ox, "y": oy}
        print(f"origin = ({ox}, {oy})")
    print(f"using origin {origin} — widget coords will be relative to it\n")

    print("== Step 2: widget centers ==")
    for w in layout["widgets"]:
        if only and w["id"] not in only:
            continue
        b = w["box"]
        print(f"\nHover the CENTER of: {w['label']}  (current box {b})")
        if not confirm("Ready?"):
            continue
        cx, cy = cursor_pos()
        rx, ry = cx - origin["x"], cy - origin["y"]
        w["box"] = {"x": rx - b["w"] // 2, "y": ry - b["h"] // 2,
                    "w": b["w"], "h": b["h"]}
        print(f"  -> {w['id']} box = {w['box']}")

    layout["origin"] = origin
    backup = layout_path.with_suffix(".json.bak")
    shutil.copy2(layout_path, backup)
    layout_path.write_text(json.dumps(layout, indent=2) + "\n", encoding="utf-8")
    print(f"\nsaved {layout_path} (backup: {backup.name})")
    print("Restart the sidecar (or refresh the OBS browser source) to load it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())