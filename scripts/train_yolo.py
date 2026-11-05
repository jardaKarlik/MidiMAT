"""Train the Traktor control detector (YOLO) from your screenshots + placed boxes.

    .\\.venv\\Scripts\\python.exe -m pip install -r requirements-train.txt   # once (~1-2 GB, torch)
    .\\.venv\\Scripts\\python.exe scripts\\train_yolo.py docs\\traktor-ui\\screens\\*.png
    .\\.venv\\Scripts\\python.exe scripts\\train_yolo.py docs\\traktor-ui\\screens\\*.png --device 0   # NVIDIA GPU

Steps: export dataset (scripts/export_yolo.py) -> train yolo11n -> copy best weights to
models/traktor_yolo.pt, which sidecar/suggest.py then uses automatically instead of OpenCV.

UI-specific augmentation: no flips (mirrored text/layout never happens), no hue shift
(deck colours carry meaning), mild brightness/scale/translate (OBS capture variance).
Watch runs/detect/<name>/results.png: losses go down, mAP50 goes up (>0.9 is great).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+", help="clean screenshots (NOT *_eval/_marks images)")
    ap.add_argument("--epochs", type=int, default=150)
    ap.add_argument("--imgsz", type=int, default=1280, help="small controls need high res")
    ap.add_argument("--device", default="cpu", help="cpu | 0 (first CUDA GPU) | mps")
    ap.add_argument("--model", default="yolo11n.pt", help="yolo11n.pt (fast) / yolo11s.pt")
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--name", default="traktor")
    args = ap.parse_args()

    bad = [f for f in args.images if f.endswith(("_eval.png", "_marks.png"))]
    if bad:
        raise SystemExit(f"these are tool OUTPUT images with boxes drawn on them: {bad}")
    data = ROOT / "dataset" / "yolo"
    if data.exists():
        shutil.rmtree(data)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "export_yolo.py"), *args.images,
                    "--out", str(data)], check=True)

    try:
        from ultralytics import YOLO  # noqa: PLC0415
    except ImportError:
        raise SystemExit("ultralytics missing: .venv\\Scripts\\python.exe -m pip install "
                         "-r requirements-train.txt") from None
    model = YOLO(args.model)
    model.train(
        data=str(data / "data.yaml"), epochs=args.epochs, imgsz=args.imgsz,
        device=args.device, batch=args.batch, project=str(ROOT / "runs" / "detect"),
        name=args.name, exist_ok=True, patience=40, plots=True,
        fliplr=0.0, flipud=0.0, hsv_h=0.0, hsv_s=0.3, hsv_v=0.3,
        degrees=0.0, shear=0.0, perspective=0.0, scale=0.25, translate=0.05,
        mosaic=1.0, close_mosaic=20,
    )
    best = ROOT / "runs" / "detect" / args.name / "weights" / "best.pt"
    if not best.exists():
        raise SystemExit("training finished without best.pt?")
    (ROOT / "models").mkdir(exist_ok=True)
    shutil.copy2(best, ROOT / "models" / "traktor_yolo.pt")
    print(f"\nmodel -> models/traktor_yolo.pt (suggest + eval now use it)\n"
          f"curves -> runs/detect/{args.name}/results.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
