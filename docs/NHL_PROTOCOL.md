# NHL — Native Instruments proprietary controller protocol

> What talks between a NI controller and Traktor in **native mode**. Investigated
> 2026-10-29 because MidiMAT must see knob moves while the DJ keeps the native
> experience (the X1 MK3 can also be switched to class-compliant MIDI mode, but
> that sacrifices the native integration).

## Facts (verified on this machine unless noted)

1. **It's called NHL.** NI X1 MK2 manual: *"In Native NHL mode TRAKTOR KONTROL X1 will
   communicate directly with TRAKTOR over USB using the Native Instruments proprietary
   NHL protocol, which features high resolution translation of the knobs superior to
   MIDI."* → not MIDI; higher-resolution knob data (MK2 community RE measured **12-bit**
   knob values vs MIDI's 7-bit).
2. **It rides a vendor-defined HID interface** — enumeration (`python -m sidecar.nhl_tap
   probe`) shows **usage page 0xFF01** on all NI gear present here:

   | Device | VID:PID | Interface | Product string | Serial |
   |---|---|---|---|---|
   | X1 MK3 (unit 1) | 17CC:2200 | MI_02 | `TRAKTOR X1 MK3 HID` | 2411742B |
   | X1 MK3 (unit 2) | 17CC:2200 | MI_02 | `TRAKTOR X1 MK3 HID` | 241196A3 |
   | Z1 MK2 | 17CC:2400 | MI_05 | `Traktor Z1 MK2 HID` | 00DDBAB2 |
   | F1 | 17CC:1120 | MI_00 | `Traktor Kontrol F1` | F89850DF |

3. **The interfaces open WITHOUT Traktor (hidapi, shareable CreateFile)** — probe opened
   all 4. The remaining unknown: whether they stay readable **while Traktor has them
   open** (Traktor may open exclusive). ⇒ the decisive test below.
4. X1 MK3 mode switch: default = native/NHL; MIDI mode = class-compliant MIDI endpoints
   (that's what `midi_tap` saw after the user switched). Both device interfaces stay
   enumerated in either mode; only one protocol streams.
5. Community RE of the NHL family exists (MK2/MK1/Z1 — not MK3 yet):
   - `github.com/b0id/NI-X1MK2-Z1MK1-WebMIDI` — full HID→MIDI bridge; `X1DOCS.md`;
     30 buttons + shift layer, 8 × 12-bit FX knobs, encoders, touch strip, 51 LEDs,
     LED output reports (~51 bytes, header `80 7f …`).
   - Mixxx community HID controller presets (infiniteloop / stotes gists).
   - Linux kernel driver `hid-ni-x1` (X1 MK1).

## Decisive test (needs hands — 2 minutes)

1. Switch X1 #1 back to **native mode**, start **Traktor**, load a track.
2. `python -m sidecar.nhl_tap probe` → open still OK while Traktor runs?
3. `python -m sidecar.nhl_tap dump --seconds 15 --out nhl_raw.jsonl` → turn every knob,
   press buttons, sweep the touch strip.
4. If hex reports stream → **NHL tap confirmed**: decode by correlating turns with
   byte/bit changes (start from MK2 doc, MK3 differs but likely same family), then feed
   decoded (control,value) into the existing Resolver like MIDI events.

## Outcomes & strategy

- **NHL readable under Traktor (best):** DJ keeps native mode (12-bit feel, OLEDs, LEDs);
  `nhl_tap` becomes a second input source beside `midi_tap`; identity = serial + report
  byte offset. MK3 decoding is a bounded RE job (single fixed-size reports).
- **Traktor opens exclusively (fallback):** two viable routes —
  (a) **MIDI mode + Traktor Generic-MIDI mapping**: X1 in MIDI mode, Traktor controls it
      via a TSI mapping (we can *generate* one with `py-ni-traktor-tsi` from the CC
      layout learned by `midi_tap watch`); MidiMAT taps the same MIDI stream passively.
      Cost: native features degraded (OLEDs/LED feedback limited).
  (b) **USB-level sniffing** (USBPcap + Wireshark, admin driver): captures the wire even
      if the app is exclusive. Last resort — heavy and fragile.

## ✅ DECISIVE TEST PASSED (2026-10-29, Traktor Pro 4 running, PID 45440)

**NHL input reports stream to our reader while Traktor runs** — all vendor interfaces
openable concurrently, reports captured from X1 MK3 unit 1, Z1 MK2, and F1
(samples: `docs/nhl_samples/capture_01_x1u1_f1.jsonl`, `capture_02_z1_faders.jsonl`).
⇒ Strategy A confirmed: DJ keeps **native mode**; MidiMAT taps NHL directly.
(MIDI-OX cannot see this traffic — it's MIDI-only; NHL is vendor HID.)

## Report formats — first-pass decode (from live captures)

All reports start with `01` (report id / protocol tag).

**X1 MK3 — 25 bytes** (`TRAKTOR X1 MK3 HID`):
| Bytes | Hypothesis | Evidence |
|---|---|---|
| [1] | page/mode enum (0/1/2/4 seen; 0 at idle) | toggles near FX-page/shift presses |
| [2],[5] | button bitfields (single-bit events: 0x02, 0x10 seen) | momentary one-report blips |
| [7:9] | **FX knob 1 — absolute, LE16 ≈ 12-bit (0-4095)** | `e7 03→e7 04` = +256 fast turn; `e9 09→e0 09` = −1 slow turns; wrap 0x9E0→0x9EF on direction change |
| [9:19] | 5 × knob LE16 pairs, rest at `ff 07` = 0x7FF = 2047 center | untouched knobs sit at center detent |
| [19:25] | 3 × LE16 (0x08BC, 0x0B34, 0x09D5 ≈ around center) | browse/tempo/strip candidates |

**Z1 MK2 — 35 bytes** (`Traktor Z1 MK2 HID`): knobs/faders as LE16 pairs
(`b0 08`, `0b 06`, `40 07`, `70 07` ≈ faders near center 1856/1904, one `ff 0f` = 0xFFF
max); **fader/crossfader sweep visible at [31:33] LE16** (`12 00→76 00` fast sweep).

**F1 — 22 bytes** (`Traktor Kontrol F1`): 8 × LE16 knob/pad values
(`c8 07`, `98 07`, `f0 0f`≈4080 …).

**Next (Phase 2 RE):** guided `nhl_tap learn` — one control at a time, baseline-diff
reports → per-control byte maps → `nhl_map.json` (serial + offset → control) feeding the
same Resolver pipeline as MIDI. Resolution beyond MIDI (12-bit) is free once decoded.

## Tooling

- `python -m sidecar.nhl_tap probe` — enumerate + open-test vendor HID (usage page ≥ 0xFF00)
- `python -m sidecar.nhl_tap dump [--seconds N] [--out FILE] [--pid 0x2200]` — raw report
  capture (hex + timestamps + serials) → JSONL for decoding sessions