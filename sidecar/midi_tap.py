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


def find_ports(hints) -> list[str]:
    """All input ports matching ANY hint substring (str or list of str).

    IMPORTANT: multi-device setups are the norm here — TWO X1 MK3s (two ports
    differing only in index) plus a Z1 MK2 mixer, maybe an F1. Never dedupe by
    model name; every match is a real device."""
    if isinstance(hints, str):
        hints = [hints]
    names = mido.get_input_names()
    out: list[str] = []
    for h in hints:
        hl = h.lower()
        out.extend(p for p in names if hl in p.lower() and p not in out)
    return out


class MidiTap(threading.Thread):
    """Background MIDI listener over ALL matching ports (hot-plug rescan / 3 s).

    callback(msg) receives dicts that always include 'port' — with two identical
    controllers, (port, channel, kind, number) is the real identity of a control."""

    def __init__(self, port_hints, callback, on_status=None, on_raw=None):
        """port_hints: one substring or a list — ALL matching ports open
        (e.g. ['X1 MK3', 'Z1 MK2'] covers two X1s + the Z1 mixer).
        on_raw(port, mido_msg): optional, sees EVERY message (incl. pitchwheel,
        sysex, clock…) before the cc/note filter — for diagnosing silent ports."""
        super().__init__(daemon=True, name="midi-tap")
        self.on_raw = on_raw
        self.port_hints = [port_hints] if isinstance(port_hints, str) else list(port_hints)
        self.callback = callback
        self.on_status = on_status or (lambda s: None)
        self.open: dict[str, object] = {}
        self._stop = threading.Event()

    def _cb(self, port_name: str):
        def handler(msg) -> None:
            try:
                _handle(msg)
            except Exception as e:  # noqa: BLE001 — rtmidi threads die silently
                self.on_status(f"callback error on {port_name!r} for {msg}: {e!r}")

        def _handle(msg) -> None:
            if self.on_raw:
                self.on_raw(port_name, msg)
            if msg.type in ("control_change", "note_on", "note_off"):
                is_cc = msg.type == "control_change"
                # NB: never getattr(msg, "control", msg.note) — the default is
                # evaluated eagerly and CC messages have no .note -> every CC
                # raised inside the rtmidi callback thread and vanished silently.
                if is_cc:
                    number, value = msg.control, msg.value
                else:
                    number = msg.note
                    value = msg.velocity if msg.type == "note_on" else 0
                self.callback({
                    "kind": "cc" if is_cc else "note",
                    "channel": msg.channel,
                    "number": number,
                    "value": value,
                    "ts": time.time(),
                    "port": port_name,
                })
        return handler

    @property
    def port_names(self) -> list[str]:
        return list(self.open)

    def run(self) -> None:
        while not self._stop.is_set():
            names = find_ports(self.port_hints)
            if not names:
                self.on_status(
                    f"no MIDI port matching {self.port_hints!r} "
                    f"(available: {mido.get_input_names()}) — retrying"
                )
            for name in names:
                if name not in self.open:
                    try:
                        self.open[name] = mido.open_input(name, callback=self._cb(name))
                        self.on_status(f"midi listening on {name!r}")
                    except Exception as e:  # noqa: BLE001
                        self.on_status(f"cannot open {name!r}: {e}")
            for name in list(self.open):
                if name not in names:
                    try:
                        self.open[name].close()
                    except Exception:  # noqa: BLE001
                        pass
                    del self.open[name]
                    self.on_status(f"midi port lost: {name!r}")
            self._stop.wait(3)

    def stop(self) -> None:
        self._stop.set()
        for p in list(self.open.values()):
            try:
                p.close()
            except Exception:  # noqa: BLE001
                pass
        self.open.clear()


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
        # port is part of the identity: two identical X1s share ch/# numbers
        key = (m["port"], m["channel"], m["kind"], m["number"])
        seen[key] = seen.get(key, 0) + 1
        print(f"[{m['port']}] ch={m['channel'] + 1:02d} {m['kind']:4s} "
              f"#{m['number']:3d} val={m['value']:3d}  (x{seen[key]})",
              flush=True)
        if rec:
            rec.write(json.dumps(m) + "\n")
            rec.flush()

    raw_count = [0]

    def raw(port: str, msg) -> None:
        raw_count[0] += 1
        if args.raw or msg.type not in ("control_change", "note_on", "note_off"):
            # non cc/note types are otherwise dropped silently — always show them
            print(f"[{port}] RAW {msg}", flush=True)

    tap = MidiTap(args.port, handle,
                  on_status=lambda s: print(f"[midi] {s}", flush=True),
                  on_raw=raw)
    print("MIDI inputs visible: " + ", ".join(mido.get_input_names()), flush=True)
    tap.start()
    print(f"watching ALL ports ~{args.port!r} — move controls now "
          f"({'%.0fs' % args.seconds if args.seconds else 'Ctrl+C'} to stop)",
          flush=True)
    deadline = time.time() + args.seconds if args.seconds else None
    try:
        while tap.is_alive():
            time.sleep(0.2)
            if deadline and time.time() > deadline:
                break
    except KeyboardInterrupt:
        pass
    finally:
        opened = tap.port_names
        tap.stop()
        if rec:
            rec.close()
        print(f"\nports opened: {len(opened)} ({', '.join(opened) or '-'})"
              f"  unique keys seen: {len(seen)}  raw messages: {raw_count[0]}")
        for (port, ch, kind, num), cnt in sorted(seen.items()):
            print(f"  [{port}] ch={ch + 1:02d} {kind:4s} #{num:3d}  x{cnt}")
        if not seen:
            print("  (no traffic — if Traktor was open, it may have the X1 fully "
                  "claimed as HID; retry with Traktor closed)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MidiMAT MIDI tap")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list MIDI ports")
    w = sub.add_parser("watch", help="print incoming MIDI messages (all matching ports)")
    w.add_argument("--port", nargs="+", default=["X1"],
                   help="port name substring(s); ALL matches are opened, "
                        "e.g. --port X1 Z1 (default: X1)")
    w.add_argument("--record", help="append raw messages to JSONL file")
    w.add_argument("--raw", action="store_true",
                   help="print every incoming message verbatim (diagnostics)")
    w.add_argument("--seconds", type=float, default=None,
                   help="auto-stop after N seconds (default: run until Ctrl+C)")
    args = parser.parse_args(argv)
    if args.cmd == "list":
        return cmd_list()
    return cmd_watch(args)


if __name__ == "__main__":
    raise SystemExit(main())