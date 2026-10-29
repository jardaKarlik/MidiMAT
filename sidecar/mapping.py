"""Resolution pipeline: raw MIDI message -> widget/label/deck for the overlay.

Sources (priority: empirical cc_map.json > static TSI > none):
  1. cc_map.json   — learned with `python -m sidecar.midi_tap watch` + hand/annotation;
                     the source of truth for NATIVE devices (X1 MK3) whose TSI DDCB
                     is empty (Traktor talks HID, not MIDI mapping, to them).
  2. TSI export    — (channel,kind,number) -> cmd_id -> function name
                     (python -m sidecar.tsi_parser file.tsi).

cc_map.json schema:
{
  "port_hint": "X1 MK3",
  "page_buttons": [{"channel": 0, "kind": "note", "number": 32, "page": "fx"}],
  "entries": [
    {"channel": 0, "kind": "cc", "number": 21, "page": "fx",
     "label": "FX1 · Dry/Wet", "deck": "FX", "widget": "fx1_drywet"}
  ]
}
Entries without "page" match in every page.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger("midimat.mapping")


class Resolver:
    def __init__(self, cc_map_path: str | Path | None = None,
                 tsi_path: str | Path | None = None):
        self.entries: list[dict] = []
        self.page_buttons: list[dict] = []
        self.port_hint: str | None = None
        self.tsi_table: dict = {}
        self.current_page: str | None = None
        if cc_map_path and Path(cc_map_path).exists():
            self._load_cc_map(cc_map_path)
        if tsi_path and Path(tsi_path).exists():
            self._load_tsi(tsi_path)

    def _load_cc_map(self, path) -> None:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.port_hint = data.get("port_hint")
        self.page_buttons = data.get("page_buttons", [])
        self.entries = data.get("entries", [])
        log.info("cc_map: %d entries, %d page buttons from %s",
                 len(self.entries), len(self.page_buttons), path)

    def _load_tsi(self, path) -> None:
        try:
            try:
                from sidecar.tsi_parser import lookup_table, parse_tsi_mappings
            except ImportError:  # flat script execution
                from tsi_parser import lookup_table, parse_tsi_mappings
            self.tsi_table = lookup_table(parse_tsi_mappings(str(path)))
            log.info("tsi: %d static mappings from %s", len(self.tsi_table), path)
        except Exception as e:  # noqa: BLE001
            log.warning("tsi load failed (%s) — cc_map only", e)

    @staticmethod
    def _matches(msg: dict, spec: dict) -> bool:
        # optional "port": substring of the MIDI port name — with two identical
        # units (two X1 MK3s) port + channel + kind + number is the real identity
        port_spec = spec.get("port")
        if port_spec and port_spec.lower() not in (msg.get("port") or "").lower():
            return False
        return (msg.get("channel") == spec.get("channel")
                and msg.get("kind") == spec.get("kind")
                and msg.get("number") == spec.get("number"))

    def resolve(self, msg: dict) -> dict | None:
        """Returns {label, deck, widget, page} or None (unknown/ignored key)."""
        # page buttons switch context first
        for pb in self.page_buttons:
            if self._matches(msg, pb) and msg.get("value", 0) > 0:
                self.current_page = pb.get("page")
                log.debug("page -> %s", self.current_page)
                return None
        # empirical cc_map (page-scoped, then pageless)
        for scope in (lambda e: e.get("page") == self.current_page,
                      lambda e: "page" not in e):
            for e in self.entries:
                if scope(e) and self._matches(msg, e):
                    return {"label": e.get("label"), "deck": e.get("deck"),
                            "widget": e.get("widget"), "page": e.get("page")}
        # static TSI fallback: semantics only, no widget (HUD-only until calibrated)
        if self.tsi_table:
            key = (msg.get("channel"), msg.get("kind"), msg.get("number"))
            hit = self.tsi_table.get(key)
            if hit and not hit.is_output:
                return {"label": hit.function.replace("_", " ").title(),
                        "deck": None, "widget": None, "page": None}
        return None


def load_resolver(config_path: str | Path = "midimat.config.json") -> Resolver:
    """Build a Resolver from midimat.config.json (missing file => empty resolver)."""
    cfg: dict = {}
    p = Path(config_path)
    if p.exists():
        cfg = json.loads(p.read_text(encoding="utf-8"))
    return Resolver(cc_map_path=cfg.get("cc_map"), tsi_path=cfg.get("tsi"))