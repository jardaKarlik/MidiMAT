# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
MidiMAT is currently **pre-1.0** — there are no tagged releases yet; everything below is
on `main`.

## [Unreleased]

### Added

- **Visual editor** — place widget boxes on a Traktor screenshot, save to
  `layout.json`, live-push to connected overlays with no OBS refresh.
- **`🎯 Detect & re-fit`** — detect controls on a fresh screenshot and move the whole
  saved layout onto them, so a moved/resized Traktor window needs one click.
- **`✨ Suggest (AI)`** — optional auto-placement for never-placed boxes (opt-in;
  requires the extra vision dependency).
- **Guided mapping wizard** (`scripts/setup_wizard.py`) — walks each Traktor
  out-mapping one control at a time, listens on the MidiMAT port, verifies the CC
  arrives, and writes the row to `mapping/controls.csv`.
- **HUD card** — control name + live value, for controls that have no on-screen widget.
- **Demo mode** (`?demo=1`) — the overlay animates with no controller or server.
- **Desktop application** (in development) — a Windows App SDK (WinUI 3) shell hosting a
  React + Tailwind management UI, with a Python sidecar bundled for a single-file
  installer. Includes a dependency checker, a sidecar process supervisor with
  restart-backoff, and a typed WebView2 IPC bridge.
- **Traktor config injection** — a *surgical* writer that adds the MidiMAT out-mappings
  into an existing `Traktor Settings.tsi` `Generic MIDI` device without touching any
  other controller or mapping.

### Changed

- Overlay now re-reads `layout.json` on every WebSocket `hello`, so edits are live.
- `run.ps1` auto-replaces a previous sidecar instance holding ports 8080/8787.

### Fixed

- HUD fade-in keys off appearance time, not the last event, removing visible blinking
  at high event rates.
- `nhl_tap` crash-guard + heartbeats so the background reader can no longer die silently.

### Research

- Documented the **NHL** (native vendor-HID) protocol for direct-HID input, which would
  remove the loopMIDI requirement. Not implemented for X1 MK3 yet — see
  `docs/NHL_PROTOCOL.md`.

[Unreleased]: https://github.com/jardaKarlik/MidiMAT/commits/main
