# AI-assisted box placement

Goal: the placer editor proposes boxes, a human reviews (Enter / Esc / drag). Never
fully automatic — vision models are good at *which*, weak at *exact pixels*.

## Pipeline (`sidecar/suggest.py`)

| Stage | What | Tech | Needs |
|---|---|---|---|
| 1 detect | find every knob / slider / button, exact edges, no names | OpenCV Hough circles + rectangle contours (later: our YOLO model) | nothing |
| 2 mark | draw numbered tags on candidates ("Set-of-Mark") | OpenCV | nothing |
| 3 identify | "which tag is Deck C MID?" → tag number, or approximate `box_2d` | vision LLM via OpenRouter | `OPENROUTER_API_KEY` |
| 4 snap | approximate boxes jump to the nearest real candidate | geometry | nothing |

Model: `MIDIMAT_VLM_MODEL` (default `qwen/qwen2.5-vl-72b-instruct`; try
`google/gemini-2.5-flash`). Nano Banana is an image *generator* — not useful here.

## Findings so far (2026-11-05, real 1920×1080 Traktor screenshot)

- OpenCV detector: knobs found (centre within ~5–10 px) but ~850–970 candidates of
  noise (text, waveforms, status dots); flat text buttons and thin fader slots missed.
- Full pipeline with the vision model: **0/65** — with ~1000 tiny overlapping tags the
  model cannot read the numbers. Set-of-Mark only works with a clean, small candidate set.
- Pitfall: never evaluate on `*_eval.png` / `*_marks.png` (tool output with boxes drawn on).
- ⇒ Next: train YOLO on our own boxes (clean candidates), then assign identities by
  geometry against the existing layout (free, offline); vision model only for brand-new
  layouts, on cropped regions with few tags.

## First trained detector (2026-11-05)

yolo11n, 17 screenshots, 150 epochs, CPU (Ryzen 5 4500) 52 min. Validation P 0.985 / R 0.593.
On an **unseen** screenshot (`eval_suggest.py`, conf 0.10):

| | OpenCV | YOLO |
|---|---|---|
| centre-hit recall | ~14 % | **96 % (85/89)** |
| median centre error | ~10 px | **1.0 px** |
| candidates | 850–970 | **85** |

Misses: FX ON buttons classified as *knob* (fx1/2/4_on), deck_a_sync. Fix: training-only
boxes for unmapped look-alikes + more FX-on examples. Inference runs on CPU (~0.1 s);
GTX 10xx (sm_61) is unsupported by cu128 torch builds (cu126 still supports it).

**Auto re-fit** (`sidecar/refit.py`, editor 🎯 *Detect & re-fit*): detect → vote for
(scale, offset) over all same-kind template/detection pairs → ICP refine (per-axis least
squares) → snap each box onto its detection (user's box size kept, centred on the
detection) or keep the mapped box when nothing matched ("fit"). Offline, no vision model.
`scripts/test_refit.py`: shifts up to 400 px, scales 0.67–1.25×, 8 % missed + 12 spurious
+ 4 % misclassified detections → transform within 0.01 / 1 px, 100 % of boxes within 3 px.
CLI: `python -m sidecar.refit shot.png`.

## Use it

```powershell
$env:OPENROUTER_API_KEY = "sk-or-..."      # current shell only; or a user env var. Never commit it.
.\scripts\run.ps1 --midi --no-demo
# editor -> paste OBS screenshot -> ✨ Suggest (AI) -> Enter accept / Esc reject / drag -> Ctrl+S
```

## Measure it (your hand-placed boxes are ground truth)

```powershell
.\.venv\Scripts\python.exe scripts\eval_suggest.py docs\traktor-ui\screens\traktor.png          # detector only, free
.\.venv\Scripts\python.exe scripts\eval_suggest.py docs\traktor-ui\screens\traktor.png --full   # + vision model
```

Reports detector recall, % correct / near / wrong, and writes `*_eval.png`
(green = yours, red = suggestion).

## Train our own detector (learning track)

Replaces stage 1 with a model that *learned* what Traktor controls look like.

1. **Collect** 15–30 OBS screenshots, same Traktor layout & size as your placement:
   different tracks, FX on/off, playing/paused, loops active, decks C/D switched.
2. **Export** — your placed boxes become labels for every screenshot:
   `python scripts\export_yolo.py docs\traktor-ui\screens\*.png`
   → `dataset/yolo/` (YOLO format: `class cx cy w h`, normalised 0–1) + `data.yaml`.
3. **Train** (GPU ~5 min; CPU ~30–60 min for the nano model) — one command does export + train
   with UI-safe augmentation (no flips / hue shifts) and installs the result:
   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements-train.txt   # once, pulls torch
   .\.venv\Scripts\python.exe scripts\train_yolo.py docs\traktor-ui\screens\*.png            # CPU
   .\.venv\Scripts\python.exe scripts\train_yolo.py docs\traktor-ui\screens\*.png --device 0 # NVIDIA GPU
   ```
   Watch `runs/detect/train/results.png`: loss going down, mAP50 going up.
4. **Evaluate** on a screenshot it never saw (`yolo detect predict model=runs/detect/train/weights/best.pt source=new.png`).
5. **Plug in**: automatic — `models/traktor_yolo.pt` exists ⇒ `suggest` and `eval_suggest`
   use YOLO. Compare: `$env:MIDIMAT_DETECTOR="opencv"` vs `"yolo"` on the same screenshot.

Caveat: widgets you never boxed are treated as "background" — box more of the UI for a
cleaner detector.
