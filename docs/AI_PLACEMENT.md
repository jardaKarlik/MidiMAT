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
3. **Train** (GPU: Colab/Modal ~5 min; CPU: ~30 min for the nano model):
   ```bash
   pip install ultralytics
   yolo detect train data=dataset/yolo/data.yaml model=yolo11n.pt imgsz=1280 epochs=150
   ```
   Watch `runs/detect/train/results.png`: loss going down, mAP50 going up.
4. **Evaluate** on a screenshot it never saw (`yolo detect predict model=runs/detect/train/weights/best.pt source=new.png`).
5. **Plug in**: swap `detect_candidates()` for the YOLO model and re-run `eval_suggest.py`
   to compare against OpenCV.

Caveat: widgets you never boxed are treated as "background" — box more of the UI for a
cleaner detector.
