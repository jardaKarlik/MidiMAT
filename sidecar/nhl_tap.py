"""NHL (Native Instruments proprietary HID) tap — probe & raw report dumper.

NI controllers talk to Traktor over a vendor-defined HID interface ("NHL mode",
see X1 MK2 manual: "proprietary NHL protocol … superior to MIDI"). On Windows
those interfaces are enumerated (VID 17CC) and — hypothesis to TEST — readable
by a second app (hidapi opens shareable) while Traktor runs.

This machine:
    X1 MK3  x2 : VID_17CC PID_2200  vendor-HID on interface MI_02
    Z1 MK2     : VID_17CC PID_2400  vendor-HID on interface MI_05
    F1         : VID_17CC PID_1120  vendor-HID on interface MI_00

Usage:
    python -m sidecar.nhl_tap probe
    python -m sidecar.nhl_tap dump --seconds 10 [--out nhl_raw.jsonl]
        (switch the X1 to native mode + open Traktor first, then turn knobs;
         each report is logged as hex + timestamp for later decoding)

Protocol references for decoding (MK2 family, MK3 TBD by capture):
    github.com/b0id/NI-X1MK2-Z1MK1-WebMIDI  (X1DOCS.md, 12-bit knobs, LED report)
    Mixxx community HID presets (infiniteloop / stotes gists)
"""
from __future__ import annotations

import argparse
import json
import time

try:
    import hid  # cython-hidapi
except ImportError:  # pragma: no cover
    hid = None

NI_VID = 0x17CC
VENDOR_USAGE_MIN = 0xFF00  # vendor-defined usage pages live here (0xFF00-0xFFFF)


def _require_hid() -> None:
    if hid is None:
        raise SystemExit(
            "hidapi not installed in THIS python.\n"
            "  Use the project venv:  .\\.venv\\Scripts\\python.exe -m sidecar.nhl_tap ...\n"
            "  (or the wrapper:      .\\scripts\\nhl.ps1 probe)"
        )


def ni_devices() -> list[dict]:
    _require_hid()
    return [d for d in hid.enumerate(NI_VID, 0)
            if d.get("interface_number", -1) >= 0]


def is_vendor(d: dict) -> bool:
    return d.get("usage_page", 0) >= VENDOR_USAGE_MIN


def cmd_probe(_args: argparse.Namespace) -> int:
    devs = ni_devices()
    print(f"{len(devs)} Native Instruments HID interfaces (VID 17CC):\n")
    for d in devs:
        vendor = "VENDOR-NHL" if is_vendor(d) else "standard "
        print(f"  [{vendor}] pid=0x{d['product_id']:04X} iface=MI_{d['interface_number']:02d} "
              f"usage_page=0x{d['usage_page']:04X} usage=0x{d['usage']:04X} "
              f"prod={d['product_string']!r} serial={d['serial_number']!r}")
    print("\nopen test (vendor interfaces):")
    ok = 0
    for d in devs:
        if not is_vendor(d):
            continue
        try:
            dev = hid.device()
            dev.open_path(d["path"])
            dev.set_nonblocking(True)
            rep = dev.read(64)  # nonblocking: [] when idle
            print(f"  OK   pid=0x{d['product_id']:04X} serial={d['serial_number']!r} "
                  f"— interface OPENED ({len(rep)} bytes pending)")
            dev.close()
            ok += 1
        except Exception as e:  # noqa: BLE001
            print(f"  FAIL pid=0x{d['product_id']:04X} serial={d['serial_number']!r} — {e}")
    print(f"\n{ok} vendor interface(s) readable WITHOUT Traktor. "
          f"Next: switch X1 to native mode, open Traktor, re-run probe — "
          f"if OK there too, we can tap NHL live.")
    return 0


def cmd_dump(args: argparse.Namespace) -> int:
    devs = [d for d in ni_devices() if is_vendor(d)]
    if args.pid:
        devs = [d for d in devs if d["product_id"] == int(args.pid, 0)]
    if not devs:
        raise SystemExit("no vendor NHL interfaces found (X1s in MIDI mode only?)")

    handles: list[tuple[dict, object]] = []
    for d in devs:
        try:
            dev = hid.device()
            dev.open_path(d["path"])
            dev.set_nonblocking(True)
            handles.append((d, dev))
        except Exception as e:  # noqa: BLE001
            print(f"open FAIL pid=0x{d['product_id']:04X} "
                  f"serial={d['serial_number']!r}: {e}")
    if not handles:
        raise SystemExit("nothing opened")

    out = open(args.out, "a", encoding="utf-8") if args.out else None
    if out:
        for d, _ in handles:
            rec = {"device": {k: (v.decode(errors="replace") if isinstance(v, bytes) else v)
                              for k, v in d.items() if k != "path"},
                   "ts_start": time.time()}
            out.write(json.dumps(rec) + "\n")

    print(f"capturing {len(handles)} interfaces for {args.seconds:.0f}s — "
          f"turn knobs NOW (X1 MK3: WAKE WITH A BUTTON PRESS, knobs alone don't wake it!)",
          flush=True)
    start = time.time()
    deadline = start + args.seconds
    counts: dict[str, int] = {}
    last_beat = start
    last_refresh = start
    total = 0
    while time.time() < deadline:
        progressed = False
        for d, dev in handles:
            rep = dev.read(256)
            if rep:
                progressed = True
                total += 1
                serial = d["serial_number"]
                counts[serial] = counts.get(serial, 0) + 1
                last_event_at = time.time()
                entry = {"t": round(time.time(), 4), "serial": serial,
                         "pid": d["product_id"], "len": len(rep),
                         "hex": bytes(rep).hex()}
                print(f"  {entry['t']} [{serial}] len={len(rep):3d} {entry['hex']}",
                      flush=True)
                if out:
                    out.write(json.dumps(entry) + "\n")
                    out.flush()  # a killed capture must never lose the buffer
        now = time.time()
        # X1 MK3 sleeps after idle: reopen handles periodically & when everything
        # is stale, so a sleep/wake re-enumeration can't orphan us silently.
        if now - last_refresh >= 20 and not progressed:
            print(f"  [{now - start:5.0f}s] all silent "
                  f"({total} reports) — refreshing handles", flush=True)
            last_refresh = now
            for _, dev in handles:
                try:
                    dev.close()
                except Exception:  # noqa: BLE001
                    pass
            handles.clear()
            for d in ni_devices():
                if not is_vendor(d):
                    continue
                try:
                    ndev = hid.device()
                    ndev.open_path(d["path"])
                    ndev.set_nonblocking(True)
                    handles.append((d, ndev))
                except Exception as e:  # noqa: BLE001
                    print(f"reopen FAIL serial={d['serial_number']!r}: {e}", flush=True)
        if now - last_beat >= 5:
            print(f"  [{now - start:5.0f}s] listening… {total} reports "
                  f"({', '.join(f'{s}:{c}' for s, c in counts.items()) or 'none'})",
                  flush=True)
            last_beat = now
        if not progressed:
            time.sleep(0.002)  # don't spin

    for _, dev in handles:
        dev.close()
    if out:
        out.close()
    print(f"\n{total} reports: " + ", ".join(f"{s}×{c}" for s, c in counts.items())
          or "0 reports")
    if out:
        print(f"appended to {args.out}")
    if total == 0:
        print("no traffic — X1s in NATIVE mode? Traktor open? controls actually moved?")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="MidiMAT NHL (NI proprietary HID) tap")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("probe", help="enumerate + open-test vendor HID interfaces")
    dp = sub.add_parser("dump", help="capture raw NHL reports to JSONL")
    dp.add_argument("--seconds", type=float, default=10)
    dp.add_argument("--out", default="nhl_raw.jsonl")
    dp.add_argument("--pid", help="only this device, e.g. 0x2200 (one X1 MK3)")
    args = ap.parse_args(argv)
    if args.cmd == "probe":
        return cmd_probe(args)
    return cmd_dump(args)


if __name__ == "__main__":
    raise SystemExit(main())