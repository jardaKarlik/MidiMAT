"""Set the 'Generic MIDI' device's OUT-Port name in a Traktor Settings.tsi.

Traktor stores a device's MIDI port selection in the DEVI's DDPT (Device Data
PorT?) as a repeated [u32 length][UTF-16BE chars] pair:

    Generic MIDI DDPT = <in-port> <out-port>   e.g.  len4 "None"  len8 "loopMIDI"

This script rewrites ONLY that device's DDPT, leaving every other byte of the file
untouched (same surgical approach as prototype_tsi_inject.py).

Usage:
    python scripts/tsi_set_port.py --list
    python scripts/tsi_set_port.py --out MidiMAT            # write (backs up first)
    python scripts/tsi_set_port.py --out MidiMAT --dry-run
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import pathlib
import re
import shutil
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from traktor_tsi.strings import decode_utf16be_str, encode_utf16be_str  # noqa: E402
from traktor_tsi.tlv import build_tlv, find_chunk, parse_tlv  # noqa: E402
from traktor_tsi.tsi import parse_tsi  # noqa: E402

DEVICE = "Generic MIDI"


def default_tsi() -> pathlib.Path:
    """Newest 'Traktor Settings.tsi' under Documents/OneDrive Documents."""
    home = pathlib.Path.home()
    roots = [home / "Documents" / "Native Instruments",
             home / "OneDrive" / "Documents" / "Native Instruments"]
    best: pathlib.Path | None = None
    for root in roots:
        if not root.is_dir():
            continue
        for p in root.glob("Traktor*/Traktor Settings.tsi"):
            if best is None or p.stat().st_mtime > best.stat().st_mtime:
                best = p
    if best is None:
        raise SystemExit("no 'Traktor Settings.tsi' found under Documents/OneDrive")
    return best


def read_ports(ddpt: bytes) -> list[str]:
    """-> [in_port, out_port, ...] as stored (each [u32 len][utf16be])."""
    out, off = [], 0
    while off + 4 <= len(ddpt):
        n = struct.unpack(">I", ddpt[off:off + 4])[0]
        end = off + 4 + n * 2
        if end > len(ddpt):
            break
        out.append(ddpt[off + 4:end].decode("utf-16-be", errors="replace"))
        off = end
    return out


def build_ports(names: list[str]) -> bytes:
    # encode_utf16be_str already emits [u32 char-count][utf16be bytes] — the exact
    # form Traktor stores in DDPT. Do NOT add another length prefix.
    return b"".join(encode_utf16be_str(n) for n in names)


def find_device(binary: bytes, name: str):
    """-> (devi_payload, rest_offset) for the named DEVI, or None."""
    diom = find_chunk(parse_tlv(binary), "DIOM")
    devs = find_chunk(parse_tlv(diom), "DEVS")
    for tag, devi, _ in parse_tlv(devs, offset=4):
        if tag != "DEVI":
            continue
        dev_name, rest = decode_utf16be_str(devi, 0)
        if dev_name == name:
            return devi, rest
    return None


def rebuild_devi_ddpt(devi: bytes, rest_off: int, ddpt_payload: bytes) -> bytes:
    """Re-encode the DEVI with a replaced DDPT payload."""
    name_bytes = encode_utf16be_str(decode_utf16be_str(devi, 0)[0])
    rest = b""
    for t, p, _ in parse_tlv(devi, offset=rest_off):
        if t == "DDAT":
            new_ddat = b""
            for t2, p2, _ in parse_tlv(p):
                new_ddat += build_tlv("DDPT", ddpt_payload) if t2 == "DDPT" else build_tlv(t2, p2)
            rest += build_tlv("DDAT", new_ddat)
        else:
            rest += build_tlv(t, p)
    return name_bytes + rest


def rebuild_with_devi(binary: bytes, devi_name: str, new_devi: bytes) -> bytes:
    diom_payload = find_chunk(parse_tlv(binary), "DIOM")
    new_diom = b""
    for tag, payload, _ in parse_tlv(diom_payload):
        if tag != "DEVS":
            new_diom += build_tlv(tag, payload)
            continue
        count = struct.unpack(">I", payload[:4])[0]
        new_devs = struct.pack(">I", count)
        for dtag, devi, _ in parse_tlv(payload, offset=4):
            if dtag != "DEVI":
                new_devs += build_tlv(dtag, devi)
                continue
            dn = decode_utf16be_str(devi, 0)[0]
            new_devs += build_tlv(dtag, new_devi if dn == devi_name else devi)
        new_diom += build_tlv("DEVS", new_devs)
    return build_tlv("DIOM", new_diom)


def write_tsi_xml(binary: bytes, out_path: pathlib.Path, template: pathlib.Path) -> None:
    """Surgical: replace only the DeviceIO.Config Value attribute in the original text."""
    raw = template.read_text(encoding="utf-8")
    payload = base64.b64encode(binary).decode("ascii")
    pattern = re.compile(
        r'(<Entry\s+Name="DeviceIO\.Config\.[^"]*"\s+Type="\d+"\s+Value=")[^"]*(")'
    )
    new_raw, n = pattern.subn(lambda m: m.group(1) + payload + m.group(2), raw, count=1)
    if n != 1:
        raise SystemExit(f"expected 1 DeviceIO.Config entry, patched {n}")
    out_path.write_text(new_raw, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Set the Generic MIDI out-port in a Traktor TSI")
    ap.add_argument("--tsi", default=None, help="path to 'Traktor Settings.tsi'")
    ap.add_argument("--device", default=DEVICE)
    ap.add_argument("--in-port", default=None, help="leave unchanged if omitted")
    ap.add_argument("--out-port", default=None)
    ap.add_argument("--list", action="store_true", help="show current ports and exit")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    tsi = pathlib.Path(args.tsi) if args.tsi else default_tsi()
    binary = parse_tsi(str(tsi))

    found = find_device(binary, args.device)
    if not found:
        raise SystemExit(f"device {args.device!r} not found in {tsi}")
    devi, rest = found
    ddat = find_chunk(parse_tlv(devi, offset=rest), "DDAT")
    ddpt = next((p for t, p, _ in parse_tlv(ddat) if t == "DDPT"), None)
    if ddpt is None:
        raise SystemExit("device has no DDPT")
    ports = read_ports(ddpt)
    print(f"{tsi}")
    print(f"  device   : {args.device!r}")
    print(f"  ports    : {ports}   (in, out)")

    if args.list:
        return 0

    new_ports = list(ports)
    if args.in_port is not None:
        new_ports[0] = args.in_port
    if args.out_port is not None:
        if len(new_ports) < 2:
            new_ports.append(args.out_port)
        else:
            new_ports[1] = args.out_port
    if new_ports == ports:
        print("  no change requested")
        return 0

    new_ddpt = build_ports(new_ports)
    new_devi = rebuild_devi_ddpt(devi, rest, new_ddpt)
    new_binary = rebuild_with_devi(binary, args.device, new_devi)

    print(f"  new ports: {new_ports}")
    if args.dry_run:
        print("  (dry run — nothing written)")
        return 0

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = tsi.with_name(tsi.name + f".midimat-backup-{stamp}")
    shutil.copy2(tsi, backup)
    write_tsi_xml(new_binary, tsi, tsi)
    print(f"  backup   : {backup.name}")
    print(f"  written  : {tsi}  ({tsi.stat().st_size} bytes)")

    # verify by re-reading
    check = find_device(parse_tsi(str(tsi)), args.device)
    ddat2 = find_chunk(parse_tlv(check[0], offset=check[1]), "DDAT")
    ddpt2 = next((p for t, p, _ in parse_tlv(ddat2) if t == "DDPT"), None)
    print(f"  verified : {read_ports(ddpt2)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
