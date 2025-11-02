

import re
from pathlib import Path
from typing import Optional

from smd.lua.endpoints import get_manilua, get_oureverday
from smd.prompts import prompt_file, prompt_select, prompt_text
from smd.structs import LuaChoice, LuaEndpoint, LuaResult, NamedIDs
from smd.zip import read_lua_from_zip


def select_from_saved_luas(saved_lua: Path, named_ids: NamedIDs) -> LuaResult:
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
        lua_contents = read_lua_from_zip(lua_path)
        if lua_contents is None:
            print("Could not find .lua in ZIP file.")
            return LuaResult(None, None, None)
        return LuaResult(lua_path, lua_contents, None)
    return LuaResult(lua_path, None, None)


def download_lua(dest: Path) -> LuaResult:
    """Downloads a lua file from the available endpoints"""

    reg = re.compile(r"(?<=store\.steampowered\.com\/app\/)\d+|\d+")

    def validate_app_id(x: str) -> bool:
        return bool(reg.search(x))

    def filter_app_id(x: str) -> str:
        match = reg.search(x)
        assert match is not None  # lmao
        return match.group()

    source: LuaEndpoint = prompt_select("Select an endpoint:", list(LuaEndpoint))

    app_id = prompt_text(
        "Enter the App ID or Store link:",
        validator=validate_app_id,
        invalid_msg="Not a valid format.",
        filter=filter_app_id,
    )

    if source == LuaEndpoint.OUREVERYDAY:
        lua_path = get_oureverday(dest, app_id)
    elif source == LuaEndpoint.MANILUA:
        lua_path = get_manilua(dest, app_id)

    if lua_path is None:
        restart = prompt_select(
            "Could not find it. Try again?",
            [("Yes", True), ("No (Add a .lua instead)", False)],
        )
        if restart:
            return LuaResult(None, None, None)
        print("Switching to manual .lua selection...")
        return LuaResult(None, None, LuaChoice.ADD_LUA)

    return LuaResult(lua_path, None, None)
