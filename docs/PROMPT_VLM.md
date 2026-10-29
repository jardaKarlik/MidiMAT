# Vision-model prompt — locate Traktor controls (Nano Banana / Gemini / GPT-4V / Claude)

Purpose: paste this prompt + a Traktor screenshot into any image-understanding model and
get back machine-readable boxes that `vision_snap --import` writes into `layout.json`.
This is the Tier-C "vision bootstrapper" from `docs/ARCHITECTURE.md`.

## Workflow

1. Run `python -m sidecar.vision_snap` — it saves `vision_preview.png` (annotated) and
   writes `vision_detections.json`. Use the raw frame as the model input (or take any
   screenshot of the Traktor window).
2. Paste the prompt below + attach the image.
3. Save the model's JSON reply to `vlm_boxes.json`.
4. `python -m sidecar.vision_snap --import vlm_boxes.json` → layout updated → refresh
   the OBS/Streamlabs browser source.

## Prompt

```text
You are a precise UI-annotation engine. Attached is a screenshot of the Traktor Pro 4
DJ software interface (4-deck Extended layout). Locate the controls listed below and
return their bounding boxes.

Coordinates must be in PIXELS of the attached image (origin = top-left corner,
x grows right, y grows down). Report the image dimensions you used in "canvas".

Controls to find (id -> what it looks like):
- z1_eq_hi_a: "HI" EQ knob of the LEFT channel strip (label HI near top of center mixer)
- z1_eq_mid_a: "MID" EQ knob directly below z1_eq_hi_a (left side of center mixer)
- z1_eq_lo_a: "LO" EQ knob directly below z1_eq_mid_a
- z1_fltr_a: "FLTR" knob of the leftmost full channel strip (GAIN/FLTR/KEY/PAN column)
- z1_eq_hi_b: "HI" EQ knob of the RIGHT side of the center mixer (inner right column)
- z1_eq_mid_b: "MID" EQ knob below z1_eq_hi_b
- z1_eq_lo_b: "LO" EQ knob below z1_eq_mid_b
- z1_fltr_b: "FLTR" knob of the rightmost full channel strip
- z1_fader_a: vertical channel fader slot of the LEFT channel pair (long thin rectangle)
- z1_fader_b: vertical channel fader slot of the RIGHT channel pair
- z1_xfade: horizontal crossfader slot at the bottom center of the mixer
- fx1_size, fx1_drywet: the two large FX knobs in the top-left FX unit (optional)
- master_gain: the MAIN/BOOST knob at the top center (optional)

Rules:
- knobs -> circle boxes tightly enclosing the knob (w == h)
- faders/crossfader -> rectangles enclosing the full travel slot
- if a control is not visible, omit it (never guess coordinates)

Return ONLY valid JSON, no markdown fences, no commentary:

{
  "canvas": {"width": <image width>, "height": <image height>},
  "boxes": {
    "<id>": {"x": <int>, "y": <int>, "w": <int>, "h": <int>},
    ...
  }
}
```

## Import format (`vlm_boxes.json`)

Exactly the JSON above. `--import` merges `boxes` into `layout.json` (ids that exist),
sets `canvas` when present, and keeps the widgets' existing shapes.