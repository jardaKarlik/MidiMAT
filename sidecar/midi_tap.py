"""MIDI input tap: monitor, verify, and feed the sidecar.

Answers the Phase-1 hardware question ("does the X1 MK3 send MIDI?") and builds
the empirical knowledge of which (channel, kind, number) each physical control
uses — the X1 MK3 is a NATIVE (HID) device in Traktor, so its DDCB mapping is
empty and cc_map.json learned via `watch`/`record` is the source of truth.

Usage:
    python -m sidecar.midi_tap list
    python -m sidecar.midi_tap watch [--port X1] [--record raw.jsonl]
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time

import mido


def find_port(substr: str, ports: list[str]) -> str | None:
    substr = substr.lower()
    return next((p for p in ports if substr in p.lower()), None)


class MidiTap(threading.Thread):
    """Background MIDI listener; invokes callback(msg_dict) for each message."""

    def __init__(self, port_substr: str, callback, on_status=None):
        super().__init__(daemon=True, name="midi-tap")
        self.port_substr = port_substr
        self.callback = callback
        self.on_status = on_status or (lambda s: None)
        self.port: mido.ports.BaseInput | None = None
        self._stop = threading.Event()

    def run(self) -> None:
        while not self._stop.is_set():
            ports = mido.get_input_names()
            name = find_port(self.port_substr, ports)
            if not name:
                self.on_status(
                    f"midi port matching {self.port_substr!r} not found; "
                    f"available: {ports} — retrying in 3 s"
                )
                self._stop.wait(3)
                continue
            try:
                self.port = mido.open_input(name)
            except Exception as e:  # noqa: BLE001
                self.on_status(f"cannot open {name!r}: {e}; retrying in 3 s")
                self._stop.wait(3)
                continue
            self.on_status(f"midi listening on {name!r}")
            try:
                for msg in self.port:
                    if self._stop.is_set():
                        break
                    if msg.type in ("control_change", "note_on", "note_off"):
                        self.callback({
                            "kind": "cc" if msg.type == "control_change" else "note",
                            "channel": msg.channel,
                            "number": getattr(msg, "control", msg.note),
                            "value": getattr(msg, "value", 127 if msg.type == "note_on" else 0),
                            "ts": time.time(),
                            "port": name,
                        })
            except Exception as e:  # noqa: BLE001
                self.on_status(f"midi read error on {name!r}: {e}; reconnecting")
                time.sleep(1)
            finally:
                if self.port:
                    self.port.close()
                    self.port = None

    def stop(self) -> None:
        self._stop.set()
        if self.port:
            self.port.close()


def cmd_list() -> int:
    print("MIDI inputs:")
    for p in mido.get_input_names():
        print(f"  IN  {p}")
    print("MIDI outputs:")
    for p in mido.get_output_names():
        print(f"  OUT {p}")
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    rec = open(args.record, "a", encoding="utf-8") if args.record else None
    seen: dict[tuple, int] = {}

    def handle(m: dict) -> None:
        key = (m["channel"], m["kind"], m["number"])
        seen[key] = seen.get(key, 0) + 1
        line = (f"ch={m['channel'] + 1:02d} {m['kind']:4s} #{m['number']:3d} "
                f"val={m['value']:3d}  (x{seen[key]})")
        print(line, flush=True)
        if rec:
            rec.write(json.dumps(m) + "\n")
            rec.flush()

    tap = MidiTap(args.port, handle, on_status=lambda s: print(f"[midi] {s}", flush=True))
    tap.start()
    print(f"watching port ~{args.port!r} — move controls now (Ctrl+C to stop)")
    try:
        while tap.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        tap.stop()
        if rec:
            rec.close()
        print(f"\nunique keys seen: {len(seen)}")
        for (ch, kind, num), cnt in sorted(seen.items()):
            print(f"  ch={ch + 1:02d} {kind:4s} #{num:3d}  x{cnt}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MidiMAT MIDI tap")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list MIDI ports")
    w = sub.add_parser("watch", help="print incoming MIDI messages")
    w.add_argument("--port", default="X1", help="port name substring (default: X1)")
    w.add_argument("--record", help="append raw messages to JSONL file")
    args = parser.parse_args(argv)
    if args.cmd == "list":
        return cmd_list()
    return cmd_watch(args)


if __name__ == "__main__":
    raise SystemExit(main())