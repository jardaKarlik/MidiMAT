"""Exploration: dump the TLV structure of a real TSI to locate MIDI keys.

Usage: python scripts/explore_tsi.py [path_to.tsi]
"""
import struct
import sys
from pathlib import Path

from traktor_tsi import decode_utf16be_str, parse_tlv, parse_tsi
from traktor_tsi.tlv import find_chunk

DEFAULT = Path.home() / (
    "OneDrive/Documents/Native Instruments/Traktor 4.5.1/Traktor Settings.tsi"
)


def walk(data: bytes, depth: int = 0, max_depth: int = 4, label: str = "") -> None:
    pad = "  " * depth
    try:
        chunks = parse_tlv(data)
    except Exception as e:  # noqa: BLE001
        print(f"{pad}{label}<not tlv: {e}>")
        return
    for tag, payload, _ in chunks:
        line = f"{pad}{label}{tag} len={len(payload)}"
        if tag in ("DEVI",) or len(payload) < 200:
            # try to show a utf16 string head
            try:
                s, _ = decode_utf16be_str(payload, 0)
                if s and s.isprintable():
                    line += f" str={s[:60]!r}"
            except Exception:  # noqa: BLE001
                pass
        print(line)
        if depth < max_depth and tag in (
            "DIOM", "DEVS", "DEVI", "DDAT", "DDDC", "DDCB", "CMAS", "DCBM", "DIOI",
        ):
            offset = 4 if tag in ("DEVS", "DDCB", "CMAS", "DCBM", "DDDC") else 0
            walk(payload, depth + 1, max_depth, "" if offset else "")


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    binary = parse_tsi(str(path))
    print(f"file: {path}\nblob: {len(binary)} bytes\n")

    diom = find_chunk(parse_tlv(binary), "DIOM")
    devs = find_chunk(parse_tlv(diom), "DEVS")
    dev_count = struct.unpack(">I", devs[:4])[0]
    print(f"DEVS: {dev_count} devices\n")

    for d, (tag, devi, _) in enumerate(parse_tlv(devs, offset=4)):
        if tag != "DEVI":
            continue
        name, rest = decode_utf16be_str(devi, 0)
        ddat = find_chunk(parse_tlv(devi, offset=rest), "DDAT")
        subtags = [t for t, _, _ in parse_tlv(ddat)]
        print(f"[{d}] {name!r}  DDAT={subtags}")

        for t, payload, _ in parse_tlv(ddat):
            if t != "DDCB":
                continue
            inner = parse_tlv(payload)
            cmas = find_chunk(inner, "CMAS")
            count = struct.unpack(">I", cmas[:4])[0]
            print(f"    DDCB: {count} mapping entries")
            for i, (ct, cp, _) in enumerate(parse_tlv(cmas, offset=4)):
                if ct != "CMAI" or i >= 3:
                    continue
                midi_idx, mtype, cmd = struct.unpack(">III", cp[:12])
                print(f"      CMAI[{i}]: midi_idx={midi_idx} type={mtype} cmd={cmd}")
                for ct2, cp2, _ in parse_tlv(cp[12:]):
                    print(f"        {ct2} len={len(cp2)} head={cp2[:32].hex()}")
            try:
                dcbm = find_chunk(inner, "DCBM")
                n2 = struct.unpack(">I", dcbm[:4])[0]
                print(f"      DCBM: {n2} control names")
                for i, (dt, dp, _) in enumerate(parse_tlv(dcbm, offset=4)):
                    if dt == "DCBM" and i < 10:
                        idx = struct.unpack(">I", dp[:4])[0]
                        nm, _ = decode_utf16be_str(dp, 4)
                        print(f"        [{idx}] {nm!r}")
            except KeyError:
                pass
        # also show DDPT / other chunks raw heads
        for t, payload, _ in parse_tlv(ddat):
            if t in ("DDPT", "DDIF", "DDIV"):
                print(f"    {t} head={payload[:40].hex()}")
        print()


if __name__ == "__main__":
    main()