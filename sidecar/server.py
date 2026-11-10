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
import os
import pathlib
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import sys

import websockets


def _resolve_root() -> pathlib.Path:
    """Where the sidecar's data lives (overlay/, layout.json, cc_map.json, …).

    - Running from source  -> the repo root (parent of sidecar/).
    - Running frozen        -> next to the built executable when the data is shipped
      there (preferred, and what build/midimat-server.spec arranges), otherwise
      PyInstaller's bundle dir (`sys._MEIPASS`, e.g. the `_internal` folder).
    """
    if getattr(sys, "frozen", False):
        exe_dir = pathlib.Path(sys.executable).resolve().parent
        if (exe_dir / "layout.json").exists():
            return exe_dir
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return pathlib.Path(meipass)
        return exe_dir
    return pathlib.Path(__file__).resolve().parent.parent


ROOT = _resolve_root()


def load_layout() -> dict:
    return json.loads((ROOT / "layout.json").read_text(encoding="utf-8"))


LAYOUT = load_layout()

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sidecar.midi_tap import MidiTap  # noqa: E402
from sidecar.mapping import Resolver, load_config  # noqa: E402
from sidecar.nhl_tap import NhlTap, decode_changes, device_nick  # noqa: E402

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


def emit_midi(widget_id: str, value: int, label: str | None = None,
               deck: str | None = None) -> None:
    ev = {"type": "midi", "id": widget_id, "value": int(value), "ts": time.time()}
    if label:
        ev["label"] = label
    if deck:
        ev["deck"] = deck
    _stats["midi_events"] = _stats.get("midi_events", 0) + 1
    emit(ev)


# --- HTTP: static files from repo root (overlay + layout.json) -----------------
def _csv_tools():
    """Shared CSV helpers live in scripts/ (wizard + build_maps)."""
    sp = str(ROOT / "scripts")
    if sp not in sys.path:
        sys.path.insert(0, sp)
    import build_maps  # noqa: PLC0415
    import setup_wizard  # noqa: PLC0415
    return setup_wizard, build_maps


class QuietStaticHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):  # editor/overlay must never see a stale layout.json
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, code: int, obj) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path.split("?")[0] == "/api/controls":
            wiz, _ = _csv_tools()
            self._json(200, {"canvas": load_layout()["canvas"],
                             "rows": list(wiz.load_rows().values())})
            return
        super().do_GET()

    def _suggest(self) -> None:
        """Placer 'Suggest': {"image": dataURL, "ids"?: [...]} -> suggestions JSON.
        Default ids = controls that still need a box (hud rows excluded)."""
        try:
            n = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(n) or b"{}")
            from sidecar import suggest as sg  # noqa: PLC0415 (opencv only when used)
            wiz, _ = _csv_tools()
            rows = list(wiz.load_rows().values())
            ids = payload.get("ids")
            rows = ([r for r in rows if r["id"] in ids] if ids else
                    [r for r in rows if r.get("shape") != "hud" and not r.get("x")])
            if not rows:
                self._json(200, {"candidates": 0, "suggestions": [], "missing": []})
                return
            img = sg.decode_data_url(payload["image"])
            log.info("suggest: %d control(s), model %s", len(rows),
                     os.environ.get("MIDIMAT_VLM_MODEL") or sg.DEFAULT_MODEL)
            res = sg.suggest(img, rows)
            cv = load_layout()["canvas"]  # editor works in canvas coords, not image px
            fx, fy = cv["width"] / img.shape[1], cv["height"] / img.shape[0]
            for sug in res["suggestions"]:
                sug["x"], sug["w"] = round(sug["x"] * fx), round(sug["w"] * fx)
                sug["y"], sug["h"] = round(sug["y"] * fy), round(sug["h"] * fy)
            log.info("suggest: %d candidates, %d suggested, %d missing",
                     res["candidates"], len(res["suggestions"]), len(res["missing"]))
            self._json(200, res)
        except ImportError as e:
            self._json(500, {"error": f"{e} - run: .venv\\Scripts\\pip install "
                                      "opencv-python numpy"})
        except RuntimeError as e:  # e.g. missing OPENROUTER_API_KEY
            self._json(400, {"error": str(e)})
        except Exception as e:  # noqa: BLE001
            log.exception("suggest failed")
            self._json(500, {"error": repr(e)})

    def _refit(self) -> None:
        """Placer 'Detect & re-fit': {"image": dataURL} -> detect controls, fit the saved
        layout onto them (scale + shift), return per-control suggestions (canvas coords)."""
        try:
            n = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(n) or b"{}")
            from sidecar import refit as rf  # noqa: PLC0415
            from sidecar import suggest as sg  # noqa: PLC0415
            wiz, _ = _csv_tools()
            template = rf.template_rows(list(wiz.load_rows().values()))
            if len(template) < 3:
                self._json(400, {"error": "need at least 3 placed boxes to re-fit"})
                return
            img = sg.decode_data_url(payload["image"])
            cv = load_layout()["canvas"]
            dets = rf.dets_to_canvas(sg.detect_candidates(img), img.shape[1], img.shape[0],
                                     cv["width"], cv["height"])
            if len(dets) < 3:
                self._json(400, {"error": f"only {len(dets)} control(s) detected - is this "
                                          "a Traktor screenshot? (detector: "
                                          f"{sg.detector_backend()})"})
                return
            res = rf.refit(template, dets)
            res["detector"], res["detections"] = sg.detector_backend(), len(dets)
            t = res["transform"]
            log.info("refit: %s, %d detections, matched %d/%d, scale %.3f/%.3f, "
                     "shift %+.1f/%+.1f, rms %.1fpx", res["detector"], len(dets), t["matched"],
                     len(template), t["sx"], t["sy"], t["tx"], t["ty"], t["rms"])
            self._json(200, res)
        except ImportError as e:
            self._json(500, {"error": f"{e} - run: .venv\\Scripts\\python.exe -m pip "
                                      "install -r requirements.txt"})
        except Exception as e:  # noqa: BLE001
            log.exception("refit failed")
            self._json(500, {"error": repr(e)})

    def do_POST(self):  # noqa: N802
        """Editor save: {"rows": [{"id", "x", "y", "w", "h", "shape"?}, ...]}
        -> merge boxes into mapping/controls.csv -> rebuild cc_map/layout ->
        push the new layout to every connected overlay (live, no OBS refresh)."""
        route = self.path.split("?")[0]
        if route == "/api/suggest":
            self._suggest()
            return
        if route == "/api/refit":
            self._refit()
            return
        if route != "/api/controls":
            self._json(404, {"error": "not found"})
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(n) or b"{}")
            wiz, bm = _csv_tools()
            rows = wiz.load_rows()
            changed = 0
            for upd in payload.get("rows", []):
                r = rows.get(upd.get("id"))
                if not r:
                    continue
                for k in ("x", "y", "w", "h"):
                    if upd.get(k) is None or upd.get(k) == "":
                        r[k] = ""
                    else:
                        r[k] = str(int(round(float(upd[k]))))
                if upd.get("shape") in ("circle", "rect"):
                    r["shape"] = upd["shape"]
                changed += 1
            wiz.save_rows(rows)
            summary = bm.build(quiet=True)
            emit({"type": "hello", "layout": load_layout()})
            log.info("editor saved %d box(es); layout pushed to overlays", changed)
            self._json(200, {"ok": True, "changed": changed, **summary})
        except Exception as e:  # noqa: BLE001
            log.exception("editor save failed")
            self._json(500, {"error": repr(e)})

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
    # fresh read per hello: layout.json edits must reach overlays without a restart
    await ws.send(json.dumps({"type": "hello", "layout": load_layout()}))
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
            "status: %d overlay client(s), %d events total (%.1f/s), "
            "%d midi/nhl events emitted",
            len(_clients), _stats["sent"], rate,
            _stats.get("midi_events", 0),
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
    parser.add_argument("--midi", action="store_true",
                        help="enable MIDI input using midi_ports from midimat.config.json")
    parser.add_argument("--midi-ports", nargs="+", default=None, metavar="SUBSTR",
                        help="override config midi ports, e.g. --midi-ports 'X1 MK3' "
                             "'Z1 MK2' (implies --midi)")
    parser.add_argument("--nhl", action="store_true",
                        help="listen to NHL (vendor HID) reports — controllers stay in "
                             "NATIVE mode; provisional labels until learn session")
    parser.add_argument("--config", default=str(ROOT / "midimat.config.json"))
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03d %(levelname)-7s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    start_http(args.http_port)
    log.info("overlay:  http://127.0.0.1:%d/overlay/index.html?debug=1", args.http_port)
    log.info("editor:   http://127.0.0.1:%d/overlay/edit.html", args.http_port)
    log.info("widgets:  %d loaded from %s", len(LAYOUT["widgets"]), ROOT / "layout.json")

    tap = None
    if args.midi or args.midi_ports:
        cfg = load_config(args.config)
        resolver = Resolver(cc_map_path=cfg.get("cc_map"), tsi_path=cfg.get("tsi"))
        port_hints = (args.midi_ports
                      or cfg.get("midi_ports")
                      or ([cfg["midi_port"]] if cfg.get("midi_port") else None)
                      or [resolver.port_hint or "X1"])

        def on_midi(msg: dict) -> None:
            res = resolver.resolve(msg)
            if not res:
                log.debug("unmapped: [%s] ch=%d %s #%d val=%d", msg.get("port"),
                          msg["channel"] + 1, msg["kind"], msg["number"], msg["value"])
                return
            wid = res.get("widget") or (
                f"key:{msg.get('port', '')}.{msg['channel']}."
                f"{msg['kind']}.{msg['number']}"
            )
            emit_midi(wid, msg["value"], res.get("label"), res.get("deck"))

        tap = MidiTap(port_hints, on_midi,
                      on_status=lambda s: log.info("midi| %s", s))
        tap.start()
        log.info("MIDI on port hints %r  resolver: %d cc_map entries, %d tsi mappings",
                 port_hints, len(resolver.entries), len(resolver.tsi_table))
        if not resolver.entries and not resolver.tsi_table:
            log.warning("empty resolver — nothing will glow; run "
                        "`python -m sidecar.midi_tap watch --port %s` and fill cc_map.json",
                        " ".join(port_hints))

    nhl = None
    if args.nhl:
        nhl_prev: dict[str, dict] = {}
        nhl_map: dict[str, dict] = {}
        map_path = ROOT / "nhl_map.json"
        if map_path.exists():
            nhl_map = json.loads(map_path.read_text(encoding="utf-8"))
            log.info("nhl_map loaded: %s",
                     {pid: len(m) for pid, m in nhl_map.items()})

        def on_nhl(raw: dict) -> None:
            prev = nhl_prev.setdefault(raw["serial"], {})
            dev_map = nhl_map.get(str(raw["pid"]), {})
            for e in decode_changes(raw["pid"], raw["data"], prev):
                info = dev_map.get(e["slot"], {})
                label = (f"{device_nick(raw['pid'], raw['serial'])} · "
                         f"{info.get('name', e['name'])}")
                wid = info.get("widget") or (
                    f"nhl:{raw['serial']}.{e['slot']}")
                emit_midi(wid, e["value"], label, None)
                log.info("nhl event: %s %s val=%d", raw["serial"], e["name"], e["value"])

        nhl = NhlTap(on_nhl, on_status=lambda s: log.info("nhl| %s", s))
        nhl.start()
        log.info("NHL tap started (native mode — wake X1s with a button press)")

    try:
        asyncio.run(run_ws(args.ws_port, demo=not args.no_demo))
    except OSError as e:
        code = getattr(e, "errno", None) or getattr(e, "winerror", None)
        if code in (98, 10048):  # EADDRINUSE / WSAEADDRINUSE
            raise SystemExit(
                f"port {args.ws_port} already in use — another MidiMAT sidecar is "
                f"running.\n  Stop it:  .\\scripts\\stop.ps1\n"
                f"  Or start with run.ps1 (auto-replaces the old instance),\n"
                f"  or pick another port: --ws-port 8788"
            ) from None
        raise
    except KeyboardInterrupt:
        log.info("shutting down")
    finally:
        if tap:
            tap.stop()
        if nhl:
            nhl.stop()


if __name__ == "__main__":
    main()