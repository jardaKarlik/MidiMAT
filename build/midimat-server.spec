# PyInstaller spec for the MidiMAT sidecar.
#
# Build:  .venv\Scripts\python.exe -m PyInstaller build\midimat-server.spec --noconfirm --clean
# Output: build\dist\midimat-server\   (onedir — see DESIGN_APP.md §7)
#
# onedir (not onefile): instant start, no self-extraction, and far friendlier to
# antivirus heuristics. The data files (overlay/, layout.json, cc_map.json, …) are
# placed NEXT TO the exe, which is where sidecar/server.py looks when frozen.
#
# DELIBERATELY EXCLUDED:
#   ultralytics / torch / torchvision  -> ~2 GB, and Ultralytics is AGPL-3.0.
#   The vision "Suggest (AI)" detector is an OPTIONAL user-installed extra; the
#   bundled OpenCV detector works without it. See ACKNOWLEDGEMENTS.md.

import pathlib

# SPECPATH is the directory containing this .spec (repo/build).
REPO = pathlib.Path(SPECPATH).resolve().parent

datas = [
    (str(REPO / "overlay"), "overlay"),
    (str(REPO / "mapping"), "mapping"),
    (str(REPO / "layout.json"), "."),
    (str(REPO / "cc_map.json"), "."),
    (str(REPO / "midimat.config.json"), "."),
]
for extra in ("nhl_map.json",):
    if (REPO / extra).exists():
        datas.append((str(REPO / extra), "."))
if (REPO / "models").is_dir():
    datas.append((str(REPO / "models"), "models"))

# sidecar/server.py imports these two by name from ROOT/scripts (the editor's
# /api/controls endpoint needs them), so they must ship in the bundle.
for script in ("build_maps.py", "setup_wizard.py"):
    if (REPO / "scripts" / script).exists():
        datas.append((str(REPO / "scripts" / script), "scripts"))

hiddenimports = [
    # MIDI / HID
    "mido",
    "mido.backends.rtmidi",
    "rtmidi",
    "hid",
    # server / WS
    "websockets",
    "websockets.legacy",
    "websockets.legacy.server",
    # Traktor TSI
    "traktor_tsi",
    "traktor_tsi.tsi",
    "traktor_tsi.tlv",
    "traktor_tsi.strings",
    "traktor_tsi.constants",
    "traktor_tsi.cmad",
    # vision (OpenCV path only)
    "cv2",
    "numpy",
    # our own package (imported after a runtime sys.path insert)
    "sidecar",
    "sidecar.midi_tap",
    "sidecar.mapping",
    "sidecar.tsi_parser",
    "sidecar.nhl_tap",
    "sidecar.suggest",
    "sidecar.refit",
    "sidecar.calibrate",
    "sidecar.vision_snap",
]

excludes = [
    "ultralytics", "torch", "torchvision", "torchaudio",
    "matplotlib", "scipy", "pandas", "sympy", "IPython", "notebook", "jupyter",
    "tkinter", "PyQt5", "PyQt6", "PySide2", "PySide6", "wx",
    "pytest", "setuptools", "pip",
]

a = Analysis(
    [str(REPO / "sidecar" / "server.py")],
    pathex=[str(REPO)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

# The sidecar uses only OpenCV's imgproc/imgcodecs — nowhere does it touch
# VideoCapture/VideoWriter/imshow. Drop the ~29 MB videoio/FFmpeg bridge that
# opencv-python ships.
a.binaries = [b for b in a.binaries if "opencv_videoio_ffmpeg" not in b[0].lower()]

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="midimat-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,          # the .NET shell captures stdout/stderr -> server:log
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="midimat-server",
    # Keep the bundle flat: data (overlay/, layout.json, …) sits next to the exe,
    # not buried in a `_internal` folder — that is where server.py looks when frozen.
    contents_directory=".",
)
