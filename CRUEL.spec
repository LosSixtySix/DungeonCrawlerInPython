# -*- mode: python ; coding: utf-8 -*-
# PyInstaller build for CRUEL. Build with:   python -m PyInstaller CRUEL.spec
# Output is a folder, dist\CRUEL\, holding CRUEL.exe plus an _internal folder it needs.
# Zip the whole dist\CRUEL folder to share it. Saves are not in it: they live in %APPDATA%\CRUEL.

a = Analysis(
    ['lineOfSight.py'],
    pathex=[],
    binaries=[],
    # Read-only files the game loads at runtime (found through paths.resourcePath)
    datas=[('Forgore.otf', '.')],
    hiddenimports=[],
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
    [],
    exclude_binaries=True,  # onedir: libraries go in the folder next to the exe, not inside it
    name='CRUEL',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # no terminal window behind the game
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='CRUEL',
)
