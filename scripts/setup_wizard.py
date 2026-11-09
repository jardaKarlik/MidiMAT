"""Guided Traktor out-mapping setup -> mapping/controls.csv

For each physical control the wizard tells you
  1. which entry to pick in Controller Manager  (Add Out... > menu path)
  2. which Assignment to set                      (Deck A / FX Unit 1 / Global)
  3. which MIDI message to pick in the dropdown   (next to "Learn": Ch01 > CC > 005)
then asks you to move the physical control, listens on the loopMIDI port, verifies
that exactly that CC arrives, and writes the row into mapping/controls.csv.

Usage (Traktor running, Generic MIDI device with Out-Port = loopMIDI):
    .\\.venv\\Scripts\\python.exe scripts\\setup_wizard.py               # z1 profile
    .\\.venv\\Scripts\\python.exe scripts\\setup_wizard.py --profile z1cd  # mixer, decks C/D
    .\\.venv\\Scripts\\python.exe scripts\\setup_wizard.py --profile fx    # FX units 1-4 (X1s)
    .\\.venv\\Scripts\\python.exe scripts\\setup_wizard.py --profile decks # play/cue/sync/loop A-D
    .\\.venv\\Scripts\\python.exe scripts\\setup_wizard.py --profile browser # browse/load
    .\\.venv\\Scripts\\python.exe scripts\\setup_wizard.py --profile all --redo
    .\\.venv\\Scripts\\python.exe scripts\\setup_wizard.py --list
Then:  .\\.venv\\Scripts\\python.exe scripts\\build_maps.py

Menu names follow the Traktor Pro manual ("Assignable MIDI Controls"). Traktor's
names are not the labels printed on the hardware - the HINT line explains each.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import queue
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "mapping" / "controls.csv"
FIELDS = ["id", "physical", "traktor_out", "channel", "cc", "label", "deck", "shape",
          "x", "y", "w", "h", "verified"]

# --- catalog -------------------------------------------------------------------
# (id, physical control, Add Out menu path, assignment, HUD label, deck, kind, hint)
# kind: "knob" (continuous, sweep it) | "button" (press it a few times)
FLTR_HINT = ("there is NO 'Filter' entry: in Traktor 3/4 the channel FLTR knob is "
             "'Mixer FX Adjust' (Filter is one of the Mixer FX)")


def _mixer_channel(d: str, side: str) -> list[tuple]:
    lo = d.lower()
    return [
        (f"z1_eq_hi_{lo}", f"Z1 {side} HI knob", "Mixer > EQ > High Adjust", f"Deck {d}",
         "EQ High", d, "knob", ""),
        (f"z1_eq_mid_{lo}", f"Z1 {side} MID knob", "Mixer > EQ > Mid Adjust", f"Deck {d}",
         "EQ Mid", d, "knob", ""),
        (f"z1_eq_lo_{lo}", f"Z1 {side} LOW knob", "Mixer > EQ > Low Adjust", f"Deck {d}",
         "EQ Low", d, "knob", ""),
        (f"z1_fltr_{lo}", f"Z1 {side} FILTER knob", "Mixer > Mixer FX Adjust", f"Deck {d}",
         "Filter", d, "knob", FLTR_HINT),
        (f"z1_gain_{lo}", f"Z1 {side} GAIN knob (skip if your Z1 has none)",
         "Mixer > Gain Adjust", f"Deck {d}", "Gain", d, "knob", ""),
        (f"z1_fader_{lo}", f"Z1 {side} channel fader", "Mixer > Volume Adjust", f"Deck {d}",
         "Volume", d, "knob", "'Volume Adjust' = the channel fader"),
        (f"z1_cue_{lo}", f"Z1 {side} CUE (headphone) button", "Mixer > Monitor Cue On",
         f"Deck {d}", "Headphone Cue", d, "button", "'Monitor Cue' = headphone cue"),
        (f"z1_mfx_on_{lo}", f"Z1 {side} round FX on/off button",
         "Mixer > Mixer FX On", f"Deck {d}", "Filter On", d, "button", FLTR_HINT),
    ]


def _fx_unit(n: int, unit_label: str) -> list[tuple]:
    rows = [(f"fx{n}_drywet", f"{unit_label} DRY/WET knob (knob 1)", "FX Unit > Dry/Wet Adjust",
             f"FX Unit {n}", f"FX{n} Dry/Wet", "FX", "knob",
             "in Group mode knob 1 is Dry/Wet; in Single mode it may be Knob 1")]
    for k in (1, 2, 3):
        rows.append((f"fx{n}_knob{k}", f"{unit_label} knob {k + 1}", f"FX Unit > Knob {k}",
                     f"FX Unit {n}", f"FX{n} Knob {k}", "FX", "knob",
                     "Traktor numbers the effect knobs 1-3 AFTER the Dry/Wet knob"))
    rows.append((f"fx{n}_on", f"{unit_label} FX ON button (button 1)", "FX Unit > Unit On",
                 f"FX Unit {n}", f"FX{n} On", "FX", "button", ""))
    for k in (1, 2, 3):
        rows.append((f"fx{n}_btn{k}", f"{unit_label} button {k + 1}", f"FX Unit > Button {k}",
                     f"FX Unit {n}", f"FX{n} Button {k}", "FX", "button",
                     "Traktor numbers the effect buttons 1-3 AFTER the Unit On button"))
    return rows


def _deck(d: str) -> list[tuple]:
    lo = d.lower()
    return [
        (f"deck_{lo}_play", f"Deck {d} PLAY button", "Deck Common > Play/Pause", f"Deck {d}",
         "Play", d, "button", ""),
        (f"deck_{lo}_cue", f"Deck {d} CUE button", "Deck Common > Cue", f"Deck {d}",
         "Cue", d, "button", ""),
        (f"deck_{lo}_sync", f"Deck {d} SYNC button", "Deck Common > Sync On", f"Deck {d}",
         "Sync", d, "button", ""),
        (f"deck_{lo}_loop", f"Deck {d} loop ACTIVE (push loop encoder)",
         "Deck Common > Loop > Loop Active On", f"Deck {d}", "Loop On", d, "button", ""),
        (f"deck_{lo}_loopsize", f"Deck {d} loop SIZE (turn loop encoder)",
         "Deck Common > Loop > Loop Size Selector", f"Deck {d}", "Loop Size", d, "knob",
         "steps, not a sweep - turn a few clicks each way"),
    ]


CMD_HINT = ("browser actions are commands, not values - Traktor may send NOTHING for "
            "them. If the test stays silent, press s (the 'Deck is Loaded' rows still "
            "catch track loads)")
BROWSER = [
    ("br_list_scroll", "X1 BROWSE encoder - turn (track list up/down)",
     "Browser > List > Select Up/Down", "Global (no deck)", "Browse", "AB", "button",
     CMD_HINT),
    ("br_tree_scroll", "X1 BROWSE encoder - SHIFT+turn (folder tree up/down; skip if unused)",
     "Browser > Tree > Select Up/Down", "Global (no deck)", "Browse Folders", "AB",
     "button", CMD_HINT),
    ("br_tree_expand", "X1 BROWSE encoder - push / SHIFT+push (open/close folder; skip if "
     "unused)", "Browser > Tree > Select Expand/Collapse", "Global (no deck)",
     "Open Folder", "AB", "button", CMD_HINT),
    ("br_only_browser", "button that maximizes the browser (skip if unused)",
     "Layout > Only Browser On", "Global (no deck)", "Browser View", "AB", "button", ""),
] + [
    (f"deck_{d.lower()}_load", f"LOAD button / encoder push for Deck {d}",
     "Deck Common > Load Selected", f"Deck {d}", "Load Track", d, "button", CMD_HINT)
    for d in "ABCD"
] + [
    (f"deck_{d.lower()}_loaded", f"load any track into Deck {d} (any way: X1, mouse...)",
     "Deck Common > Deck is Loaded", f"Deck {d}", "Track Loaded", d, "button",
     "Out-only signal: fires when a track lands on the deck - load 2 tracks in a row "
     "(or unload + load) so the wizard sees a change")
    for d in "ABCD"
]
MIXER_GLOBAL = [
    ("z1_xfade", "Z1 crossfader", "Mixer > X-Fader > Position", "Global (no deck)",
     "Crossfader", "AB", "knob", "Assignment may be greyed out - that's fine"),
    ("z1_cue_mix", "Z1 CUE MIX knob (skip if none)", "Mixer > Monitor Mix Adjust",
     "Global (no deck)", "Cue Mix", "AB", "knob", "'Monitor' = headphones"),
    ("z1_cue_vol", "Z1 CUE VOL knob (skip if none)", "Mixer > Monitor Volume Adjust",
     "Global (no deck)", "Cue Volume", "AB", "knob", ""),
    ("z1_main", "Z1 MAIN/MASTER knob (skip if none)", "Mixer > Master Volume Adjust",
     "Global (no deck)", "Master Volume", "AB", "knob", ""),
    ("z1_mfx_sel", "Z1 center FX select buttons 1-4 (+ the wide button below them)",
     "Mixer > Mixer FX Selector", "Deck A", "Mixer FX", "AB", "button",
     "press 1,2,3,4 and the wide button in turn - each sends a different value. If "
     "nothing arrives with Deck A, the selector may be global: try another Assignment"),
]
SWITCHED = "(Z1 deck switch ON: {side} channel = Deck {d})"


def _mixer_cd() -> list[tuple]:
    rows = []
    for d, side in (("C", "LEFT"), ("D", "RIGHT")):
        for r in _mixer_channel(d, side):
            rows.append((r[0], f"{r[1]} {SWITCHED.format(side=side, d=d)}", *r[2:]))
    return rows


PROFILES: dict[str, list[tuple]] = {
    # Traktor out-mappings are per DECK / FX UNIT, not per device: whichever
    # controller (or the mouse) moves Deck C's EQ, Traktor reports Deck C's EQ.
    # => Z1 deck switching and the two X1 MK3s need no tracking in MidiMAT.
    "z1": _mixer_channel("A", "LEFT") + _mixer_channel("B", "RIGHT") + MIXER_GLOBAL,
    "z1cd": _mixer_cd(),
    "fx": (_fx_unit(1, "X1 FX section driving FX Unit 1")
           + _fx_unit(2, "X1 FX section driving FX Unit 2")
           + _fx_unit(3, "X1 FX section driving FX Unit 3")
           + _fx_unit(4, "X1 FX section driving FX Unit 4")),
    "decks": _deck("A") + _deck("B") + _deck("C") + _deck("D"),
    "browser": BROWSER,
}
PROFILES["x1"] = PROFILES["fx"] + PROFILES["decks"]
PROFILES["all"] = PROFILES["z1"] + PROFILES["z1cd"] + PROFILES["x1"] + BROWSER


def default_shape(cid: str, kind: str = "") -> str:
    """circle = real round knob; rect = fader/slider/button; hud = card only
    (events with no on-screen spot, e.g. 'track loaded', browser commands)."""
    if cid.endswith("_loaded") or cid.startswith("br_"):
        return "hud"
    if ("fader" in cid or cid == "z1_xfade" or "loopsize" in cid
            or re.fullmatch(r"fx\d_knob\d", cid)):  # Group-mode FX knobs 1-3 are sliders
        return "rect"
    if kind == "button":
        return "rect"
    return "circle"


# --- csv -------------------------------------------------------------------------
def load_rows() -> dict[str, dict]:
    if not CSV_PATH.exists():
        return {}
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        return {r["id"]: {k: (r.get(k) or "") for k in FIELDS} for r in csv.DictReader(f)}


def save_rows(rows: dict[str, dict]) -> None:
    CSV_PATH.parent.mkdir(exist_ok=True)
    tmp = CSV_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows.values())
    tmp.replace(CSV_PATH)  # atomic: Ctrl+C mid-write can't corrupt the sheet


def used_keys(rows: dict[str, dict], exclude: str | None = None) -> set[tuple[int, int]]:
    out = set()
    for r in rows.values():
        if r["id"] != exclude and r["cc"].strip():
            out.add((int(r["channel"] or 1), int(r["cc"])))
    return out


def next_free(rows: dict[str, dict], exclude: str) -> tuple[int, int]:
    used = used_keys(rows, exclude)
    for ch in range(1, 17):
        for cc in range(1, 128):
            if (ch, cc) not in used:
                return ch, cc
    raise SystemExit("all 16x127 CCs used?!")


# --- midi ------------------------------------------------------------------------
class Listener:
    def __init__(self, hint: str):
        import mido
        names = [n for n in mido.get_input_names() if hint.lower() in n.lower()]
        if not names:
            raise SystemExit(f"no MIDI input matching {hint!r}. Visible: "
                             f"{mido.get_input_names()} - is loopMIDI running?")
        self.q: "queue.Queue[tuple[int,int,int,float]]" = queue.Queue()
        self.port = mido.open_input(names[0], callback=self._cb)
        self.name = names[0]

    def _cb(self, m) -> None:
        if m.type == "control_change":
            self.q.put((m.channel + 1, m.control, m.value, time.time()))
        elif m.type in ("note_on", "note_off"):  # someone picked Note in the dropdown
            self.q.put((m.channel + 1, 1000 + m.note,
                        m.velocity if m.type == "note_on" else 0, time.time()))

    def drain(self) -> None:
        while not self.q.empty():
            self.q.get_nowait()

    def collect(self, seconds: float, stop_after_hit=None) -> dict[tuple[int, int], list[int]]:
        """Gather messages for `seconds` -> {(ch, cc): [values...]}."""
        seen: dict[tuple[int, int], list[int]] = {}
        end = time.time() + seconds
        while time.time() < end:
            try:
                ch, cc, val, _ = self.q.get(timeout=0.1)
            except queue.Empty:
                continue
            seen.setdefault((ch, cc), []).append(val)
            if stop_after_hit and stop_after_hit(seen):
                end = min(end, time.time() + 0.8)  # grab the tail of the gesture
        return seen


def fmt_key(ch: int, cc: int) -> str:
    return f"Ch{ch:02d} > Note > {cc - 1000}" if cc >= 1000 else f"Ch{ch:02d} > CC > {cc:03d}"


def good_enough(kind: str, vals: list[int]) -> bool:
    if kind == "button":
        return len(set(vals)) >= 2 or len(vals) >= 2
    return len(vals) >= 3 and (max(vals) - min(vals)) >= 10


def ask(prompt: str, choices: str) -> str:
    while True:
        a = input(prompt).strip().lower()
        if a == "" and "" in choices.split("/"):
            return ""
        if a in choices.split("/"):
            return a
        print(f"   please answer one of: {choices.replace('/', ', ') or 'Enter'}")


# --- wizard ----------------------------------------------------------------------
def run_step(lis: Listener, rows: dict[str, dict], step: tuple, i: int, n: int) -> str:
    cid, physical, menu, assign, label, deck, kind, hint = step
    row = rows.get(cid) or {k: "" for k in FIELDS}
    if row["cc"].strip():
        ch, cc = int(row["channel"] or 1), int(row["cc"])
        if (ch, cc) in used_keys(rows, cid):
            ch, cc = next_free(rows, cid)
    else:
        ch, cc = next_free(rows, cid)

    print("\n" + "=" * 72)
    print(f"[{i}/{n}]  {physical}")
    print("-" * 72)
    print("  In Controller Manager (your Generic MIDI / loopMIDI device):")
    print(f"    1. Add Out...  >  {menu}")
    print(f"    2. Assignment  :  {assign}")
    print(f"    3. Mapped to   :  dropdown next to 'Learn'  >  {fmt_key(ch, cc)}")
    if hint:
        print(f"    HINT: {hint}")
    a = ask("  Enter = done, s = skip, q = quit > ", "/s/q")
    if a in ("s", "q"):
        return a

    while True:
        time.sleep(0.6)  # Traktor re-sends all out states after table edits
        lis.drain()
        verb = "SWEEP it fully both ways" if kind == "knob" else "PRESS it 3-4 times"
        print(f"  >> Now {verb}: {physical}   (listening 12 s on {lis.name})")
        seen = lis.collect(12, stop_after_hit=lambda s: good_enough(kind, s.get((ch, cc), [])))
        hit = seen.get((ch, cc), [])
        others = {k: v for k, v in seen.items() if k != (ch, cc) and len(v) >= 2}

        if good_enough(kind, hit):
            print(f"  OK  {fmt_key(ch, cc)}  received {len(hit)} msgs "
                  f"(values {min(hit)}..{max(hit)})")
            break
        if others:
            best = max(others, key=lambda k: len(others[k]))
            vals = others[best]
            print(f"  ?   expected {fmt_key(ch, cc)} but got {fmt_key(*best)} "
                  f"({len(vals)} msgs, {min(vals)}..{max(vals)})")
            if best in used_keys(rows, cid):
                owner = next(r["id"] for r in rows.values()
                             if r["cc"] and (int(r["channel"] or 1), int(r["cc"])) == best)
                print(f"      that message already belongs to '{owner}' - the dropdown "
                      f"probably still has the old value, fix it and retry")
            elif ask("      use that one instead? (y/n) > ", "y/n") == "y":
                ch, cc = best
                break
        elif hit:
            print(f"  ~   got {len(hit)} msg(s) on {fmt_key(ch, cc)} but too little movement"
                  f" ({hit}) - move it more")
        else:
            print("  X   nothing received. Check, in this order:")
            print("      - 'Mapped to' really shows " + fmt_key(ch, cc))
            print(f"      - Assignment is {assign} (not 'Device Target' / Focus)")
            print("      - move the SAME control on screen with the MOUSE: if that sends,")
            print("        Traktor works and your hardware drives a different target")
            print("        (e.g. Deck C instead of A, FX Unit 3 instead of 1) -> change Assignment")
            print("      - wrong menu entry: Traktor names differ from hardware labels")
        a = ask("  r = retry, s = skip, q = quit > ", "r/s/q")
        if a in ("s", "q"):
            return a

    row.update({"id": cid, "physical": physical, "traktor_out": f"{menu} [{assign}]",
                "channel": str(ch), "cc": str(cc) if cc < 1000 else "",
                "label": row["label"] or label, "deck": row["deck"] or deck,
                "shape": row["shape"] or default_shape(cid, kind),
                "verified": dt.date.today().isoformat()})
    if cc >= 1000:
        print("  !   Note messages aren't supported by the overlay yet - pick CC instead")
        return "r"
    rows[cid] = row
    save_rows(rows)
    print(f"  saved -> {CSV_PATH.relative_to(ROOT)}")
    return "ok"


def main() -> int:
    ap = argparse.ArgumentParser(description="Guided Traktor out-mapping setup")
    ap.add_argument("--profile", choices=sorted(PROFILES), default="z1")
    ap.add_argument("--port", default="MidiMAT", help="MIDI input substring")
    ap.add_argument("--redo", action="store_true", help="re-test already verified rows")
    ap.add_argument("--only", nargs="+", metavar="ID", help="just these control ids")
    ap.add_argument("--list", action="store_true", help="print the plan and exit")
    ap.add_argument("--fix-shapes", action="store_true",
                    help="reset every row's shape to the default rule (circle/rect/hud)")
    args = ap.parse_args()

    steps = PROFILES[args.profile]
    if args.only:
        steps = [s for s in steps if s[0] in args.only]
    rows = load_rows()
    todo = [s for s in steps if args.redo or not rows.get(s[0], {}).get("verified")]

    if args.fix_shapes:
        kinds = {st[0]: st[6] for st in PROFILES["all"]}
        n = 0
        for cid, r in rows.items():
            want = default_shape(cid, kinds.get(cid, ""))
            if r["shape"] != want:
                print(f"  {cid:18s} {r['shape'] or '-':6s} -> {want}")
                r["shape"] = want
                n += 1
        save_rows(rows)
        print(f"{n} shape(s) fixed. Now: scripts\\build_maps.py (or Save in the editor)")
        return 0
    if args.list:
        for s in steps:
            r = rows.get(s[0], {})
            st = (f"{fmt_key(int(r['channel'] or 1), int(r['cc']))} verified {r['verified']}"
                  if r.get("verified") else "todo")
            print(f"  {s[0]:18s} {s[1]:44s} {s[2]:38s} [{s[3]}]  {st}")
        return 0
    if not todo:
        print("everything in this profile is verified (use --redo to re-test)")
        return 0

    print(__doc__.split("Usage")[0].strip())
    print(f"\nprofile {args.profile}: {len(todo)} control(s) to set up. "
          "Ctrl+C anytime - progress is saved after each control.")
    print("TIP: X1 MK3 sleeps - press any button on it before testing its knobs.")
    lis = Listener(args.port)
    done = 0
    try:
        for i, step in enumerate(todo, 1):
            while True:
                res = run_step(lis, rows, step, i, len(todo))
                if res != "r":
                    break
            if res == "q":
                break
            if res == "ok":
                done += 1
    except KeyboardInterrupt:
        print("\ninterrupted")
    finally:
        lis.port.close()
    print(f"\n{done} control(s) verified and saved. Next:\n"
          "  .\\.venv\\Scripts\\python.exe scripts\\build_maps.py\n"
          "  .\\scripts\\run.ps1 --midi --no-demo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
