

import zipfile
from pathlib import Path
from typing import Optional

from smd.prompts import prompt_file, prompt_select
from smd.storage.vdf import VDFLoadAndDumper, vdf_load
from smd.structs import LuaChoice, LuaResult
from smd.utils import enter_path


def get_steam_libs(steam_path: Path):
    """Get list of Steam library paths by the user

    Args:
        steam_path (Path): Steam install path

    Returns:
        list[Path]: list of Steam library paths
    """
    lib_folders = steam_path / "config/libraryfolders.vdf"

    vdf_data = vdf_load(lib_folders)
    paths: list[Path] = []
    for library in vdf_data["libraryfolders"].values():
        if (path := Path(library["path"])).exists():
            paths.append(path)

    return paths


def find_lua_in_zip(path: Path):
    """Given a zip path, return the string contents,
    blank if it can't be found"""
    lua_contents = ""
    with zipfile.ZipFile(path) as zf:
        for file in zf.filelist:
            if file.filename.endswith(".lua"):
                print(f".lua found: {file.filename}")
                lua_contents = zf.read(file).decode(encoding="utf-8")
                break  # lua found in ZIP, stop searching
    return lua_contents


def select_from_saved_luas(saved_lua: Path, named_ids: dict[str, str]) -> LuaResult:
    """Prompt the user to select a saved lua file

    Args:
        saved_lua (Path): Path to the folder with saved lua files
        named_ids (dict[str, str]): A dict of (game_id, game_name)

    Returns:
        LuaResult:
    """
    if len(named_ids) == 0:
        print("You don't have any saved .lua files. Try adding some first.")
        return LuaResult(None, None, LuaChoice.ADD_LUA)
    lua_path: Optional[Path] = prompt_select(
        "Choose a game:",
        [(name, saved_lua / f"{app_id}.lua") for app_id, name in named_ids.items()]
        + [("(Add a lua file instead)", None)],
        fuzzy=True,
    )
    if lua_path is None or not lua_path.exists():
        return LuaResult(None, None, LuaChoice.ADD_LUA)
    return LuaResult(lua_path, None, None)


def add_new_lua() -> LuaResult:
    """Prompts user to add a new .lua or ZIP file

    Returns:
        LuaResult:
    """
    lua_path = prompt_file(
        "Drag a .lua file (or .zip w/ .lua inside) into here "
        "then press Enter.\n"
        "Leave it blank to switch to selecting a saved .lua:",
        allow_blank=True,
    )

    if lua_path.samefile(Path.cwd()):  # Blank input
        # Switch to other option
        return LuaResult(None, None, LuaChoice.SELECT_SAVED_LUA)

    if lua_path.suffix == ".zip":
        lua_contents = find_lua_in_zip(lua_path)
        if lua_contents == "":
            print("Could not find .lua in ZIP file.")
            return LuaResult(None, None, None)
        return LuaResult(lua_path, lua_contents, None)
    return LuaResult(lua_path, None, None)


def add_decryption_key_to_config(vdf_file: Path, depot_dec_key: list[tuple[str, str]]):
    """Adds decryption keys to config.vdf"""
    with VDFLoadAndDumper(vdf_file) as vdf_data:
        for depot_id, dec_key in depot_dec_key:
            print(f"Depot {depot_id} has decryption key {dec_key}...", end="")
            depots = enter_path(
                vdf_data,
                "InstallConfigStore",
                "Software",
                "Valve",
                "Steam",
                "depots",
                mutate=True,
            )
            if depot_id not in depots:
                depots[depot_id] = {"DecryptionKey": dec_key}
                print("Added to config.vdf succesfully.")
            else:
                print("Already in config.vdf.")
