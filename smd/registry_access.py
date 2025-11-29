from typing import Optional
import winreg
from pathlib import Path


from smd.prompts import prompt_confirm, prompt_select
from smd.storage.settings import get_setting, set_setting
from smd.structs import GreenLumaVersions, Settings


def find_steam_path_from_registry():
    """Get the user's Steam location.
    Checks CurrentUser first, then LocalMachine"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Valve\Steam") as key:
            return Path(winreg.QueryValueEx(key, "SteamPath")[0])
    except FileNotFoundError:
        pass

    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"
        ) as key:
            return Path(winreg.QueryValueEx(key, "InstallPath")[0])
    except FileNotFoundError:
        return None


def key_exists(hive: int, key_path: str):
    try:
        key = winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False
    except OSError as e:
        print(f"An OS error occurred: {e}")
        return False


def get_greenluma_key():
    greenluma_keynames = [x.value for x in GreenLumaVersions]
    existing_keys = [
        x
        for x in greenluma_keynames
        if key_exists(winreg.HKEY_CURRENT_USER, rf"SOFTWARE\{x}")
    ]
    if len(existing_keys) == 0:
        selected_version = prompt_select(
            "Which GreenLuma version do you have:", greenluma_keynames
        )
    elif len(existing_keys) == 1:
        selected_version = existing_keys[0]
    else:  # More than 1
        print("More than one Greenluma key found.")
        selected_version = prompt_select(
            "Which version are you using rn?", existing_keys
        )
    return selected_version


def read_subkey(hive: int, key_path: str, sub_key_name: str):
    try:
        with winreg.OpenKey(hive, key_path) as key:
            return winreg.QueryValueEx(key, sub_key_name)[0]
    except FileNotFoundError:
        return


def set_stats_and_achievements(app_id: int):
    """Sets the SkipStatsAndAchievements key (GreenLuma) for a game."""
    if (selected_version := get_setting(Settings.GL_VERSION)) is None:
        selected_version = get_greenluma_key()
        set_setting(Settings.GL_VERSION, selected_version)

    curr: Optional[int] = read_subkey(
        winreg.HKEY_CURRENT_USER,
        rf"SOFTWARE\{selected_version}\AppID\{app_id}",
        "SkipStatsAndAchievements",
    )
    enabled = prompt_confirm(
        "Would you like Greenluma (normal mode) to track achievements?"
        + (
            (" (Currently Disabled)" if curr else " (Currently Enabled)")
            if curr is not None
            else ""
        )
    )
    try:
        with winreg.CreateKey(
            winreg.HKEY_CURRENT_USER, rf"SOFTWARE\{selected_version}\AppID\{app_id}"
        ) as key:
            winreg.SetValueEx(
                key,
                "SkipStatsAndAchievements",
                0,
                winreg.REG_DWORD,
                0 if enabled else 1,
            )
        return True
    except OSError as e:
        print(f"Error setting registry key: {e}")
        return False


if __name__ == "__main__":
    set_stats_and_achievements(123)
