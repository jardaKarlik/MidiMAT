# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet — see [v0.1.0](#010---2026-11-25) for the first public release.

## [0.1.0] - 2026-11-25

First public release. The desktop app bundles the Python sidecar and the overlay behind a
single `MidiMAT.exe` (Windows, x64); the overlay still works standalone as a Browser Source.

### Added

- **Single-file desktop app** (`MidiMAT.exe`) — a .NET 10 / WinUI 3 shell hosting the React +
  Tailwind management UI in one WebView2, with the Python sidecar bundled as a PyInstaller
  payload and installed to `%LOCALAPPDATA%` on first run.
- **Guided setup wizard** — six steps (runtime, loopMIDI, Traktor, server, OBS, save) that
  installs loopMIDI, injects the Traktor out-mappings into `Traktor Settings.tsi`, and wires
  the OBS Browser Source.
- **System tray** — closing the window hides to the tray so the sidecar keeps serving the
  overlay; the tray menu offers Show / Open overlay / Quit.
- **Traktor config injection** — a *surgical* writer that adds the MidiMAT out-mappings into
  an existing `Traktor Settings.tsi` `Generic MIDI` device without touching any other
  controller or mapping.
- **Version** — the release version is now surfaced in the app (Help screen) and pinned in
  `app/MidiMAT.csproj` and `ui/package.json`.
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
- **Dependency checker, sidecar supervisor and a typed WebView2 IPC bridge** — the shell
  probes for loopMIDI / Traktor / OBS / WebView2, restarts the sidecar with backoff, and
  exchanges typed messages with the React UI.

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
[0.1.0]: https://github.com/jardaKarlik/MidiMAT/releases/tag/v0.1.0
