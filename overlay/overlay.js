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
const WS_URL = "ws://127.0.0.1:8787";

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
let demoPaused = false;
let wsConnected = false;

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function poke(id, value) {
  const s = state.get(id);
  if (!s) return;
  // hysteresis: ignore ±1 jitter so the glow doesn't flicker on encoder noise
  if (Math.abs(value - s.value) < 2 && value !== 0 && value !== 127) return;
  s.value = value;
  s.last = performance.now();
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
    if (msg.type === "midi") poke(msg.id, msg.value);
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
  const { box, label } = widget;
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

  // label pill above the widget
  if (label) {
    ctx.globalAlpha = 1;
    ctx.font = "600 15px 'Segoe UI', system-ui, sans-serif";
    const padX = 10;
    const pillW = ctx.measureText(label).width + padX * 2;
    const pillH = 24;
    const pillX = box.x + box.w / 2 - pillW / 2;
    const pillY = box.y - pillH - 10;
    ctx.fillStyle = theme.label_bg;
    roundRect(pillX, pillY, pillW, pillH, 12);
    ctx.fill();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.fillStyle = theme.label_color;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(label, pillX + pillW / 2, pillY + pillH / 2 + 1);
  }

  ctx.restore();
}

function frame(now) {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (layout) {
    const ttl = layout.glow.ttl_ms;
    for (const w of layout.widgets) {
      const s = state.get(w.id);
      const age = now - s.last;
      if (age > ttl) continue;
      const decay = 1 - age / ttl; // linear fade-out after last MIDI event
      const intensity = Math.max(s.value / 127, 0.3) * decay;
      drawGlow(w, intensity, s.value, now);
    }
  }
  requestAnimationFrame(frame);
}

/* ---------------- boot ---------------- */
function applyLayout(newLayout) {
  layout = newLayout;
  canvas.width = layout.canvas.width;
  canvas.height = layout.canvas.height;
  for (const w of layout.widgets) {
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