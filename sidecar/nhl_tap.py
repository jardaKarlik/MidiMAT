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
import threading
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


# --- Live tap (feeds the sidecar server) -------------------------------------

NHL_DEVICES = {  # pid -> (nick, knob-slot byte offsets for LE16 pairs)
    0x2200: ("X1", list(range(7, 24, 2))),   # X1 MK3: 9 analog slots + buttons [1..6]
    0x2400: ("Z1", list(range(3, 34, 2))),   # Z1 MK2: knobs/faders incl. crossfader @31
    0x1120: ("F1", list(range(6, 21, 2))),   # F1: 8 analog slots + buttons [1..5]
}
BUTTON_OFFSETS = {0x2200: range(1, 7), 0x2400: range(1, 3), 0x1120: range(1, 6)}
RAW_MAX = 4095  # 12-bit


def device_nick(pid: int, serial: str) -> str:
    base = NHL_DEVICES.get(pid, ("NI", []))[0]
    return f"{base}·{serial[-4:]}" if base == "X1" else base


def decode_changes(pid: int, data: list[int], prev: dict) -> list[dict]:
    """Diff a raw report against per-serial previous state -> normalized events.

    PROVISIONAL naming (byte-offset based) until the guided learn session builds
    real control names -> nhl_map.json. Values normalized 0-4095 -> 0-127.
    """
    nick_slots = NHL_DEVICES.get(pid)
    if not nick_slots or len(data) < 4 or data[0] != 0x01:
        return []
    _, slots = nick_slots
    events: list[dict] = []
    for off in slots:
        if off + 1 >= len(data):
            break
        raw12 = data[off] | ((data[off + 1] & 0x0F) << 8)
        if raw12 > RAW_MAX:
            raw12 &= RAW_MAX
        if prev.get(off) != raw12:
            prev[off] = raw12
            events.append({"slot": f"knob{off:02d}", "kind": "knob",
                           "name": f"Knob[{off}:{off + 2}]",
                           "value": round(raw12 * 127 / RAW_MAX),
                           "raw": raw12})
    for off in BUTTON_OFFSETS.get(pid, ()):  # one-shot bit events
        if off >= len(data):
            break
        bit = data[off]
        if prev.get(f"b{off}") != bit:
            prev[f"b{off}"] = bit
            events.append({"slot": f"btn{off:02d}", "kind": "button",
                           "name": f"Btn[{off}]={'ON' if bit else 'off'}",
                           "value": 127 if bit else 0,
                           "raw": bit})
    return events


class NhlTap(threading.Thread):
    """Background NHL listener over all vendor-HID interfaces (hot-plug + sleep
    resilient: rescans every 3 s, refreshes handles after 15 s of total silence)."""

    def __init__(self, callback, on_status=None):
        super().__init__(daemon=True, name="nhl-tap")
        self.callback = callback
        self.on_status = on_status or (lambda s: None)
        self.handles: list[tuple[dict, object]] = []
        self._stop = threading.Event()

    def _refresh(self) -> None:
        wanted = {d["path"]: d for d in ni_devices() if is_vendor(d)}
        for d, dev in list(self.handles):  # handles store (device_dict, handle)
            if d["path"] not in wanted:
                try:
                    dev.close()
                except Exception:  # noqa: BLE001
                    pass
                self.handles = [h for h in self.handles if h[0]["path"] != d["path"]]
        for path, d in wanted.items():
            if any(h[0]["path"] == path for h in self.handles):
                continue
            try:
                dev = hid.device()
                dev.open_path(path)
                dev.set_nonblocking(True)
                self.handles.append((d, dev))
                self.on_status(f"nhl listening on {d['product_string']!r} "
                               f"({d['serial_number']})")
            except Exception as e:  # noqa: BLE001
                self.on_status(f"nhl open fail {d['serial_number']!r}: {e}")

    def run(self) -> None:
        last_refresh = 0.0
        last_activity = time.time()
        reports_total = 0
        last_alive = time.time()
        while not self._stop.is_set():
            try:
                now = time.time()
                if now - last_refresh >= 3 or not self.handles:
                    self._refresh()
                    last_refresh = now
                activity = False
                for d, dev in self.handles:
                    try:
                        rep = dev.read(256)
                    except Exception:  # noqa: BLE001
                        rep = []
                    if rep:
                        activity = True
                        reports_total += 1
                        self.callback({"serial": d["serial_number"],
                                       "pid": d["product_id"], "data": list(rep)})
                if activity:
                    last_activity = time.time()
                elif now - last_activity >= 15:  # everyone silent -> force reopen
                    for _, dev in self.handles:
                        try:
                            dev.close()
                        except Exception:  # noqa: BLE001
                            pass
                    self.handles.clear()
                    last_activity = now
                    self.on_status("all silent >15s — reopening handles")
                if now - last_alive >= 15:  # alive-proof heartbeat (silence is loud)
                    self.on_status(
                        f"tap alive: {len(self.handles)} handles open, "
                        f"{reports_total} reports total"
                        + ("" if reports_total else
                           " — devices asleep? press a button, then TURN A KNOB")
                    )
                    last_alive = now
                time.sleep(0.002)
            except Exception as e:  # noqa: BLE001 — never die silently
                self.on_status(f"tap loop error (restarting): {e!r}")
                time.sleep(1)

    def stop(self) -> None:
        self._stop.set()
        for _, dev in self.handles:
            try:
                dev.close()
            except Exception:  # noqa: BLE001
                pass
        self.handles.clear()


# --- Guided learn: name the byte-offset slots --------------------------------

PLANS = {
    "z1": {
        "pid": 0x2400,
        "controls": [  # (prompt name, widget id in layout.json or None)
            ("Filter A", "z1_fltr_a"), ("EQ High A", "z1_eq_hi_a"),
            ("EQ Mid A", "z1_eq_mid_a"), ("EQ Low A", "z1_eq_lo_a"),
            ("Channel Fader A", "z1_fader_a"),
            ("Filter B", "z1_fltr_b"), ("EQ High B", "z1_eq_hi_b"),
            ("EQ Mid B", "z1_eq_mid_b"), ("EQ Low B", "z1_eq_lo_b"),
            ("Channel Fader B", "z1_fader_b"),
            ("Crossfader", "z1_xfade"),
        ],
    },
    "x1": {
        "pid": 0x2200,
        "controls": [(f"X1 Knob {i + 1}", None) for i in range(9)],
    },
}


def cmd_learn(args: argparse.Namespace) -> int:
    """Non-interactive guided capture: print prompts, record timed windows."""
    plan = PLANS[args.plan]
    devs = [d for d in ni_devices()
            if is_vendor(d) and d["product_id"] == plan["pid"]]
    if args.serial:
        devs = [d for d in devs if d["serial_number"] == args.serial]
    if not devs:
        raise SystemExit(f"no device for plan {args.plan!r}")
    handles = []
    for d in devs:
        dev = hid.device()
        dev.open_path(d["path"])
        dev.set_nonblocking(True)
        handles.append((d, dev))

    out = open(args.out, "a", encoding="utf-8")
    per = args.seconds_per
    print(f"\nLEARN SESSION — plan {args.plan}, {len(plan['controls'])} controls "
          f"x {per:.0f}s. Sweep each control FULLY when prompted!\n", flush=True)
    for i, (name, _) in enumerate(plan["controls"], 1):
        print(f"  {i:2d}. {name}", flush=True)
    time.sleep(3)
    total = 0
    for name, widget in plan["controls"]:
        t0 = time.time()
        print(f"\n>>>  SWEEP NOW: {name}  ({per:.0f}s)", flush=True)
        out.write(json.dumps({"type": "marker", "control": name, "widget": widget,
                              "t_start": t0, "t_end": t0 + per}) + "\n")
        deadline = t0 + per
        while time.time() < deadline:
            for d, dev in handles:
                rep = dev.read(256)
                if rep:
                    total += 1
                    out.write(json.dumps({
                        "t": round(time.time(), 4), "serial": d["serial_number"],
                        "pid": d["product_id"], "len": len(rep),
                        "hex": bytes(rep).hex()}) + "\n")
            time.sleep(0.002)
    out.close()
    for _, dev in handles:
        dev.close()
    print(f"\ndone — {total} reports captured. Run: "
          f"python -m sidecar.nhl_tap learnmap --plan {args.plan}", flush=True)
    return 0


def cmd_learnmap(args: argparse.Namespace) -> int:
    """Analyze a learn capture -> nhl_map.json (slot -> {name, widget})."""
    plan = PLANS[args.plan]
    pid = plan["pid"]
    windows = []  # (control, widget, t_start, t_end, {slot: [raw12...]})
    per_slot_vals: list[dict[str, list[int]]] = []
    for line in Path(args.capture).read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if rec.get("type") == "marker":
            windows.append([rec["control"], rec.get("widget"),
                            rec["t_start"], rec["t_end"], {}])
            per_slot_vals.append({})
            continue
        if "hex" not in rec or rec.get("pid") != pid or not windows:
            continue
        if not (windows[-1][2] <= rec["t"] <= windows[-1][3] + 0.3):
            continue
        data = list(bytes.fromhex(rec["hex"]))
        if len(data) < 4 or data[0] != 0x01:
            continue
        _, slots = NHL_DEVICES[pid]
        for off in slots:
            if off + 1 >= len(data):
                break
            raw12 = (data[off] | ((data[off + 1] & 0x0F) << 8)) & RAW_MAX
            per_slot_vals[-1].setdefault(f"knob{off:02d}", []).append(raw12)

    mapping: dict[str, dict] = {}
    used: set[str] = set()
    problems = []
    for (control, widget, *_rest), vals in zip(windows, per_slot_vals):
        best, best_range = None, -1
        for slot, series in vals.items():
            if slot in used or not series:
                continue
            rng = max(series) - min(series)
            if rng > best_range:
                best, best_range = slot, rng
        if best is None or best_range < 40:
            problems.append(f"{control}: no clear movement (best range {best_range})")
            continue
        used.add(best)
        mapping[best] = {"name": control}
        if widget:
            mapping[best]["widget"] = widget
        print(f"  {best} -> {control:18s} (range {best_range})"
              + (f" -> widget {widget}" if widget else ""))

    out_path = Path(args.out)
    data_out: dict = {}
    if out_path.exists():
        data_out = json.loads(out_path.read_text(encoding="utf-8"))
    data_out[str(pid)] = mapping
    out_path.write_text(json.dumps(data_out, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {len(mapping)} mappings for pid 0x{pid:04X} -> {out_path}")
    for p in problems:
        print(f"  WARN {p}")
    if problems:
        print("re-run the learn session for the missed controls")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="MidiMAT NHL (NI proprietary HID) tap")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("probe", help="enumerate + open-test vendor HID interfaces")
    dp = sub.add_parser("dump", help="capture raw NHL reports to JSONL")
    dp.add_argument("--seconds", type=float, default=10)
    dp.add_argument("--out", default="nhl_raw.jsonl")
    dp.add_argument("--pid", help="only this device, e.g. 0x2200 (one X1 MK3)")
    sub.add_parser("probe", help="enumerate + open-test vendor HID interfaces")
    for name in ("learn", "learnmap"):
        lp = sub.add_parser(name, help=f"{name}: guided control naming (see docs)")
        lp.add_argument("--plan", choices=sorted(PLANS), default="z1")
        if name == "learn":
            lp.add_argument("--seconds-per", type=float, default=7)
            lp.add_argument("--serial", help="limit to one unit (two X1s present)")
            lp.add_argument("--out", default="nhl_learn.jsonl")
        else:
            lp.add_argument("--capture", default="nhl_learn.jsonl")
            lp.add_argument("--out", default="nhl_map.json")
    args = ap.parse_args(argv)
    if args.cmd == "probe":
        return cmd_probe(args)
    if args.cmd == "learn":
        return cmd_learn(args)
    if args.cmd == "learnmap":
        return cmd_learnmap(args)
    return cmd_dump(args)


if __name__ == "__main__":
    raise SystemExit(main())