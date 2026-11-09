# Contributing to MidiMAT

Thanks for taking the time to help. This project lives or dies on **real reports from
real controller setups**, so even a "it does nothing on my Z1" issue is valuable.

## Ways to help

| | |
|---|---|
| 🐞 **Bug reports** | Use the [bug template](../../issues/new?template=bug_report.yml). Include your controller, Traktor version and what you saw vs expected. |
| 💡 **Feature ideas** | Use the [feature template](../../issues/new?template=feature_request.yml). |
| 🎛 **New device support** | Own a controller that isn't mapped? A learned mapping (see below) is the single most useful contribution. |
| 📖 **Docs** | If a step confused you, it'll confuse the next person — fix it. |
| 🔧 **Code** | See "Development" below. |

## Development

### Prerequisites

- **Windows 10/11**
- **Python 3.11+**
- **Node.js 20+** (only for the desktop app UI under `ui/`)
- For a full end-to-end run: Traktor Pro, [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html), and OBS Studio

### Getting started

```powershell
git clone https://github.com/jardaKarlik/MidiMAT.git
cd MidiMAT

# Create the venv and install runtime deps
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Run the sidecar (demo events, no hardware needed)
.\scripts\run.ps1
```

The overlay is then at <http://127.0.0.1:8080/overlay/index.html?demo=1>.

> `requirements-train.txt` is **only** for training the optional control detector and
> pulls PyTorch (~1–2 GB). You almost certainly don't need it.

### Learning a new device

The most valuable contribution. See `docs/PHASE1.md`, then:

```powershell
# 1. See what your controller sends
.\.venv\Scripts\python.exe -m sidecar.midi_tap watch --port "YOUR DEVICE"

# 2. Run the guided mapping wizard
.\.venv\Scripts\python.exe scripts\setup_wizard.py --profile all
```

`mapping/controls.csv` is the source of truth; `scripts\build_maps.py` regenerates
`cc_map.json` and `layout.json` from it.

### Running the tests

```powershell
.\.venv\Scripts\python.exe scripts\test_phase1.py     # TSI parser + resolver
.\.venv\Scripts\python.exe scripts\test_suggest.py    # auto-placement
node scripts\test_hud_alpha.js                        # HUD fade timeline
```

## Conventions

- **Python** — standard library style, type hints where they help, `snake_case`.
  Keep the sidecar modules importable without a running server.
- **Front-end** — plain HTML/JS/CSS for `overlay/` (it runs inside OBS, keep it
  dependency-free); React + TypeScript + Tailwind for `ui/`.
- **Commits** — short imperative subject, e.g.
  `z1: map channel faders`, `overlay: fix glow flicker on ±1 jitter`.
- **One change per PR.** Small and reviewable beats big and clever.

## What NOT to commit

Some files are personal or machine-generated and must stay out of the repo. `.gitignore`
already covers most of these — please don't force-add them:

- `Traktor Settings.tsi` or any personal Traktor config;
- your own `mapping/controls.csv` edits unless they add a **new device** (mappings are
  personal to each rig — if in doubt, open an issue first);
- `.jsonl` capture dumps, `*.log`, `*.pid`, and `models/*.pt` weights;
- `.venv/`, `node_modules/`, `app/bin/`, `app/obj/`.

Generated files (`cc_map.json`, `layout.json`) are committed so the app works out of
the box — regenerate them via `scripts\build_maps.py` rather than hand-editing.

## Reporting a mapping problem

Include all of:

1. Controller model(s) and how they're connected (native vs. MIDI mode).
2. Traktor version.
3. Output of `.\.venv\Scripts\python.exe -m sidecar.midi_tap list`.
4. A few lines of `midi_tap watch` output while you move the problem control.

That's usually enough to reproduce it.
