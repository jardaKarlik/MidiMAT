"""Phase-0 smoke test: connect to the sidecar WS, count MIDI events in 3 s."""
import asyncio
import json
import sys

import websockets


async def main() -> int:
    async with websockets.connect("ws://127.0.0.1:8787") as ws:
        hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert hello["type"] == "hello", hello
        widgets = len(hello["layout"]["widgets"])
        print(f"hello: layout with {widgets} widgets")
        count = 0
        last = None
        try:
            async with asyncio.timeout(3):
                async for raw in ws:
                    msg = json.loads(raw)
                    if msg["type"] == "midi":
                        count += 1
                        last = msg
        except TimeoutError:
            pass
        print(f"midi events in 3s: {count}, last: {last}")
        return 0 if count >= 10 and last else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))