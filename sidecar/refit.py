"""Re-fit a known layout onto a new screenshot (Traktor window moved / resized / rescaled).

    detections (YOLO) + your saved boxes (template)
      1. vote   - for every scale in a range, each (template, detection) pair of the same
                  kind votes for an offset; the most-voted (scale, offset) wins. Robust to
                  missed and spurious detections, works for large moves.
      2. refine - iterative closest point: per-axis least squares (sx, sy, tx, ty) on pairs
                  that agree, shrinking the match radius.
      3. snap   - map every template box; take the matched detection's box ("snap") or keep
                  the mapped box when nothing is close ("fit").

All coordinates here are in LAYOUT CANVAS space (the overlay canvas, e.g. 1920x1080).

CLI:  python -m sidecar.refit shot.png        # prints transform + per-control result
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
KIND_OF_SHAPE = {"circle": {"knob"}, "rect": {"slider", "button"}}


def _centres(boxes: list[dict]) -> np.ndarray:
    return np.array([[b["x"] + b["w"] / 2, b["y"] + b["h"] / 2] for b in boxes], float)


def _compatible(shape: str, kind: str) -> bool:
    return kind in KIND_OF_SHAPE.get(shape, {"knob", "slider", "button"})


def estimate_transform(template: list[dict], dets: list[dict],
                       scales: np.ndarray | None = None, bin_px: float = 6.0) -> dict:
    """template: [{x,y,w,h,shape}], dets: [{x,y,w,h,kind}] -> {sx,sy,tx,ty,matched,rms}."""
    if not template or not dets:
        raise ValueError("need template boxes and detections")
    if scales is None:
        scales = np.round(np.arange(0.5, 2.0001, 0.01), 3)
    T, D = _centres(template), _centres(dets)
    compat = np.array([[_compatible(t.get("shape", ""), d["kind"]) for d in dets]
                       for t in template])
    ti, di = np.nonzero(compat)
    best = (-1, 1.0, 0.0, 0.0)
    for s in scales:  # 1. coarse vote over (scale, offset)
        off = D[di] - s * T[ti]
        keys = np.round(off / bin_px).astype(np.int64)
        uniq, counts = np.unique(keys, axis=0, return_counts=True)
        k = counts.argmax()
        if counts[k] > best[0]:
            o = off[(keys == uniq[k]).all(axis=1)].mean(axis=0)
            best = (int(counts[k]), float(s), float(o[0]), float(o[1]))
    _, s, tx, ty = best
    sx = sy = s
    radius = 40.0
    pairs: list[tuple[int, int]] = []
    for _ in range(8):  # 2. ICP refine, shrinking radius
        mapped = np.c_[sx * T[:, 0] + tx, sy * T[:, 1] + ty]
        dist = np.linalg.norm(mapped[:, None, :] - D[None, :, :], axis=2)
        dist[~compat] = np.inf
        pairs, used = [], set()
        for t in np.argsort(dist.min(axis=1)):  # greedy one-to-one
            d = int(dist[t].argmin())
            if dist[t, d] <= radius and d not in used:
                pairs.append((int(t), d))
                used.add(d)
        if len(pairs) < 3:
            break
        tp, dp = T[[p[0] for p in pairs]], D[[p[1] for p in pairs]]
        if np.ptp(tp[:, 0]) > 50 and np.ptp(tp[:, 1]) > 50:
            sx, tx = np.polyfit(tp[:, 0], dp[:, 0], 1)
            sy, ty = np.polyfit(tp[:, 1], dp[:, 1], 1)
        radius = max(8.0, radius * 0.6)
    mapped = np.c_[sx * T[:, 0] + tx, sy * T[:, 1] + ty]
    res = [np.linalg.norm(mapped[t] - D[d]) for t, d in pairs]
    return {"sx": float(sx), "sy": float(sy), "tx": float(tx), "ty": float(ty),
            "matched": len(pairs), "rms": float(np.sqrt(np.mean(np.square(res)))) if res else 0.0,
            "pairs": pairs}


def refit(template: list[dict], dets: list[dict]) -> dict:
    """-> {"transform": {...}, "suggestions": [{id,x,y,w,h,source}], "unmatched": [ids]}"""
    tr = estimate_transform(template, dets)
    pair_of = dict(tr.pop("pairs"))
    out, unmatched = [], []
    for i, t in enumerate(template):
        mx, my = tr["sx"] * t["x"] + tr["tx"], tr["sy"] * t["y"] + tr["ty"]
        mw, mh = tr["sx"] * t["w"], tr["sy"] * t["h"]
        d = dets[pair_of[i]] if i in pair_of else None
        if d is not None:
            # detector edges are tight; keep the user's box size (their taste for glow
            # padding) but centre it on the detection
            cx, cy = d["x"] + d["w"] / 2, d["y"] + d["h"] / 2
            box, src = (cx - mw / 2, cy - mh / 2, mw, mh), "snap"
        else:
            box, src = (mx, my, mw, mh), "fit"
            unmatched.append(t["id"])
        out.append({"id": t["id"], "x": int(round(box[0])), "y": int(round(box[1])),
                    "w": int(round(box[2])), "h": int(round(box[3])), "source": src})
    return {"transform": tr, "suggestions": out, "unmatched": unmatched}


def dets_to_canvas(dets: list[dict], img_w: int, img_h: int, cw: int, ch: int) -> list[dict]:
    fx, fy = cw / img_w, ch / img_h
    return [{**d, "x": d["x"] * fx, "y": d["y"] * fy, "w": d["w"] * fx, "h": d["h"] * fy}
            for d in dets]


def template_rows(rows: list[dict]) -> list[dict]:
    return [{"id": r["id"], "shape": r.get("shape", ""), "x": float(r["x"]),
             "y": float(r["y"]), "w": float(r["w"]), "h": float(r["h"])}
            for r in rows if r.get("shape") != "hud" and all(r.get(k) for k in "xywh")]


def main(argv: list[str] | None = None) -> int:
    import json  # noqa: PLC0415

    import cv2  # noqa: PLC0415

    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "scripts"))
    from sidecar import suggest as S  # noqa: PLC0415
    import setup_wizard  # noqa: PLC0415

    path = (argv or sys.argv[1:] or [None])[0]
    if not path:
        raise SystemExit("usage: python -m sidecar.refit screenshot.png")
    img = cv2.imread(path)
    if img is None:
        raise SystemExit(f"cannot read {path}")
    canvas = json.loads((ROOT / "layout.json").read_text(encoding="utf-8"))["canvas"]
    dets = dets_to_canvas(S.detect_candidates(img), img.shape[1], img.shape[0],
                          canvas["width"], canvas["height"])
    res = refit(template_rows(list(setup_wizard.load_rows().values())), dets)
    t = res["transform"]
    print(f"detector {S.detector_backend()} · {len(dets)} detections · matched "
          f"{t['matched']}/{len(res['suggestions'])} · scale {t['sx']:.3f}x{t['sy']:.3f} · "
          f"shift {t['tx']:+.1f},{t['ty']:+.1f}px · rms {t['rms']:.1f}px")
    if res["unmatched"]:
        print("not snapped (mapped only): " + ", ".join(res["unmatched"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
