# Acknowledgements

MidiMAT wouldn't exist without the people who documented, reverse-engineered, or
simply built the things it stands on. Thank you.

## The DJ ecosystem

- **Native Instruments** — for Traktor Pro and the KONTROL hardware line. MidiMAT is an
  independent companion tool and is **not affiliated with, endorsed by, or sponsored by
  Native Instruments**. *Traktor* is a trademark of Native Instruments GmbH.
- **Tobias Erichsen** — for [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html)
  and [rtpMIDI](https://www.tobias-erichsen.de/software/rtpmidi.html), the virtual MIDI
  ports that make the Windows MIDI path possible.
- **OBS Project** — for OBS Studio and its Browser Source, which renders the overlay
  with no plugin required.

## Reverse-engineering & community research

- **`github.com/b0id/NI-X1MK2-Z1MK1-WebMIDI`** — HID↔MIDI bridge and protocol notes for
  the X1 MK2 / Z1 MK1 family, which mapped out the ground for the NHL research.
- **Mixxx community HID presets** (infiniteloop, stotes) and the Linux `hid-ni-x1`
  kernel driver — additional reference points for the native protocol.
- **cmdr / `py-ni-traktor-tsi`** — for cracking the Traktor `.tsi` container and publishing
  the TLV chunk grammar.

## Open-source software

### Runtime (shipped)

| Project | License |
|---|---|
| [websockets](https://github.com/python-websockets/websockets) | BSD-3-Clause |
| [mido](https://github.com/mido/mido) | MIT |
| [python-rtmidi](https://github.com/SpotlightKid/python-rtmidi) | MIT |
| [py-ni-traktor-tsi](https://github.com/cmdr/py-ni-traktor-tsi) | MIT |
| [hidapi](https://github.com/trezor/cython-hidapi) | BSD-3-Clause / MIT |
| [OpenCV](https://opencv.org/) (`opencv-python`) | Apache-2.0 |
| [NumPy](https://numpy.org/) | BSD-3-Clause |
| [PyInstaller](https://pyinstaller.org/) | GPL-2.0 **with the exception** that allows bundling into proprietary/commercial apps |
| [Windows App SDK](https://github.com/microsoft/WindowsAppSDK) | MIT |
| [WebView2](https://developer.microsoft.com/microsoft-edge/webview2/) | Microsoft |
| [React](https://react.dev/) · [Vite](https://vitejs.dev/) · [Tailwind CSS](https://tailwindcss.com/) | MIT |
| [Framer Motion](https://www.framer.com/motion/) · [Lucide](https://lucide.dev/) | MIT |
| [Inter](https://rsms.me/inter/) · [JetBrains Mono](https://www.jetbrains.com/lp/mono/) | SIL OFL 1.1 |

### Optional / development only

| Project | License | Note |
|---|---|---|
| [Ultralytics YOLO](https://github.com/ultralytics/ultralytics) | **AGPL-3.0** | Used **only** for the optional auto-placement feature and for training the detector. It is **not** bundled with releases and is not a runtime dependency of the core overlay. If you build the vision feature into your own distribution, the AGPL applies to that combination. |

If any credit is missing, that's an oversight — please open an issue and it'll be fixed.
