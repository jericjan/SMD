# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

upx_excludes = [
    str(x.relative_to(".")) for x in Path("third_party").rglob("*") if x.is_file()
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("third_party", "third_party"),
        ("LICENSE", "."),
        ("third_party_licenses", "third_party_licenses"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
    upx_exclude=upx_excludes,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SMD',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=upx_excludes,
    name='main',
)
