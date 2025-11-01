
import winreg
from pathlib import Path

from smd.prompts import prompt_dir


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
        print(f"Your steam path is {steam_path}")
    return steam_path
