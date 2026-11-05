"""Offline test for sidecar/suggest.py: synthetic Traktor-like frame + fake VLM reply."""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sidecar import suggest as S  # noqa: E402


def frame():
    img = np.full((1080, 1920, 3), (27, 23, 21), np.uint8)
    knobs = {"eq_hi_a": (929, 142), "eq_mid_a": (929, 197), "eq_lo_a": (929, 252),
             "gain_a": (866, 142)}
    for cx, cy in knobs.values():
        cv2.circle(img, (cx, cy), 17, (58, 54, 50), -1)
        cv2.circle(img, (cx, cy), 17, (150, 150, 150), 2)
        cv2.line(img, (cx, cy), (cx, cy - 14), (230, 230, 230), 2)
    sliders = {"fader_a": (920, 300, 18, 130), "fx1_knob1": (175, 44, 60, 10)}
    for x, y, w, h in sliders.values():
        cv2.rectangle(img, (x, y), (x + w, y + h), (40, 38, 36), -1)
        cv2.rectangle(img, (x, y), (x + w, y + h), (120, 120, 120), 1)
    buttons = {"play_a": (30, 360, 34, 24)}
    for x, y, w, h in buttons.values():
        cv2.rectangle(img, (x, y), (x + w, y + h), (55, 50, 48), -1)
        cv2.rectangle(img, (x, y), (x + w, y + h), (110, 110, 110), 1)
    return img, knobs, sliders, buttons


def main() -> int:
    img, knobs, sliders, buttons = frame()
    cands = S.detect_candidates(img)
    ok = True

    def found(box, kinds, tol=6):
        cx, cy = box["x"] + box["w"] / 2, box["y"] + box["h"] / 2
        return any(c["kind"] in kinds and abs(c["x"] + c["w"] / 2 - cx) <= tol
                   and abs(c["y"] + c["h"] / 2 - cy) <= tol for c in cands)

    for name, (cx, cy) in knobs.items():
        r = found({"x": cx - 17, "y": cy - 17, "w": 34, "h": 34}, ("knob",))
        print(f"  knob   {name:10s} {'OK' if r else 'MISSED'}"); ok &= r
    for name, (x, y, w, h) in {**sliders, **buttons}.items():
        r = found({"x": x, "y": y, "w": w, "h": h}, ("slider", "button"))
        print(f"  rect   {name:10s} {'OK' if r else 'MISSED'}"); ok &= r
    print(f"  {len(cands)} candidates total")

    # fake VLM: mark for eq_mid_a, approximate box_2d for fader_a, null for unknown
    def mark_of(cx, cy):
        return min(cands, key=lambda c: abs(c["x"] + c["w"] / 2 - cx)
                   + abs(c["y"] + c["h"] / 2 - cy))["mark"]
    fx, fy, fw, fh = sliders["fader_a"]
    approx = [(fy - 6) / 1080 * 1000, (fx + 4) / 1920 * 1000,
              (fy + fh + 8) / 1080 * 1000, (fx + fw + 9) / 1920 * 1000]
    reply_json = ('{"eq_mid_a": {"mark": %d}, "fader_a": {"box_2d": %s}, "ghost": null}'
                  % (mark_of(*knobs["eq_mid_a"]), approx))

    def transport(body):
        assert body["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/png")
        return {"choices": [{"message": {"content": "Sure!\n```json\n" + reply_json + "\n```"}}]}

    rows = [{"id": "eq_mid_a", "shape": "circle"}, {"id": "fader_a", "shape": "rect"},
            {"id": "ghost", "shape": "circle"}]
    res = S.suggest(img, rows, transport=transport)
    by = {s["id"]: s for s in res["suggestions"]}
    m = by.get("eq_mid_a")
    r1 = m and m["source"] == "mark" and abs(m["x"] + m["w"] / 2 - 929) <= 3
    f = by.get("fader_a")
    r2 = f and f["source"] == "box+snap" and abs(f["x"] - fx) <= 3 and abs(f["h"] - fh) <= 4
    r3 = res["missing"] == ["ghost"]
    print(f"  vlm mark  -> {'OK' if r1 else 'FAIL'} {m}")
    print(f"  vlm box   -> {'OK' if r2 else 'FAIL'} {f} (snapped from approx)")
    print(f"  vlm null  -> {'OK' if r3 else 'FAIL'} missing={res['missing']}")
    ok &= bool(r1 and r2 and r3)
    print("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
