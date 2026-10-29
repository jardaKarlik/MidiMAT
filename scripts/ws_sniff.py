"""Sniff MidiMAT WS events live — proves the server->overlay wire end-to-end.

Run: python scripts/ws_sniff.py [--seconds 12]
Then press buttons / turn knobs on the controllers.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

import websockets


async def main(seconds: float) -> int:
    async with websockets.connect("ws://127.0.0.1:8787") as ws:
        n = 0
        print(f"sniffing ws://127.0.0.1:8787 for {seconds:.0f}s — "
              "press buttons / turn knobs NOW", flush=True)
        try:
            async with asyncio.timeout(seconds):
                async for raw in ws:
                    msg = json.loads(raw)
                    if msg.get("type") == "midi":
                        n += 1
                        print(f"  {msg.get('label')!r:44s} value={msg.get('value')}")
        except TimeoutError:
            pass
        print(f"TOTAL midi events received: {n}")
        return 0 if n else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=12)
    sys.exit(asyncio.run(main(ap.parse_args().seconds)))