# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

upx_excludes = [
    str(x.relative_to(".")) for x in Path("third_party").rglob("*") if x.is_file()
]

def file_is_inside_dir(file: Path, dir: Path):
    try:
        file.relative_to(dir)
        return True
    except ValueError:
        return False

tree = Tree("third_party")

third_party_files = []

# excludes in Tree doesn't work some reason
for _, file, _ in tree:
    if not any(
        file_is_inside_dir(Path(file), Path(x))
        for x in (
            "third_party/gbe_fork_tools/generate_emu_config/output/",
            "third_party/gbe_fork_tools/generate_emu_config/backup/",
        )
    ):
        third_party_files.append((file, Path(file).parent if Path(file).is_file() else file))

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        *third_party_files,
        ("LICENSE", "."),
        ("third_party_licenses", "third_party_licenses"),
        ("static", "static"),
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
