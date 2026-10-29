import json
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "layout.json"
d = json.loads(p.read_text(encoding="utf-8"))
d["canvas"] = {"width": 1936, "height": 1047}
d["_positions"] = (
    "Snapped by vision_snap 2026-10-29 from occlusion-proof PrintWindow capture "
    "(1936x1047). Grid read from annotated preview: EQ cols x=923/982 "
    "(rows y=235/294/355), FLTR outer strips x=861/1052 y=267, "
    "faders x=893/1019 y=352-490, crossfader y=685."
)
boxes = {
    "z1_eq_hi_a": ("circle", 900, 212, 46, 46),
    "z1_eq_mid_a": ("circle", 900, 271, 46, 46),
    "z1_eq_lo_a": ("circle", 900, 332, 46, 46),
    "z1_fltr_a": ("circle", 838, 244, 46, 46),
    "z1_eq_hi_b": ("circle", 959, 212, 46, 46),
    "z1_eq_mid_b": ("circle", 959, 271, 46, 46),
    "z1_eq_lo_b": ("circle", 959, 332, 46, 46),
    "z1_fltr_b": ("circle", 1029, 244, 46, 46),
    "z1_fader_a": ("rect", 881, 352, 24, 140),
    "z1_fader_b": ("rect", 1007, 352, 24, 140),
    "z1_xfade": ("rect", 860, 672, 200, 26),
}
for w in d["widgets"]:
    if w["id"] in boxes:
        s, x, y, ww, hh = boxes[w["id"]]
        w["box"] = {"x": x, "y": y, "w": ww, "h": hh}
p.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
print("layout snapped: canvas 1936x1047, 11 Z1 widgets placed")