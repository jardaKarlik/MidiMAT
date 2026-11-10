/**
 * Shared constants: sidecar ports/URLs and the shell's virtual host.
 * Mirrors DESIGN_APP.md §3.2 (React ↔ Python sidecar) and §6 (config defaults).
 */

/** Python sidecar HTTP origin (static overlay + REST API). */
export const HTTP_BASE = "http://127.0.0.1:8080";

/** Python sidecar WebSocket origin (live MIDI/NHL events). */
export const WS_URL = "ws://127.0.0.1:8787";

/**
 * Virtual host the WinUI 3 shell maps onto app/Resources/ui.
 * Present so the UI can reason about where it is hosted; the app itself is
 * origin-agnostic because Vite emits relative asset URLs (base: "./").
 */
export const APP_ORIGIN = "https://midimat.local/";

/** OBS browser-source overlay (served by the sidecar). */
export const OVERLAY_URL = `${HTTP_BASE}/overlay/index.html`;

/** Legacy visual editor embedded in the Editor screen (wiring-later iframe). */
export const EDITOR_URL = `${HTTP_BASE}/overlay/edit.html`;

/** Sidecar REST endpoints used by the management UI. */
export const ENDPOINTS = {
  health: `${HTTP_BASE}/api/health`,
  controls: `${HTTP_BASE}/api/controls`,
  suggest: `${HTTP_BASE}/api/suggest`,
  refit: `${HTTP_BASE}/api/refit`,
} as const;

/** Placeholder donate link (real campaign pending). */
export const COFFEE_URL = "https://www.buymeacoffee.com/lee_cz";

/** Upstream repository (DESIGN_APP.md §12). */
export const REPO_URL = "https://github.com/jardaKarlik/MidiMAT";
