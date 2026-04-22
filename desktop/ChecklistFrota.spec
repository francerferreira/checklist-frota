# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


desktop_root = Path(SPECPATH).resolve()
backend_root = desktop_root.parent / "backend"

hiddenimports = collect_submodules("PySide6") + collect_submodules("app")
datas = [
    (str(desktop_root / "assets" / "app-icon.ico"), "assets"),
    (str(desktop_root / "assets" / "app-icon.png"), "assets"),
    (str(desktop_root / "assets" / "app-logo-cover.png"), "assets"),
    (str(desktop_root / "assets" / "cf-logo-cover.png"), "assets"),
]


a = Analysis(
    [str(desktop_root / "main.py")],
    pathex=[str(desktop_root), str(backend_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ChecklistFrotaDesktop",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(desktop_root / "assets" / "app-icon.ico"),
)
