/* MidiMAT overlay — phase 0.
 *
 * Modes:
 *   ?demo=1     self-running glow demo (no sidecar needed) — click a widget to pulse,
 *               Space pauses.
 *   (default)   connects to sidecar WebSocket ws://127.0.0.1:8787 and glows on real events.
 *   ?debug=1    shows the status pill (connection / mode).
 */
"use strict";

const qs = new URLSearchParams(location.search);
const DEMO = qs.get("demo") === "1";
const DEBUG = qs.get("debug") === "1";
const SHOT = qs.get("shot"); // ?shot=<widget_id> — deterministic still-frame for visual QA
const SHOT_LABEL = qs.get("shotlabel"); // ?shotlabel=Z1 · Test — HUD-only still (no widget)
const WS_URL = "ws://127.0.0.1:8787";

// Never die silently again: any JS error becomes a visible red-bordered pill.
window.addEventListener("error", (e) =>
  setStatus(`MidiMAT JS error: ${e.message} (line ${e.lineno})`, true),
);
window.addEventListener("unhandledrejection", (e) =>
  setStatus(`MidiMAT async error: ${e.reason}`, true),
);

// Built-in fallback so the overlay still glows when layout.json can't be fetched
// (e.g. the page was opened directly from disk). Keep in sync with ../layout.json.
const DEFAULT_LAYOUT = {
  canvas: { width: 1920, height: 1080 },
  theme: {
    deck_colors: { A: "#33ccff", B: "#3dff9e", FX: "#ffcc33" },
    label_bg: "rgba(0, 0, 0, 0.6)",
    label_color: "#ffffff",
  },
  glow: { ttl_ms: 600, stroke_width: 3, blur_base: 12, blur_gain: 26, corner_radius: 14 },
  hud: { enabled: true, ttl_ms: 1600, anchor: "bottom-center", margin_bottom: 48, width: 640, height: 88, show_value_pct: true },
  widgets: [
    { id: "deck_a_filter", label: "Deck A · Filter", deck: "A", box: { x: 300, y: 430, w: 110, h: 110 } },
    { id: "deck_a_move", label: "Deck A · Move", deck: "A", box: { x: 470, y: 430, w: 110, h: 110 } },
    { id: "fx1_size", label: "FX1 · Flanger Size", deck: "FX", box: { x: 900, y: 300, w: 96, h: 96 } },
    { id: "fx1_drywet", label: "FX1 · Dry/Wet", deck: "FX", box: { x: 1050, y: 300, w: 96, h: 96 } },
    { id: "master_gain", label: "Master · Gain", deck: "B", box: { x: 1560, y: 700, w: 80, h: 160 } },
  ],
};

const canvas = document.getElementById("stage");
const ctx = canvas.getContext("2d");
const statusEl = document.getElementById("status");

let layout = null;
const state = new Map(); // widget id -> { value, last }
const widgetById = new Map(); // widget id -> widget (for label/deck lookup)
let hud = null; // { label, deck, value, last } — the lower-third description card
let demoPaused = false;
let wsConnected = false;

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function poke(id, value, label, deck) {
  const now = performance.now();
  const s = state.get(id);
  const w = widgetById.get(id);
  // HUD-only events are legal: label without calibrated widget => description
  // card shows, no glow box (until calibrate.py assigns a box to this id).
  if (!s && !w && !label) return;
  if (s) {
    // liveness ALWAYS refreshes — slow knob turns (±1 steps) must not blink the
    // card/glow out mid-interaction; value gets hysteresis, activity never does.
    s.last = now;
    if (Math.abs(value - s.value) >= 2 || value === 0 || value === 127) {
      s.value = value;
    }
  }
  const ttl = (layout && layout.hud && layout.hud.ttl_ms) || 1600;
  // fade-in only on TRUE appearance: keep first-seen time while the interaction
  // continues (same id, events within ttl). Keying it off `last` caused the
  // bottom-center card to re-fade on every value tick = blinking.
  const continuing = hud && hud.id === id && now - hud.last <= ttl;
  hud = {
    id,
    label: label || (w && w.label) || id,
    deck: (w && w.deck) || deck || "MIDI",
    value: s ? s.value : value,
    last: now,
    first: continuing ? hud.first : now,
  };
}

function setStatus(text, isError = false) {
  if (!text) {
    if (!DEBUG) statusEl.hidden = true; // keep pill visible when debugging
    return;
  }
  statusEl.hidden = false;
  statusEl.textContent = text;
  statusEl.style.borderColor = isError ? "#ff5555" : "rgba(255,255,255,0.25)";
}

/* ---------------- WebSocket mode ---------------- */
function connectWS() {
  const ws = new WebSocket(WS_URL);
  ws.onopen = () => {
    wsConnected = true;
    setStatus(DEBUG ? `ws ${WS_URL} · connected` : null);
  };
  ws.onclose = () => {
    wsConnected = false;
    setStatus(
      `MidiMAT: sidecar not reachable (${WS_URL}) — start it with .\\scripts\\run.ps1` +
        `  ·  attract demo running`,
      true,
    );
    setTimeout(connectWS, 1500);
  };
  ws.onmessage = (e) => {
    let msg;
    try {
      msg = JSON.parse(e.data);
    } catch {
      return;
    }
    if (msg.type === "hello" && msg.layout) applyLayout(msg.layout);
    if (msg.type === "midi") poke(msg.id, msg.value, msg.label, msg.deck);
  };
}

/* ---------------- demo / attract mode ---------------- */
async function demoLoop() {
  let i = 0;
  while (true) {
    // In demo mode it's the show; in WS mode it's an "attract" fallback that only
    // runs while the sidecar is disconnected (no sidecar = no real events anyway).
    const attract = DEMO || !wsConnected;
    if (attract && !demoPaused && layout) {
      const w = layout.widgets[i % layout.widgets.length];
      i++;
      for (let s = 0; s <= 22; s++) {
        if (demoPaused) break;
        const t = s / 22;
        poke(w.id, Math.round(127 * (t < 0.5 ? t * 2 : (1 - t) * 2)));
        await sleep(50);
      }
      await sleep(350);
    } else {
      await sleep(150);
    }
  }
}

/* ---------------- rendering ---------------- */
function roundRect(x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function drawGlow(widget, intensity, value, now) {
  const { box } = widget;
  const theme = layout.theme;
  const glow = layout.glow;
  const color = theme.deck_colors[widget.deck] || "#33ccff";
  // subtle pulse so a held control still reads as "active"
  const pulse = 0.85 + 0.15 * Math.sin(now / 140);

  ctx.save();

  // bloom pass
  ctx.shadowColor = color;
  ctx.shadowBlur = (glow.blur_base + glow.blur_gain * intensity) * pulse;
  ctx.lineWidth = glow.stroke_width;
  ctx.strokeStyle = color;
  ctx.globalAlpha = 0.35 + 0.65 * intensity;
  roundRect(box.x, box.y, box.w, box.h, glow.corner_radius);
  ctx.stroke();

  // crisp core pass (bloom alone reads muddy at low stream bitrates)
  ctx.shadowBlur = 0;
  ctx.lineWidth = glow.stroke_width - 1;
  ctx.globalAlpha = Math.min(1, 0.5 + intensity);
  roundRect(box.x, box.y, box.w, box.h, glow.corner_radius);
  ctx.stroke();

  // value bar under the widget (viewers can't see tiny GUI knob positions)
  const barY = box.y + box.h + 8;
  ctx.globalAlpha = 0.5;
  ctx.fillStyle = "rgba(255,255,255,0.25)";
  ctx.fillRect(box.x, barY, box.w, 4);
  ctx.globalAlpha = 0.4 + 0.6 * intensity;
  ctx.fillStyle = color;
  ctx.fillRect(box.x, barY, (box.w * value) / 127, 4);

  ctx.restore();
}

/* Lower-third description card — bottom center, over the browser zone.
 * The widget itself only glows; ALL text lives here (decision: docs/TRAKTOR_UI.md). */
function drawHud(now, force = false) {
  if (!hud || !layout.hud || !layout.hud.enabled) return;
  const cfg = layout.hud;
  // single fade timeline, unit-tested: fadeIn off APPEARANCE (hud.first),
  // fadeOut off last event — refreshes never restart the fade (no blinking)
  const alpha = force
    ? 1
    : MidiHudAlpha.hudAlpha(now, hud.last, hud.first ?? hud.last, cfg.ttl_ms);
  if (alpha <= 0) return;
  const color = layout.theme.deck_colors[hud.deck] || "#33ccff";
  const w = cfg.width;
  const h = cfg.height;
  const x = (canvas.width - w) / 2;
  const y = canvas.height - cfg.margin_bottom - h + (1 - alpha) * 14; // slide-up

  const badgeText =
    hud.deck === "A" || hud.deck === "B" ? `DECK ${hud.deck}` : String(hud.deck);
  const innerX = x + 24;

  ctx.save();

  // card body (subtle deck-tinted glow, not competing with the widget glow)
  ctx.globalAlpha = alpha;
  ctx.shadowColor = color;
  ctx.shadowBlur = 24;
  ctx.fillStyle = "rgba(0, 0, 0, 0.72)";
  roundRect(x, y, w, h, 16);
  ctx.fill();
  ctx.shadowBlur = 0;
  ctx.strokeStyle = color;
  ctx.globalAlpha = alpha * 0.5;
  ctx.lineWidth = 1.5;
  roundRect(x, y, w, h, 16);
  ctx.stroke();

  // left accent bar
  ctx.globalAlpha = alpha;
  ctx.fillStyle = color;
  roundRect(x, y + 14, 6, h - 28, 3);
  ctx.fill();

  // deck/FX badge
  ctx.font = "700 13px 'Segoe UI', system-ui, sans-serif";
  const badgeW = ctx.measureText(badgeText).width + 20;
  ctx.fillStyle = color;
  roundRect(innerX, y + 16, badgeW, 24, 12);
  ctx.fill();
  ctx.fillStyle = "#0b0b0b";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(badgeText, innerX + badgeW / 2, y + 28);

  // function name — the star of the card
  ctx.font = "600 26px 'Segoe UI', system-ui, sans-serif";
  ctx.fillStyle = "#ffffff";
  ctx.textAlign = "left";
  ctx.fillText(hud.label, innerX + badgeW + 16, y + 29);

  // value, right-aligned
  if (cfg.show_value_pct !== false) {
    ctx.font = "700 22px 'Segoe UI', system-ui, sans-serif";
    ctx.fillStyle = color;
    ctx.textAlign = "right";
    ctx.fillText(`${Math.round((hud.value / 127) * 100)}%`, x + w - 22, y + 29);
  }

  // value bar along the bottom inner edge
  const barW = w - 48;
  ctx.fillStyle = "rgba(255, 255, 255, 0.16)";
  roundRect(innerX, y + h - 22, barW, 6, 3);
  ctx.fill();
  ctx.fillStyle = color;
  roundRect(innerX, y + h - 22, (barW * hud.value) / 127, 6, 3);
  ctx.fill();

  ctx.restore();
}

function frame() {
  // ONE clock source only — rAF's timestamp can diverge from performance.now()
  // (seen under headless virtual time) which once pushed the HUD off-canvas.
  const now = performance.now();
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (layout) {
    if (SHOT && widgetById.has(SHOT)) {
      // deterministic still-frame for screenshots/QA: fixed value, no decay
      const w = widgetById.get(SHOT);
      drawGlow(w, 0.9, 100, now);
      hud = { id: SHOT, label: w.label, deck: w.deck, value: 100, last: now, first: now };
      drawHud(now, true);
    } else if (SHOT_LABEL) {
      // HUD-only still: exactly the render path used by live NHL events
      hud = { id: "shot", label: SHOT_LABEL, deck: "MIDI", value: 64, last: now, first: now };
      drawHud(now, true);
    } else {
      const ttl = layout.glow.ttl_ms;
      for (const w of layout.widgets) {
        const s = state.get(w.id);
        const age = now - s.last;
        if (age > ttl || age < 0) continue;
        const decay = Math.max(0, Math.min(1, 1 - age / ttl));
        const intensity = Math.max(s.value / 127, 0.3) * decay;
        drawGlow(w, intensity, s.value, now);
      }
      drawHud(now);
    }
  }
  requestAnimationFrame(frame);
}

/* ---------------- boot ---------------- */
function applyLayout(newLayout) {
  layout = newLayout;
  canvas.width = layout.canvas.width;
  canvas.height = layout.canvas.height;
  widgetById.clear();
  for (const w of layout.widgets) {
    widgetById.set(w.id, w);
    if (!state.has(w.id)) state.set(w.id, { value: 0, last: 0 });
  }
}

async function init() {
  try {
    const resp = await fetch("../layout.json");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    applyLayout(await resp.json());
  } catch (err) {
    // file:// origin or sidecar down — never die silently, fall back and SAY so
    console.error("MidiMAT: layout.json not loadable:", err);
    applyLayout(DEFAULT_LAYOUT);
    setStatus(`MidiMAT: layout.json not loadable (${err.message}) — using built-in copy`, true);
  }

  if (DEMO) setStatus("demo mode · click=pulse, Space=pause");
  else connectWS();
  demoLoop(); // the show in demo mode; attract fallback in ws mode while disconnected

  window.addEventListener("keydown", (e) => {
    if (e.code === "Space") {
      demoPaused = !demoPaused;
      e.preventDefault();
    }
  });

  canvas.addEventListener("click", (e) => {
    if (!DEMO || !layout) return;
    const rect = canvas.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * canvas.width;
    const y = ((e.clientY - rect.top) / rect.height) * canvas.height;
    for (const w of layout.widgets) {
      const b = w.box;
      if (x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h) {
        poke(w.id, 127);
        setTimeout(() => poke(w.id, 64), 200);
      }
    }
  });

  requestAnimationFrame(frame);
}

init();