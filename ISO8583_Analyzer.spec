# -*- mode: python ; coding: utf-8 -*-
"""Spec de PyInstaller para generar el ejecutable de ISO8583 Analyzer.

Uso:
    pyinstaller ISO8583_Analyzer.spec
"""

from pathlib import Path

block_cipher = None
project_root = Path(SPECPATH)

a = Analysis(
    ["app.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / "assets"), "assets"),
        (str(project_root / "history"), "history"),
        (str(project_root / "core" / "profiles" / "specs"), "core/profiles/specs"),
        (str(project_root / "plugins"), "plugins"),
    ],
    hiddenimports=["qdarktheme"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ISO8583 Analyzer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    icon=str(project_root / "assets" / "app_icon.png"),
)
