import json
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "layout.json"
d = json.loads(p.read_text(encoding="utf-8"))
# scene canvas = screen (1920x1080); Traktor content = top 988px;
# the free 92px band (989..1079) is the info bar (HUD card + user's widgets).
d["canvas"] = {"width": 1920, "height": 1080}
d["hud"]["height"] = 76
d["hud"]["margin_bottom"] = 14
d["_positions"] = (
    "Vision-snapped 2026-10-29 from CLIENT-area PrintWindow capture "
    "(Traktor content 1920x988 at scene 0,0). Info band y>=989 reserved for HUD. "
    "Z1: EQ cols x=915/980 rows y=158/216/278, FLTR x=860/1052 y=240, "
    "faders x=887/1020 y=300-450, xfade y=586."
)
boxes = {
    "z1_eq_hi_a": ("circle", 892, 135, 46, 46),
    "z1_eq_mid_a": ("circle", 892, 193, 46, 46),
    "z1_eq_lo_a": ("circle", 892, 255, 46, 46),
    "z1_fltr_a": ("circle", 837, 217, 46, 46),
    "z1_eq_hi_b": ("circle", 957, 135, 46, 46),
    "z1_eq_mid_b": ("circle", 957, 193, 46, 46),
    "z1_eq_lo_b": ("circle", 957, 255, 46, 46),
    "z1_fltr_b": ("circle", 1029, 217, 46, 46),
    "z1_fader_a": ("rect", 875, 300, 24, 150),
    "z1_fader_b": ("rect", 1008, 300, 24, 150),
    "z1_xfade": ("rect", 847, 573, 220, 26),
}
for w in d["widgets"]:
    if w["id"] in boxes:
        s, x, y, ww, hh = boxes[w["id"]]
        w["box"] = {"x": x, "y": y, "w": ww, "h": hh}
    elif w["id"].startswith(("fx1_", "deck_a_", "master_")):
        w["box"] = {"x": 40, "y": 1120, "w": 40, "h": 40}  # off-canvas parking
p.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
print("layout applied: canvas 1920x1080, 11 Z1 widgets snapped, HUD -> info band")