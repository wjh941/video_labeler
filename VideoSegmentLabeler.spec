from pathlib import Path


PROJECT_ROOT = Path(SPECPATH)

# FFmpeg and FFprobe intentionally remain external system dependencies.
APP_DATAS = [
    (str(PROJECT_ROOT / "video_labeler" / "themes" / "light_fresh.qss"), "video_labeler/themes"),
    (str(PROJECT_ROOT / "start.bat"), "."),
]

a = Analysis(
    [str(PROJECT_ROOT / "app.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=APP_DATAS,
    hiddenimports=["PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VideoSegmentLabeler",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="VideoSegmentLabeler",
)
