"""Collect OBS screenshots for detector training.

OBS saves "Screenshot (Source)" images as  <Videos>\\Screenshot YYYY-MM-DD hh-mm-ss.png .
This copies the matching ones into docs/traktor-ui/screens/train/ :
  - only today's by default (--since YYYY-MM-DD / --all to change)
  - only images whose size matches the overlay canvas (layout.json) - a full-scene
    capture or another source would teach the detector wrong positions
  - duplicates (same pixels) skipped

    .\\.venv\\Scripts\\python.exe scripts\\collect_screens.py
    .\\.venv\\Scripts\\python.exe scripts\\collect_screens.py --since 2026-11-05
    .\\.venv\\Scripts\\python.exe scripts\\collect_screens.py --src "D:\\Recordings"
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "docs" / "traktor-ui" / "screens" / "train"


def video_dirs() -> list[Path]:
    """Windows 'Videos' known folder, incl. OneDrive-redirected variants."""
    home = Path.home()
    cands = [home / "Videos"]
    for var in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        if os.environ.get(var):
            cands.append(Path(os.environ[var]) / "Videos")
    cands += list(home.glob("OneDrive*/Videos"))
    seen, out = set(), []
    for c in cands:
        if c.is_dir() and c.resolve() not in seen:
            seen.add(c.resolve())
            out.append(c)
    return out


def png_size(path: Path) -> tuple[int, int]:
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return (0, 0)
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def collect(src: list[Path] | None = None, since: dt.date | None = None,
            all_dates: bool = False, quiet: bool = False) -> list[Path]:
    canvas = json.loads((ROOT / "layout.json").read_text(encoding="utf-8"))["canvas"]
    want = (canvas["width"], canvas["height"])
    since = since or dt.date.today()
    dirs = src or video_dirs()
    if not dirs:
        raise SystemExit("no Videos folder found - pass --src <folder where OBS saves screenshots>")
    DEST.mkdir(parents=True, exist_ok=True)
    have = {hashlib.sha1(p.read_bytes()).hexdigest() for p in DEST.glob("*.png")}
    copied, skipped_size, skipped_dup, skipped_old = [], [], 0, 0
    for d in dirs:
        for p in sorted(d.glob("Screenshot*.png")):
            mdate = dt.date.fromtimestamp(p.stat().st_mtime)
            if not all_dates and mdate < since:
                skipped_old += 1
                continue
            size = png_size(p)
            if size != want:
                skipped_size.append((p.name, size))
                continue
            digest = hashlib.sha1(p.read_bytes()).hexdigest()
            if digest in have:
                skipped_dup += 1
                continue
            have.add(digest)
            dst = DEST / p.name.replace(" ", "_")
            shutil.copy2(p, dst)
            copied.append(dst)
    if not quiet:
        print(f"searched: {', '.join(str(d) for d in dirs)}")
        print(f"copied {len(copied)} new screenshot(s) -> {DEST.relative_to(ROOT)}  "
              f"(now {len(list(DEST.glob('*.png')))} in total)")
        if skipped_size:
            print(f"skipped {len(skipped_size)} with wrong size (need {want[0]}x{want[1]} = "
                  f"'Screenshot (Source)' of the Traktor capture):")
            for name, s in skipped_size[:5]:
                print(f"    {name}  {s[0]}x{s[1]}")
        if skipped_dup:
            print(f"skipped {skipped_dup} duplicate(s)")
        if skipped_old:
            print(f"ignored {skipped_old} older screenshot(s) (before {since}; use --since/--all)")
    return copied


def main() -> int:
    ap = argparse.ArgumentParser(description="collect OBS screenshots for training")
    ap.add_argument("--src", nargs="+", type=Path, help="folder(s) to search instead of Videos")
    ap.add_argument("--since", type=dt.date.fromisoformat, help="YYYY-MM-DD (default: today)")
    ap.add_argument("--all", action="store_true", help="any date")
    args = ap.parse_args()
    collect(args.src, args.since, args.all)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
