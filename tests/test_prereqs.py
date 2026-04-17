import shutil
import sys
from pathlib import Path


def test_fzf():
    if sys.platform == "win32":
        assert (Path.cwd() / "third_party/fzf/fzf.exe").exists()
    elif sys.platform == "linux":
        assert shutil.which("fzf") is not None


def test_gbe_fork():
    gbe_fork_dir = Path.cwd() / "third_party/gbe_fork"
    assert (gbe_fork_dir / "steam_api.dll").exists() and (
        gbe_fork_dir / "steam_api64.dll"
    ).exists()


def test_gbe_fork_tools():
    exe = (
        Path.cwd()
        / "third_party/gbe_fork_tools/generate_emu_config"
        / ("generate_emu_config" + ".exe" if sys.platform == "win32" else "")
    )
    assert exe.exists()


def test_steamless():
    assert (Path.cwd() / "third_party/steamless/Steamless.CLI.exe").exists()


def test_downloader():
    if sys.platform == "win32":
        assert (Path.cwd() / "third_party/aria2c/aria2c.exe").exists()
    elif sys.platform == "linux":
        assert shutil.which("axel") is not None


def test_midi():
    assert (Path.cwd() / "c/midi_player_lib.dll").exists()
    assert (Path.cwd() / "c/Extended_Super_Mario_64_Soundfont.sf2").exists()
    assert (Path.cwd() / "c/th105_broken_moon_redpaper_.mid").exists()
