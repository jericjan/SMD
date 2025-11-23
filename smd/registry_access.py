import winreg
from pathlib import Path

from colorama import Fore, Style

from smd.prompts import prompt_dir, prompt_select
from smd.structs import GreenLumaVersions


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


def get_steam_path():
    steam_path = find_steam_path_from_registry()
    if steam_path is None or not steam_path.exists():
        steam_path = prompt_dir(
            "Couldn't find your Steam path. Paste the "
            "path here (The folder that has steam.exe)"
        )
    else:
        colorized = Fore.YELLOW + str(steam_path.resolve()) + Style.RESET_ALL
        print(f"Your Steam path is {colorized}")
    return steam_path


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


def set_stats_and_achievements(app_id: int, enabled: bool):
    """Sets the SkipStatsAndAchievements key for a game."""
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
    set_stats_and_achievements(123, True)
