"""
MidiMAT sidecar — Phase 0 demo server.

Serves the overlay (OBS browser source) over HTTP and broadcasts fake MIDI events
over WebSocket. Phase 1 replaces the demo generator with real MIDI input from the
Traktor X1 mk3.

Usage:
    python sidecar/server.py                # static overlay + demo event generator
    python sidecar/server.py --no-demo      # static overlay, wait for real MIDI (phase 1)
    python sidecar/server.py --http-port 8080 --ws-port 8787
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import pathlib
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import websockets

ROOT = pathlib.Path(__file__).resolve().parent.parent
LAYOUT = json.loads((ROOT / "layout.json").read_text(encoding="utf-8"))

log = logging.getLogger("midimat")

# --- shared state between the HTTP thread and the asyncio loop -----------------
_clients: set = set()
_queue: "asyncio.Queue[dict] | None" = None
_loop: "asyncio.AbstractEventLoop | None" = None
_stats = {"sent": 0, "last_status": time.monotonic()}


def emit(event: dict) -> None:
    """Thread-safe: schedule a broadcast on the asyncio loop (safe from any thread)."""
    if _queue is None or _loop is None:
        return
    asyncio.run_coroutine_threadsafe(_queue.put(event), _loop)


def emit_midi(widget_id: str, value: int) -> None:
    emit({"type": "midi", "id": widget_id, "value": int(value), "ts": time.time()})


# --- HTTP: static files from repo root (overlay + layout.json) -----------------
class QuietStaticHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):  # route through logging, keep console tidy
        log.debug("http %s", fmt % args)


def start_http(port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), QuietStaticHandler)
    Thread(target=server.serve_forever, daemon=True, name="http").start()
    return server


# --- WebSocket: broadcast MIDI events to the overlay ---------------------------
async def ws_handler(ws):
    _clients.add(ws)
    log.info("overlay connected (%d client(s))", len(_clients))
    await ws.send(json.dumps({"type": "hello", "layout": LAYOUT}))
    try:
        async for msg in ws:  # overlay may send calibration clicks in later phases
            log.debug("from overlay: %s", msg)
    finally:
        _clients.discard(ws)
        log.info("overlay disconnected (%d remaining)", len(_clients))


async def pump():
    """Forward queued events to every connected overlay."""
    assert _queue is not None
    while True:
        event = await _queue.get()
        if not _clients:
            continue
        data = json.dumps(event)
        results = await asyncio.gather(
            *(c.send(data) for c in list(_clients)), return_exceptions=True
        )
        _stats["sent"] += sum(1 for r in results if not isinstance(r, Exception))


async def demo_generator():
    """Fake X1 activity: sweep values across every widget in `layout.json`."""
    widgets = LAYOUT["widgets"]
    log.info("demo generator started — %d widgets", len(widgets))
    step = 0
    while True:
        widget = widgets[step % len(widgets)]
        # triangle sweep 0 → 127 → 0 over ~1.1 s (22 steps × 50 ms)
        for i in range(23):
            t = i / 22
            value = round(127 * (t * 2 if t < 0.5 else (1 - t) * 2))
            emit_midi(widget["id"], value)
            await asyncio.sleep(0.05)
        step += 1
        await asyncio.sleep(0.4)  # gap → glow decays, visible breathing


async def status_loop():
    """Keep-alive log line so long runs are monitorable (every 30 s)."""
    while True:
        await asyncio.sleep(30)
        now = time.monotonic()
        rate = _stats["sent"] / max(now - _stats["last_status"], 1e-6)
        log.info(
            "status: %d overlay client(s), %d events total (%.1f/s)",
            len(_clients), _stats["sent"], rate,
        )
        _stats["last_status"] = now


async def run_ws(port: int, demo: bool):
    global _queue, _loop
    _loop = asyncio.get_running_loop()
    _queue = asyncio.Queue()
    async with websockets.serve(ws_handler, "127.0.0.1", port):
        tasks = [asyncio.create_task(pump()), asyncio.create_task(status_loop())]
        if demo:
            tasks.append(asyncio.create_task(demo_generator()))
        log.info("WebSocket ready on ws://127.0.0.1:%d (demo=%s)", port, demo)
        await asyncio.gather(*tasks)


def main() -> None:
    parser = argparse.ArgumentParser(description="MidiMAT sidecar (phase 0)")
    parser.add_argument("--http-port", type=int, default=8080)
    parser.add_argument("--ws-port", type=int, default=8787)
    parser.add_argument("--no-demo", action="store_true",
                        help="disable the fake event generator (phase 1: real MIDI)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03d %(levelname)-7s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    start_http(args.http_port)
    log.info("overlay:  http://127.0.0.1:%d/overlay/index.html?debug=1", args.http_port)
    log.info("widgets:  %d loaded from %s", len(LAYOUT["widgets"]), ROOT / "layout.json")
    try:
        asyncio.run(run_ws(args.ws_port, demo=not args.no_demo))
    except KeyboardInterrupt:
        log.info("shutting down")


if __name__ == "__main__":
    main()