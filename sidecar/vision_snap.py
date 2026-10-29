"""Vision snap: locate knobs in the RUNNING Traktor window and snap layout.json.

Replaces fragile hover-calibration: grabs a frame of the actual Traktor window
(ctypes FindWindow + mss), detects the round knobs (HoughCircles — knobs are dark
circles with light rims), and snaps every circular widget in layout.json to the
nearest detection. Canvas size is set to the window size so the overlay maps
1:1 onto the captured window.

REQUIREMENT for OBS/Streamlabs: set the Window Capture source and the Browser
Source to the SAME rectangle in the scene (both scaled identically) — then window
pixels == overlay canvas pixels no matter how the compositor scales them.

Usage:
    python -m sidecar.vision_snap            # detect + annotated preview PNG
    python -m sidecar.vision_snap --apply    # also snap layout.json circles
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent


def traktor_window_rect(title_substr: str = "Traktor") -> dict | None:
    """Largest visible window matching title -> CLIENT-area rect (content only,
    no invisible resize borders / title bar) + hwnd."""
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
    user32 = ctypes.windll.user32
    titles: list[tuple] = []

    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_long)

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                if title_substr.lower() in buf.value.lower():
                    rc = wt.RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(rc))
                    titles.append((buf.value, rc.left, rc.top,
                                   rc.right, rc.bottom, hwnd))
        return True

    user32.EnumWindows(EnumProc(cb), 0)
    if not titles:
        return None
    name, l, t, r, b, hwnd = max(
        titles, key=lambda x: (x[3] - x[1]) * (x[4] - x[2]))

    # CLIENT area (what Traktor actually draws) via GetClientRect + ClientToScreen
    crc = wt.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(crc))
    pt = wt.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return {"title": name,
            "x": int(pt.x), "y": int(pt.y),            # CLIENT on screen
            "w": int(crc.right), "h": int(crc.bottom),
            "wx": int(l), "wy": int(t),                # WINDOW outer (PrintWindow paints all)
            "ww": int(r - l), "wh": int(b - t),
            "hwnd": int(hwnd)}


def grab(rect: dict) -> np.ndarray:
    """Grab the window CONTENT even when occluded (PrintWindow, PW_RENDERFULLCONTENT).
    Falls back to a screen grab of the rect if PrintWindow yields a blank frame."""
    from ctypes import wintypes

    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    hwnd = rect["hwnd"]
    # PrintWindow paints the WHOLE window (incl. title/menu) — size the bitmap to
    # the outer rect, then crop to the client area so coords are content-space.
    ox, oy = rect["x"] - rect.get("wx", rect["x"]), rect["y"] - rect.get("wy", rect["y"])
    w, h = rect["ww"], rect["wh"]
    cw, ch = rect["w"], rect["h"]
    img = None
    try:
        hwnd_dc = user32.GetWindowDC(hwnd)
        mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
        bmp = gdi32.CreateCompatibleBitmap(hwnd_dc, w, h)
        gdi32.SelectObject(mem_dc, bmp)
        PW_RENDERFULLCONTENT = 0x2
        ok = user32.PrintWindow(hwnd, mem_dc, PW_RENDERFULLCONTENT)

        class BMI(ctypes.Structure):
            _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                        ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                        ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                        ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                        ("biClrImportant", wintypes.DWORD)]

        if ok:
            buf = ctypes.create_string_buffer(w * h * 4)
            bmi = BMI()
            bmi.biSize = ctypes.sizeof(BMI)
            bmi.biWidth, bmi.biHeight = w, -h  # top-down
            bmi.biPlanes, bmi.biBitCount = 1, 32
            gdi32.GetDIBits(mem_dc, bmp, 0, h, buf, ctypes.byref(bmi), 0)
            arr = np.frombuffer(buf.raw, np.uint8).reshape(h, w, 4)[:, :, :3]
            cand = arr[:, :, ::-1].copy()  # BGRA -> BGR
            cand = cand[oy:oy + ch, ox:ox + cw]  # crop to client content
            if cand.size and cand.std() > 5.0:
                img = cand
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(hwnd, hwnd_dc)
    except Exception:  # noqa: BLE001
        img = None
    if img is None:
        import mss
        with mss.mss() as sct:
            mon = {"left": rect["x"], "top": rect["y"],
                   "width": rect["w"], "height": rect["h"]}
            img = cv2.cvtColor(np.array(sct.grab(mon)), cv2.COLOR_BGRA2BGR)
    return img


def detect_knobs(img: np.ndarray) -> list[tuple[int, int, int]]:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    h, w = gray.shape

    # stage 1 (full window): classic Hough on blurred image
    blur = cv2.GaussianBlur(gray, (7, 7), 1.6)
    found = cv2.HoughCircles(
        blur, cv2.HOUGH_GRADIENT, dp=1.05,
        minDist=max(14, min(h, w) // 60),
        param1=90, param2=20,
        minRadius=max(6, min(h, w) // 140),
        maxRadius=max(18, min(h, w) // 40),
    )
    out: list[tuple[int, int, int]] = []
    if found is not None:
        for cx_f, cy_f, r_f in np.around(found[0]):
            cx, cy, r = int(cx_f), int(cy_f), int(r_f)
            ring = gray[max(0, cy - r):cy + r, max(0, cx - r):cx + r]
            if ring.size == 0:
                continue
            center_dark = gray[max(0, cy - 3):cy + 4, max(0, cx - 3):cx + 4].mean()
            if center_dark < ring.mean() + 12:
                out.append((cx, cy, r))

    # stage 2 (center-mixer region ONLY): dark knobs on dark background have
    # subtle rims — a morphological gradient turns those rims into bright
    # circles that Hough finds reliably. Region-limit kills waveform false hits.
    mx0, mx1 = int(w * 0.435), int(w * 0.565)
    my0, my1 = int(h * 0.09), int(h * 0.62)
    mix = gray[my0:my1, mx0:mx1]
    grad = cv2.morphologyEx(mix, cv2.MORPH_GRADIENT,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    grad = cv2.GaussianBlur(grad, (5, 5), 1.2)
    grid = cv2.HoughCircles(
        grad, cv2.HOUGH_GRADIENT, dp=1.0,
        minDist=30, param1=100, param2=14,
        minRadius=10, maxRadius=20,
    )
    if grid is not None:
        for cx_f, cy_f, r_f in np.around(grid[0]):
            cx, cy, r = int(cx_f) + mx0, int(cy_f) + my0, int(r_f)
            if not any(abs(cx - ox) < 8 and abs(cy - oy) < 8 for ox, oy, _ in out):
                out.append((cx, cy, r))
    return out

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="MidiMAT vision snap")
    ap.add_argument("--title", default="Traktor", help="window title substring")
    ap.add_argument("--apply", action="store_true",
                    help="snap circular widgets in layout.json to detections")
    ap.add_argument("--max-snap-dist", type=int, default=90,
                    help="max distance (px) widget->detection to accept a snap")
    ap.add_argument("--import", dest="import_json", metavar="FILE",
                    help="apply VLM boxes JSON (see docs/PROMPT_VLM.md) instead "
                         "of detecting")
    args = ap.parse_args(argv)

    if args.import_json:
        data = json.loads(Path(args.import_json).read_text(encoding="utf-8"))
        layout_path = ROOT / "layout.json"
        layout = json.loads(layout_path.read_text(encoding="utf-8"))
        if "canvas" in data:
            layout["canvas"] = data["canvas"]
        applied = 0
        by_id = {w["id"]: w for w in layout["widgets"]}
        for wid, box in data.get("boxes", {}).items():
            if wid in by_id:
                by_id[wid]["box"] = {k: int(v) for k, v in box.items()}
                applied += 1
                print(f"  IMPORT {wid}: {box}")
            else:
                print(f"  skip unknown id {wid}")
        layout_path.write_text(json.dumps(layout, indent=2) + "\n", encoding="utf-8")
        print(f"imported {applied} boxes; refresh the browser source")
        return 0

    rect = traktor_window_rect(args.title)
    if not rect:
        raise SystemExit(f"no visible window matching {args.title!r}")
    print(f"window: {rect['title']!r} at ({rect['x']},{rect['y']}) "
          f"{rect['w']}x{rect['h']}")
    img = grab(rect)
    knobs = detect_knobs(img)
    print(f"detected {len(knobs)} knob circles")

    preview = img.copy()
    for cx, cy, r in knobs:
        cv2.circle(preview, (cx, cy), r, (0, 255, 128), 2)
        cv2.circle(preview, (cx, cy), 2, (0, 0, 255), 2)
    out_png = ROOT / "vision_preview.png"
    cv2.imwrite(str(out_png), preview)
    print(f"annotated preview: {out_png}")
    (ROOT / "vision_detections.json").write_text(
        json.dumps([{"x": c[0], "y": c[1], "r": c[2]} for c in knobs]),
        encoding="utf-8")

    if not args.apply:
        print("dry run — inspect vision_preview.png, then re-run with --apply")
        return 0

    layout_path = ROOT / "layout.json"
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    layout["canvas"] = {"width": rect["w"], "height": rect["h"]}
    used: set[int] = set()
    for wdg in layout["widgets"]:
        if wdg.get("shape") != "circle":
            continue
        b = wdg["box"]
        cx0, cy0 = b["x"] + b["w"] // 2, b["y"] + b["h"] // 2
        best, bd = None, args.max_snap_dist + 1
        for i, (cx, cy, r) in enumerate(knobs):
            if i in used:
                continue
            d = ((cx - cx0) ** 2 + (cy - cy0) ** 2) ** 0.5
            if d < bd:
                best, bd = i, d
        if best is None or bd > args.max_snap_dist:
            print(f"  MISS {wdg['id']}: nearest {bd:.0f}px > threshold")
            continue
        used.add(best)
        cx, cy, r = knobs[best]
        size = 2 * r + 10
        wdg["box"] = {"x": cx - size // 2, "y": cy - size // 2,
                      "w": size, "h": size}
        print(f"  SNAP {wdg['id']:14s} -> ({cx},{cy}) r={r} (moved {bd:.0f}px)")
    layout_path.write_text(json.dumps(layout, indent=2) + "\n", encoding="utf-8")
    print(f"canvas set to window size {rect['w']}x{rect['h']}; layout saved")
    print("-> refresh the browser source (same scene rect as the capture!)")
    return 0


if __name__ == "__main__":
    sys.exit(main())