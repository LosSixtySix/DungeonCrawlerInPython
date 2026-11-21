# -*- mode: python ; coding: utf-8 -*-
import glob
import os

# PyInstaller build for CRUEL. Build with:   python -m PyInstaller CRUEL.spec
# Output is a folder, dist\CRUEL\, holding CRUEL.exe plus an _internal folder it needs.
# To share it, run distribution\release.ps1: it builds, zips and publishes to players over Tailscale. Saves are not in it: they live in %APPDATA%\CRUEL.

# Every .json and .wav anywhere in music/ (the tracks and sound effects, in their folders), kept at the same path inside the build
MUSIC = []
for path in glob.glob(os.path.join(SPECPATH, 'music', '**', '*.json'), recursive=True) + glob.glob(os.path.join(SPECPATH, 'music', '**', '*.wav'), recursive=True):
    relative = os.path.relpath(path, SPECPATH)
    MUSIC.append((relative, os.path.dirname(relative)))

a = Analysis(
    ['lineOfSight.py'],
    pathex=[],
    binaries=[],
    # Read-only files the game loads at runtime (found through paths.resourcePath), music included
    datas=[('Forgore.otf', '.'), ('icon.png', '.')] + MUSIC,
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
    icon='CRUEL.ico',  # made by makeIcon.py
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
