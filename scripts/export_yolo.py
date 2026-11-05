"""Turn your hand-placed boxes into a YOLO training dataset (the "train our own model" track).

    .\\.venv\\Scripts\\python.exe scripts\\export_yolo.py docs\\traktor-ui\\screens\\*.png

Every screenshot must show Traktor in the SAME layout/resolution your boxes were placed on
(the boxes are reused for each image — vary loaded tracks, FX on/off, playing/paused, etc.).
Classes: 0 knob (circle), 1 slider (long rect), 2 button (short rect).

Output: dataset/yolo/{images,labels}/{train,val}/ + dataset/yolo/data.yaml
Train (GPU recommended, CPU works for a small model):
    pip install ultralytics
    yolo detect train data=dataset/yolo/data.yaml model=yolo11n.pt imgsz=1280 epochs=150
See docs/AI_PLACEMENT.md for the walkthrough.
"""
from __future__ import annotations

import argparse
import glob
import json
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import setup_wizard  # noqa: E402

CLASSES = ["knob", "slider", "button"]


def cls_of(r: dict) -> int:
    if r["shape"] == "circle":
        return 0
    w, h = int(r["w"]), int(r["h"])
    return 1 if max(w, h) / max(1, min(w, h)) >= 3 else 2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+", help="screenshots (globs ok)")
    ap.add_argument("--out", default=str(ROOT / "dataset" / "yolo"))
    ap.add_argument("--val", type=float, default=0.2, help="validation fraction")
    args = ap.parse_args()

    files = sorted({f for pat in args.images for f in glob.glob(pat)})
    if not files:
        raise SystemExit("no screenshots matched")
    lay = json.loads((ROOT / "layout.json").read_text(encoding="utf-8"))
    cw, ch = lay["canvas"]["width"], lay["canvas"]["height"]
    rows = [r for r in setup_wizard.load_rows().values()
            if r.get("shape") in ("circle", "rect") and all(r.get(k) for k in "xywh")]
    if not rows:
        raise SystemExit("no placed boxes in mapping/controls.csv")
    # YOLO label = class cx cy w h, all normalized 0-1 -> independent of image size
    lines = [f"{cls_of(r)} {(int(r['x']) + int(r['w']) / 2) / cw:.6f} "
             f"{(int(r['y']) + int(r['h']) / 2) / ch:.6f} {int(r['w']) / cw:.6f} "
             f"{int(r['h']) / ch:.6f}" for r in rows]

    out = Path(args.out)
    random.seed(42)
    random.shuffle(files)
    n_val = max(1, int(len(files) * args.val)) if len(files) > 1 else 0
    for split in ("train", "val"):
        (out / "images" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)
    for i, f in enumerate(files):
        split = "val" if i < n_val else "train"
        dst = out / "images" / split / Path(f).name
        shutil.copy2(f, dst)
        (out / "labels" / split / (dst.stem + ".txt")).write_text("\n".join(lines) + "\n")
    if n_val == 0:  # single image: reuse it for val so training can run at all
        shutil.copy2(files[0], out / "images" / "val" / Path(files[0]).name)
        (out / "labels" / "val" / (Path(files[0]).stem + ".txt")).write_text("\n".join(lines) + "\n")
    (out / "data.yaml").write_text(
        f"path: {out.resolve().as_posix()}\ntrain: images/train\nval: images/val\n"
        f"names:\n" + "".join(f"  {i}: {c}\n" for i, c in enumerate(CLASSES)), encoding="utf-8")
    counts = {c: sum(1 for r in rows if cls_of(r) == i) for i, c in enumerate(CLASSES)}
    print(f"{len(files)} image(s) ({len(files) - n_val} train / {max(n_val, 1)} val), "
          f"{len(rows)} boxes each {counts} -> {out / 'data.yaml'}")
    print("NOTE: unmapped widgets on screen count as 'background' — the more of the UI you "
          "box, the cleaner the detector learns.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
