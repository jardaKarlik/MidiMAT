"""Score box suggestions against YOUR hand-placed boxes (mapping/controls.csv = ground truth).

    # stage 1 only (no API key): how many of your controls does the detector find?
    .\\.venv\\Scripts\\python.exe scripts\\eval_suggest.py docs\\traktor-ui\\screens\\traktor.png

    # full pipeline (detector + vision model) on every placed control
    $env:OPENROUTER_API_KEY = "..."   # in your shell, never in the repo
    .\\.venv\\Scripts\\python.exe scripts\\eval_suggest.py docs\\traktor-ui\\screens\\traktor.png --full
    .\\.venv\\Scripts\\python.exe scripts\\eval_suggest.py shot.png --full --model google/gemini-2.5-flash

The screenshot must be the same frame your boxes were placed on (OBS "Screenshot (Source)",
same Traktor layout). Coordinates are scaled from the layout canvas to the image size.
Writes <image>_eval.png: green = your box, red = suggestion / nearest candidate.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from sidecar import suggest as S  # noqa: E402
import setup_wizard  # noqa: E402


def center_err(a: dict, b: dict) -> float:
    return (((a["x"] + a["w"] / 2) - (b["x"] + b["w"] / 2)) ** 2
            + ((a["y"] + a["h"] / 2) - (b["y"] + b["h"] / 2)) ** 2) ** 0.5


def centre_hit(c: dict, g: dict) -> bool:
    """Size-agnostic: candidate centre lies inside the central half of your box.
    (Hand-drawn boxes are looser/tighter than detector edges, so IoU under-reports.)"""
    cx, cy = c["x"] + c["w"] / 2, c["y"] + c["h"] / 2
    return (abs(cx - (g["x"] + g["w"] / 2)) <= max(4, g["w"] / 4)
            and abs(cy - (g["y"] + g["h"] / 2)) <= max(4, g["h"] / 4))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--full", action="store_true", help="also ask the vision model")
    ap.add_argument("--model")
    args = ap.parse_args()

    img = cv2.imread(args.image)
    if img is None:
        raise SystemExit(f"cannot read {args.image}")
    lay = json.loads((ROOT / "layout.json").read_text(encoding="utf-8"))
    sx, sy = img.shape[1] / lay["canvas"]["width"], img.shape[0] / lay["canvas"]["height"]
    gt = []
    for r in setup_wizard.load_rows().values():
        if r.get("shape") == "hud" or not all(r.get(k) for k in "xywh"):
            continue
        gt.append({**r, "box": {"x": int(r["x"]) * sx, "y": int(r["y"]) * sy,
                                "w": int(r["w"]) * sx, "h": int(r["h"]) * sy}})
    if not gt:
        raise SystemExit("no placed boxes in mapping/controls.csv to compare against")

    vis = img.copy()
    cands = S.detect_candidates(img)
    print(f"\n{len(gt)} placed controls · {len(cands)} candidates detected\n")
    print("STAGE 1 - detector (does a candidate cover your box?)")
    hit = chit = 0
    errs = []
    for g in gt:
        best = max(cands, key=lambda c: S._iou(c, g["box"]), default=None)
        iou = S._iou(best, g["box"]) if best else 0
        near = min(cands, key=lambda c: center_err(c, g["box"]), default=None)
        ok = iou >= 0.5
        cok = bool(near) and centre_hit(near, g["box"])
        hit += ok
        chit += cok
        if best:
            errs.append(center_err(best, g["box"]))
        b = g["box"]
        cv2.rectangle(vis, (int(b["x"]), int(b["y"])), (int(b["x"] + b["w"]), int(b["y"] + b["h"])),
                      (60, 220, 60), 2)
        if not cok:
            print(f"  miss {g['id']:18s} best IoU {iou:.2f} · nearest centre "
                  f"{center_err(near, g['box']) if near else 0:.0f}px ({near['kind'] if near else '-'})")
    print(f"  centre-hit recall: {chit}/{len(gt)} = {chit / len(gt):.0%}   (the number that matters)")
    by_shape = {}
    for g in gt:
        near = min(cands, key=lambda c: center_err(c, g["box"]), default=None)
        k = g.get("shape", "?")
        t = by_shape.setdefault(k, [0, 0]); t[1] += 1; t[0] += bool(near) and centre_hit(near, g["box"])
    print("  by shape: " + ", ".join(f"{k} {a}/{b}" for k, (a, b) in by_shape.items()))
    kinds = {k: sum(1 for c in cands if c["kind"] == k) for k in ("knob", "slider", "button")}
    print(f"  candidates by kind: {kinds}")
    print(f"  recall@IoU0.5: {hit}/{len(gt)} = {hit / len(gt):.0%}"
          + (f" · median centre error {sorted(errs)[len(errs) // 2]:.1f}px" if errs else ""))

    if args.full:
        print("\nSTAGE 1-4 - full pipeline (vision model picks marks)")
        res = S.suggest(img, gt, model=args.model)
        by = {s["id"]: s for s in res["suggestions"]}
        good, near, wrong = 0, 0, []
        for g in gt:
            s = by.get(g["id"])
            if not s:
                wrong.append((g["id"], "not found"))
                continue
            iou, ce = S._iou(s, g["box"]), center_err(s, g["box"])
            cv2.rectangle(vis, (s["x"], s["y"]), (s["x"] + s["w"], s["y"] + s["h"]), (60, 60, 255), 1)
            if iou >= 0.5:
                good += 1
            elif ce <= 25:
                near += 1
            else:
                wrong.append((g["id"], f"{ce:.0f}px off ({s['source']})"))
        n = len(gt)
        print(f"  correct (IoU>=0.5): {good}/{n} = {good / n:.0%}")
        print(f"  near (<=25px, needs a nudge): {near}/{n}")
        print(f"  wrong / missing: {len(wrong)}/{n}")
        for i, why in wrong:
            print(f"    {i:18s} {why}")
    out = str(Path(args.image).with_name(Path(args.image).stem + "_eval.png"))
    cv2.imwrite(out, vis)
    print(f"\nvisual: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
