import os
import shutil
import sys

from smd.utils import root_folder


def test_fzf():
    if sys.platform == "win32":
        file = (root_folder() / "third_party/fzf/fzf.exe")
        assert (
            file.exists()
        ), f"\"{str(file.relative_to(root_folder(True)))}\" does not exist. "
        "Please install it to that location"
    elif sys.platform == "linux":
        assert shutil.which("fzf") is not None, "fzf is missing. Please install it"


# Bundled in repo
def test_gbe_fork():
    gbe_fork_dir = root_folder() / "third_party/gbe_fork"
    files = [
        (gbe_fork_dir / "steam_api.dll"),
        (gbe_fork_dir / "steam_api64.dll")
    ]
    for file in files:
        assert (
            file.exists()
        ), f"\"{str(file.relative_to(root_folder(True)))}\" does not exist. "
        "Please install it to that location"


def test_gbe_fork_tools():
    exe = (
        root_folder()
        / "third_party/gbe_fork_tools/generate_emu_config"
        / ("generate_emu_config" + ".exe" if sys.platform == "win32" else "")
    )
    assert exe.exists(), f'"{str(exe.relative_to(root_folder(True)))}" does not exist. '
    "Please install it to that location"
    assert os.access(
        exe.absolute(), os.X_OK
    ), f'"{str(exe.relative_to(root_folder(True)))}" is not executable.'


# Bundled in repo
def test_steamless():
    file = (root_folder() / "third_party/steamless/Steamless.CLI.exe")
    assert (
        file.exists()
    ), f'"{str(file.relative_to(root_folder(True)))}" does not exist. '
    "Please install it to that location"
    assert os.access(
        file.absolute(), os.X_OK
    ), f'"{str(file.relative_to(root_folder(True)))}" is not executable.'


def test_downloader():
    if sys.platform == "win32":
        file = (root_folder() / "third_party/aria2c/aria2c.exe")
        assert (
            file.exists()
        ), f'"{str(file.relative_to(root_folder(True)))}" does not exist. '
        'Please install it to that location'
    elif sys.platform == "linux":
        assert shutil.which("axel") is not None, "axel is missing. Please install it"


def test_midi():
    files = [(root_folder() / "c/midi_player_lib.dll"),
             (root_folder() / "c/Extended_Super_Mario_64_Soundfont.sf2"),
             (root_folder() / "c/th105_broken_moon_redpaper_.mid")]
    for file in files:
        assert (
            file.exists()
        ), f'"{str(file.relative_to(root_folder(True)))}" does not exist'
