"""TSI mapping parser: MIDI key -> Traktor function description.

Format (reverse-engineered by cmdr/py-ni-traktor-tsi, verified here against the
factory 'DDJ-FLX4' TSI and the user's live 'Traktor Settings.tsi'):

    XML Entry "DeviceIO.Config.*" = base64(TLV):
      DIOM > DEVS > [count] DEVI(name) > DDAT >
        DDCB > CMAS > [count] CMAI{ midi_idx, mapping_type, cmd_id, CMAD{...} }
              DCBM > [count] DCBM{ idx, 'Ch01.CC.21' | 'Ch08.Note.B1' } <- SOURCE key
        DDDC > DDCI + DCDT{idx, control name} <- native device control definitions

    cmd_id -> human function name via traktor_tsi.constants (497 named commands).

NOTE: native NI devices (X1 MK3 in the user's live settings) carry their control
*definitions* but ZERO DDCB mappings — Traktor talks HID to them. For those,
the empirical cc_map.json (midi_tap watch + calibrate) is the source of truth.

Usage:
    python -m sidecar.tsi_parser <file.tsi> [--json] [--device=SUBSTR]
"""
from __future__ import annotations

import json
import re
import struct
import sys
from dataclasses import asdict, dataclass

import traktor_tsi.constants as tc
from traktor_tsi import decode_utf16be_str, parse_cmad, parse_tlv, parse_tsi
from traktor_tsi.tlv import find_chunk

# cmd_id -> 'XFADER_POSITION' style names (reverse of the CMD_* constants)
CMD_NAMES: dict[int, str] = {
    v: k[4:] for k, v in vars(tc).items()
    if k.startswith("CMD_") and isinstance(v, int)
}

CONTROL_TYPES = {0: "button", 1: "knob", 2: "encoder", 0xFFFF: "output"}
INTERACTION_MODES = {
    1: "toggle", 2: "direct", 3: "absolute", 4: "relative",
    5: "inc", 6: "dec", 7: "reset", 8: "output",
}

_KEY_RE = re.compile(r"^Ch(\d+)\.(CC|Note|PitchBend|ChannelAftertouch)\.(.+)$", re.I)
_NOTE_RE = re.compile(r"^([A-G])(#|b)?(-?\d+)$", re.I)
_NOTE_BASE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def note_name_to_number(name: str) -> int | None:
    """'B1' -> 35. Assumes C4 = 60 (middle C). (TBC against live X1 traffic.)"""
    m = _NOTE_RE.match(name)
    if not m:
        return None
    semis = _NOTE_BASE[m.group(1).upper()]
    if m.group(2) == "#":
        semis += 1
    elif m.group(2) == "b":
        semis -= 1
    return (int(m.group(3)) + 1) * 12 + semis


def parse_key_name(key_name: str) -> tuple[int, str, int] | None:
    "'Ch08.Note.B1' -> (7, 'note', 35) ; 'Ch01.CC.21' -> (0, 'cc', 21)"
    m = _KEY_RE.match(key_name.strip())
    if not m:
        return None
    channel = int(m.group(1)) - 1
    kind = m.group(2).lower()
    kind = "cc" if kind == "cc" else ("note" if kind == "note" else kind)
    raw = m.group(3)
    number = int(raw) if raw.isdigit() else note_name_to_number(raw)
    if number is None:
        return None
    return channel, kind, number


@dataclass
class MappingEntry:
    device: str
    key_name: str
    channel: int          # 0-based
    kind: str             # 'cc' | 'note' | ...
    number: int
    cmd_id: int
    function: str         # e.g. 'XFADER_POSITION'
    is_output: bool
    control_type: str     # button/knob/encoder/output
    interaction: str      # toggle/absolute/...
    target: int           # deck/slot/FX assignment 0-15
def parse_tsi_mappings(path: str, device_filter: str | None = None) -> list[MappingEntry]:
    binary = parse_tsi(path)
    diom = find_chunk(parse_tlv(binary), "DIOM")
    devs = find_chunk(parse_tlv(diom), "DEVS")
    entries: list[MappingEntry] = []

    for tag, devi, _ in parse_tlv(devs, offset=4):
        if tag != "DEVI":
            continue
        name, rest = decode_utf16be_str(devi, 0)
        if device_filter and device_filter.lower() not in name.lower():
            continue
        try:
            ddat = find_chunk(parse_tlv(devi, offset=rest), "DDAT")
        except KeyError:
            continue
        for t, payload, _ in parse_tlv(ddat):
            if t != "DDCB":
                continue
            inner = parse_tlv(payload)
            # DCBM: idx -> source key name ('Ch01.CC.21' / 'Ch08.Note.B1')
            key_by_idx: dict[int, str] = {}
            try:
                dcbm = find_chunk(inner, "DCBM")
            except KeyError:
                dcbm = b""
            if dcbm:
                for dt, dp, _ in parse_tlv(dcbm, offset=4):
                    if dt == "DCBM" and len(dp) >= 4:
                        idx = struct.unpack(">I", dp[:4])[0]
                        key_by_idx[idx], _ = decode_utf16be_str(dp, 4)
            # CMAS: mapping entries
            try:
                cmas = find_chunk(inner, "CMAS")
            except KeyError:
                continue
            for ct, cp, _ in parse_tlv(cmas, offset=4):
                if ct != "CMAI" or len(cp) < 12:
                    continue
                midi_idx, mtype, cmd_id = struct.unpack(">III", cp[:12])
                key_name = key_by_idx.get(midi_idx, "")
                parsed = parse_key_name(key_name)
                if not parsed:
                    continue  # outputs / unparseable names
                channel, kind, number = parsed
                cmad: dict = {}
                for ct2, cp2, _ in parse_tlv(cp[12:]):
                    if ct2 == "CMAD" and len(cp2) >= 120:
                        cmad = parse_cmad(cp2)
                entries.append(MappingEntry(
                    device=name,
                    key_name=key_name,
                    channel=channel,
                    kind=kind,
                    number=number,
                    cmd_id=cmd_id,
                    function=CMD_NAMES.get(cmd_id, f"CMD_{cmd_id}"),
                    is_output=(mtype == 1 or cmad.get("control_type") == 0xFFFF),
                    control_type=CONTROL_TYPES.get(cmad.get("control_type", -1), "unknown"),
                    interaction=INTERACTION_MODES.get(cmad.get("interaction_mode", 0), "unknown"),
                    target=cmad.get("target", -1),
                ))
    return entries


def lookup_table(entries: list[MappingEntry]) -> dict[tuple[int, str, int], MappingEntry]:
    """(channel, kind, number) -> first non-output entry."""
    table: dict[tuple[int, str, int], MappingEntry] = {}
    for e in entries:
        if e.is_output:
            continue
        table.setdefault((e.channel, e.kind, e.number), e)
    return table


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    device = next((a.split("=", 1)[1] for a in argv if a.startswith("--device=")), None)
    entries = parse_tsi_mappings(args[0], device)
    if "--json" in argv:
        print(json.dumps([asdict(e) for e in entries], indent=2))
    else:
        print(f"{len(entries)} input mappings from {args[0]}")
        for e in entries:
            print(f"  {e.device:34s} {e.key_name:18s} -> {e.function}"
                  f"  [{e.control_type}/{e.interaction} target={e.target}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))