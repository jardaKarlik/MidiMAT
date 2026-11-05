"""Suggest widget boxes for a Traktor screenshot: detect -> mark -> ask a VLM -> snap.

Pipeline (each stage is replaceable; the editor always shows results for human review):

  1. detect   - classic OpenCV finds candidate knobs (circles) and sliders/buttons
                (rectangles): exact edges, but no names. A trained YOLO model can
                replace this stage later (scripts/export_yolo.py builds its dataset).
  2. mark     - draw numbered tags on the candidates ("Set-of-Mark" prompting):
                vision models are bad at pixel coordinates but good at picking a
                labelled option.
  3. identify - ask a vision LLM via OpenRouter "which mark is <control>?"; if no
                mark fits it may answer an approximate box_2d instead.
  4. snap     - approximate boxes are snapped to the nearest candidate of the right
                kind, so suggestions land on real edges.

Config (environment, never in the repo):
  OPENROUTER_API_KEY   required for stage 3
  MIDIMAT_VLM_MODEL    default qwen/qwen2.5-vl-72b-instruct (any OpenRouter vision model)

CLI:
  python -m sidecar.suggest detect shot.png             # stage 1+2 only, no key needed
  python -m sidecar.suggest suggest shot.png [--ids a b] # full pipeline -> JSON
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "qwen/qwen2.5-vl-72b-instruct"


# --- 1. detect ---------------------------------------------------------------------
def _iou(a: dict, b: dict) -> float:
    x1, y1 = max(a["x"], b["x"]), max(a["y"], b["y"])
    x2 = min(a["x"] + a["w"], b["x"] + b["w"])
    y2 = min(a["y"] + a["h"], b["y"] + b["h"])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    union = a["w"] * a["h"] + b["w"] * b["h"] - inter
    return inter / union if union else 0.0


def _nms(cands: list[dict], thr: float = 0.35) -> list[dict]:
    keep: list[dict] = []
    for c in sorted(cands, key=lambda c: -c["score"]):
        if all(_iou(c, k) < thr for k in keep):
            keep.append(c)
    return keep


def detect_candidates(img: np.ndarray) -> list[dict]:
    """-> [{x,y,w,h,kind: knob|slider|button, score}] in image pixels."""
    h_img, w_img = img.shape[:2]
    scale = h_img / 1080.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cands: list[dict] = []

    # knobs: Traktor knobs are round with a lighter rim/indicator on dark UI
    blur = cv2.medianBlur(gray, 3)
    rmin, rmax = max(6, int(9 * scale)), int(30 * scale)
    circles = cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, dp=1.2, minDist=rmin * 2,
                               param1=90, param2=20, minRadius=rmin, maxRadius=rmax)
    if circles is not None:
        for x, y, r in np.round(circles[0]).astype(int):
            cands.append({"x": int(x - r), "y": int(y - r), "w": int(2 * r), "h": int(2 * r),
                          "kind": "knob", "score": 1.0})

    # sliders / buttons: closed rectangular contours on the edge map
    edges = cv2.Canny(blur, 40, 120)
    edges = cv2.dilate(edges, np.ones((2, 2), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    min_side, max_area = max(6, int(8 * scale)), 0.02 * w_img * h_img
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w < min_side or h < min_side or w * h > max_area:
            continue
        rectness = cv2.contourArea(c) / float(w * h)
        if rectness < 0.6:
            continue
        aspect = max(w, h) / min(w, h)
        kind = "slider" if aspect >= 3 else "button"
        if kind == "button" and (w > 160 * scale or h > 60 * scale):
            continue
        cands.append({"x": x, "y": y, "w": w, "h": h, "kind": kind,
                      "score": 0.5 + 0.5 * rectness})
    out = _nms(cands)
    out.sort(key=lambda c: (c["y"] // max(1, int(20 * scale)), c["x"]))  # reading order
    for i, c in enumerate(out, 1):
        c["mark"] = i
    return out


# --- 2. mark -----------------------------------------------------------------------
def render_marks(img: np.ndarray, cands: list[dict]) -> np.ndarray:
    out = img.copy()
    colors = {"knob": (255, 200, 40), "slider": (60, 255, 120), "button": (80, 160, 255)}
    for c in cands:
        col = colors.get(c["kind"], (255, 255, 255))
        cv2.rectangle(out, (c["x"], c["y"]), (c["x"] + c["w"], c["y"] + c["h"]), col, 1)
        tag = str(c["mark"])
        (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
        tx, ty = c["x"], max(th + 2, c["y"] - 2)
        cv2.rectangle(out, (tx, ty - th - 2), (tx + tw + 2, ty + 1), (0, 0, 0), -1)
        cv2.putText(out, tag, (tx + 1, ty - 1), cv2.FONT_HERSHEY_SIMPLEX, 0.4, col, 1,
                    cv2.LINE_AA)
    return out


def _png_data_url(img: np.ndarray) -> str:
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise RuntimeError("png encode failed")
    return "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode()


# --- 3. identify -------------------------------------------------------------------
PROMPT = """You are locating controls in a screenshot of the Traktor Pro 4 DJ software.
Image 1 is the clean screenshot ({w}x{h} px). Image 2 is the same screenshot with numbered
tags on candidate controls (yellow = round knobs, green = sliders/faders, blue = buttons).

For EACH control below, answer with the tag number that best covers it. If no tag covers
it, give an approximate box instead as "box_2d": [ymin, xmin, ymax, xmax] normalized to
0-1000. If the control is not visible at all, answer null. Never guess a tag that covers a
different control.

Layout hints: 4-deck layout, decks A (top-left), B (top-right), C (bottom-left),
D (bottom-right); the mixer sits in the centre column with one channel strip per deck
(A and C on the left half, B and D on the right half); FX units are in the top bar
(FX unit 1 top-left row, unit 3 below it) as small horizontal sliders after a round
DRY/WET knob.

Controls:
{controls}

Return ONLY JSON, no prose:
{{"<id>": {{"mark": <int>}} | {{"box_2d": [ymin, xmin, ymax, xmax]}} | null, ...}}"""


def _describe(row: dict) -> str:
    deck = row.get("deck") or ""
    where = f"deck/group {deck}" if deck else ""
    return (f'- {row["id"]}: {row.get("label", "")} ({where}; Traktor function: '
            f'{row.get("traktor_out", "")}; expected shape: {row.get("shape", "")})')


def _parse_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"no JSON in model reply: {text[:200]!r}")
    return json.loads(m.group(0))


def ask_vlm(img: np.ndarray, marked: np.ndarray, rows: list[dict],
            model: str | None = None, api_key: str | None = None,
            batch: int = 20, transport=None) -> dict:
    """-> {id: {"mark": n} | {"box_2d": [...]} | None}. `transport` is injectable for tests."""
    api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
    model = model or os.environ.get("MIDIMAT_VLM_MODEL") or DEFAULT_MODEL
    if not api_key and transport is None:
        raise RuntimeError("OPENROUTER_API_KEY is not set (put it in your environment, "
                           "never in the repo)")
    h, w = img.shape[:2]
    clean_url, marked_url = _png_data_url(img), _png_data_url(marked)
    answers: dict = {}
    for i in range(0, len(rows), batch):
        chunk = rows[i:i + batch]
        body = {
            "model": model,
            "temperature": 0,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": PROMPT.format(
                    w=w, h=h, controls="\n".join(_describe(r) for r in chunk))},
                {"type": "image_url", "image_url": {"url": clean_url}},
                {"type": "image_url", "image_url": {"url": marked_url}},
            ]}],
        }
        if transport:
            reply = transport(body)
        else:
            req = urllib.request.Request(
                OPENROUTER_URL, data=json.dumps(body).encode(),
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json",
                         "X-Title": "MidiMAT placer"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                reply = json.loads(resp.read())
        text = reply["choices"][0]["message"]["content"]
        if isinstance(text, list):  # some providers return content parts
            text = "".join(p.get("text", "") for p in text)
        answers.update(_parse_json(text))
    return answers


# --- 4. snap -----------------------------------------------------------------------
SHAPE_KINDS = {"circle": ("knob",), "rect": ("slider", "button")}


def snap(box: dict, cands: list[dict], shape: str, max_dist: float) -> tuple[dict, bool]:
    """Move an approximate box onto the nearest candidate of a compatible kind."""
    kinds = SHAPE_KINDS.get(shape, ("knob", "slider", "button"))
    cx, cy = box["x"] + box["w"] / 2, box["y"] + box["h"] / 2
    best, best_d = None, max_dist
    for c in cands:
        if c["kind"] not in kinds:
            continue
        d = ((c["x"] + c["w"] / 2 - cx) ** 2 + (c["y"] + c["h"] / 2 - cy) ** 2) ** 0.5
        if d < best_d:
            best, best_d = c, d
    if best:
        return {k: best[k] for k in ("x", "y", "w", "h")}, True
    return box, False


def suggest(img: np.ndarray, rows: list[dict], **vlm_kwargs) -> dict:
    """Full pipeline. rows: controls.csv dicts to place. Returns
    {"candidates": n, "suggestions": [{id, x, y, w, h, source, mark?}], "missing": [ids]}."""
    h, w = img.shape[:2]
    cands = detect_candidates(img)
    by_mark = {c["mark"]: c for c in cands}
    answers = ask_vlm(img, render_marks(img, cands), rows, **vlm_kwargs)
    out, missing = [], []
    for r in rows:
        a = answers.get(r["id"])
        if isinstance(a, dict) and isinstance(a.get("mark"), int) and a["mark"] in by_mark:
            c = by_mark[a["mark"]]
            out.append({"id": r["id"], **{k: c[k] for k in ("x", "y", "w", "h")},
                        "source": "mark", "mark": a["mark"]})
        elif isinstance(a, dict) and isinstance(a.get("box_2d"), list) and len(a["box_2d"]) == 4:
            y0, x0, y1, x1 = (float(v) for v in a["box_2d"])
            approx = {"x": x0 / 1000 * w, "y": y0 / 1000 * h,
                      "w": (x1 - x0) / 1000 * w, "h": (y1 - y0) / 1000 * h}
            box, snapped = snap(approx, cands, r.get("shape", ""), max_dist=0.03 * w)
            out.append({"id": r["id"], **{k: int(round(v)) for k, v in box.items()},
                        "source": "box+snap" if snapped else "box"})
        else:
            missing.append(r["id"])
    return {"candidates": len(cands), "suggestions": out, "missing": missing}


def decode_data_url(data_url: str) -> np.ndarray:
    raw = base64.b64decode(data_url.split(",", 1)[1])
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("could not decode image")
    return img


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="MidiMAT box suggestions")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("detect", help="candidates only (no API key) -> *_marks.png")
    d.add_argument("image")
    s = sub.add_parser("suggest", help="full pipeline -> JSON on stdout")
    s.add_argument("image")
    s.add_argument("--ids", nargs="+", help="only these control ids (default: unplaced)")
    s.add_argument("--model")
    args = ap.parse_args(argv)

    img = cv2.imread(args.image)
    if img is None:
        raise SystemExit(f"cannot read {args.image}")
    if args.cmd == "detect":
        cands = detect_candidates(img)
        out = str(Path(args.image).with_name(Path(args.image).stem + "_marks.png"))
        cv2.imwrite(out, render_marks(img, cands))
        kinds = {k: sum(1 for c in cands if c["kind"] == k) for k in ("knob", "slider", "button")}
        print(f"{len(cands)} candidates {kinds} -> {out}")
        return 0

    sys.path.insert(0, str(ROOT / "scripts"))
    import setup_wizard  # noqa: PLC0415
    rows = list(setup_wizard.load_rows().values())
    if args.ids:
        rows = [r for r in rows if r["id"] in args.ids]
    else:
        rows = [r for r in rows if r.get("shape") != "hud" and not r.get("x")]
    print(json.dumps(suggest(img, rows, model=args.model), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
