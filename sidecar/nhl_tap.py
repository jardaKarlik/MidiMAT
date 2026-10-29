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
        raise SystemExit("hidapi not installed — pip install hidapi")


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
    out = open(args.out, "a", encoding="utf-8") if args.out else None
    deadline = time.time() + args.seconds
    total = 0
    for d in devs:
        try:
            dev = hid.device()
            dev.open_path(d["path"])
            dev.set_nonblocking(True)
        except Exception as e:  # noqa: BLE001
            log = f"pid=0x{d['product_id']:04X} serial={d['serial_number']!r}"
            print(f"open FAIL {log}: {e}")
            continue
        info = (f"pid=0x{d['product_id']:04X} iface=MI_{d['interface_number']:02d} "
                f"serial={d['serial_number']!r}")
        print(f"dumping {info} for {args.seconds:.0f}s — turn knobs/press buttons!")
        rec = {"device": {k: (v.decode(errors="replace") if isinstance(v, bytes) else v)
                          for k, v in d.items() if k != "path"},
               "ts_start": time.time()}
        if out:
            out.write(json.dumps(rec) + "\n")
        while time.time() < deadline:
            rep = dev.read(256)
            if rep:
                total += 1
                entry = {"t": round(time.time(), 4),
                         "serial": d["serial_number"],
                         "len": len(rep),
                         "hex": bytes(rep).hex()}
                print(f"  {entry['t']} [{d['serial_number']}] len={len(rep):3d} "
                      f"{entry['hex']}")
                if out:
                    out.write(json.dumps(entry) + "\n")
            else:
                time.sleep(0.002)  # don't spin
        dev.close()
    if out:
        out.close()
        print(f"\n{total} reports appended to {args.out}")
    else:
        print(f"\n{total} reports captured")
    if total == 0:
        print("no traffic — is the X1 in NATIVE mode with Traktor open and in use?")
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