"""Offline test for sidecar/refit.py: repetitive Traktor-like grid, scaled + shifted,
with jitter, missed and spurious detections and a few wrong kinds."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sidecar.refit import refit  # noqa: E402


def layout():
    t = []
    for d, x0 in (("a", 850), ("b", 1035)):            # mixer: 2 strips x 4 rows x 2 cols
        for r in range(4):
            for c in range(2):
                t.append({"id": f"k_{d}{r}{c}", "shape": "circle",
                          "x": x0 + c * 63, "y": 125 + r * 55, "w": 34, "h": 34})
        t.append({"id": f"fader_{d}", "shape": "rect", "x": x0 + 70, "y": 300, "w": 18, "h": 130})
    for d, (x0, y0) in {"A": (30, 360), "B": (1110, 360), "C": (30, 580), "D": (1110, 580)}.items():
        for i, w in enumerate((34, 34, 34, 30, 30, 30, 30, 30, 30, 30, 30)):  # transport + loop row
            t.append({"id": f"btn_{d}{i}", "shape": "rect", "x": x0 + i * 40, "y": y0, "w": w, "h": 24})
    for u, (x0, y0) in {1: (40, 40), 2: (1540, 40), 3: (40, 82), 4: (1540, 82)}.items():
        t.append({"id": f"fx{u}_dw", "shape": "circle", "x": x0 + 90, "y": y0, "w": 30, "h": 30})
        for k in range(3):
            t.append({"id": f"fx{u}_k{k}", "shape": "rect", "x": x0 + 140 + k * 75, "y": y0 + 8,
                      "w": 60, "h": 10})
    return t


def run(s, tx, ty, seed):
    rnd = random.Random(seed)
    tpl = layout()
    dets = []
    for b in tpl:
        if rnd.random() < 0.08:                         # missed
            continue
        cx = s * (b["x"] + b["w"] / 2) + tx + rnd.uniform(-1.5, 1.5)
        cy = s * (b["y"] + b["h"] / 2) + ty + rnd.uniform(-1.5, 1.5)
        w, h = s * b["w"] * 0.85, s * b["h"] * 0.85     # detector edges tighter than user boxes
        kind = "knob" if b["shape"] == "circle" else ("slider" if max(b["w"], b["h"]) / min(b["w"], b["h"]) >= 3 else "button")
        if rnd.random() < 0.04:
            kind = "knob" if kind != "knob" else "button"   # misclassified
        dets.append({"x": cx - w / 2, "y": cy - h / 2, "w": w, "h": h, "kind": kind})
    for _ in range(12):                                 # spurious
        dets.append({"x": rnd.uniform(0, 1800), "y": rnd.uniform(0, 1000), "w": 30, "h": 24,
                     "kind": rnd.choice(["knob", "button", "slider"])})
    res = refit(tpl, dets)
    tr = res["transform"]
    ok_t = abs(tr["sx"] - s) < 0.01 and abs(tr["tx"] - tx) < 4 and abs(tr["ty"] - ty) < 4
    good = 0
    for b, sg in zip(tpl, res["suggestions"]):
        ex = s * (b["x"] + b["w"] / 2) + tx
        ey = s * (b["y"] + b["h"] / 2) + ty
        good += abs(sg["x"] + sg["w"] / 2 - ex) <= 3 and abs(sg["y"] + sg["h"] / 2 - ey) <= 3
    frac = good / len(tpl)
    print(f"  s={s} t=({tx:+},{ty:+}) -> s={tr['sx']:.3f}/{tr['sy']:.3f} "
          f"t=({tr['tx']:+.1f},{tr['ty']:+.1f}) matched {tr['matched']}/{len(tpl)} "
          f"rms {tr['rms']:.1f}px · within 3px: {frac:.0%}  {'OK' if ok_t and frac >= 0.95 else 'FAIL'}")
    return ok_t and frac >= 0.95


cases = [(1.0, 0, 0, 1), (1.0, 23, -11, 2), (0.85, 120, -40, 3), (1.25, -300, -150, 4),
         (0.667, 0, 0, 5), (0.9, 400, 200, 6)]
ok = all([run(*c) for c in cases])
print("ALL PASSED" if ok else "FAILED")
sys.exit(0 if ok else 1)
