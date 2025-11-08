import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from smd.utils import run_fzf
from smd.http_utils import download_to_tempfile
from smd.lua.endpoints import get_manilua, get_oureverday
from smd.prompts import prompt_confirm, prompt_file, prompt_select, prompt_text
from smd.structs import LuaChoice, LuaEndpoint, LuaResult, NamedIDs
from smd.utils import enter_path, root_folder
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


def search_game() -> Optional[str]:
    """Using fzf, lets a user search for a game, then returns game ID"""
    all_games_file = (root_folder() / "all_games.txt")
    if all_games_file.exists():
        mtime = all_games_file.stat().st_mtime
        mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %I:%M %p")
        download = prompt_confirm(f"Do you want to update the list of every Game ID? (Last Modified: {mtime_str})", default=False)
    else:
        download = True
    if download:
        while True:
            with download_to_tempfile(
                "https://api.steampowered.com/ISteamApps/GetAppList/v1/"
            ) as tf:
                if tf is None:
                    continue
                resp = json.load(tf)
            break
        games = enter_path(resp, "applist", "apps", "app")
        games = [x.get("name") + f" [ID={x.get('appid')}]" for x in games]
        with all_games_file.open("w", encoding="utf=-8") as f:
            f.write('\n'.join(games))
    else:
        games = all_games_file
    selection = run_fzf(games)
    if selection:
        match = re.search(r"(?<=\[ID=)\d+(?=\]$)", selection)
        assert match is not None
        return match.group()


def download_lua(dest: Path) -> LuaResult:
    """Downloads a lua file from the available endpoints"""

    reg = re.compile(r"(?<=store\.steampowered\.com\/app\/)\d+|\d+")

    def validate_app_id(x: str) -> bool:
        return bool(reg.search(x)) or x == ''

    def filter_app_id(x: str) -> str:
        if x == "":
            return x
        match = reg.search(x)
        assert match is not None  # lmao
        return match.group()

    source: LuaEndpoint = prompt_select("Select an endpoint:", list(LuaEndpoint))

    app_id: str = prompt_text(
        "Enter the App ID or Store link. Leave it blank to search for games:",
        validator=validate_app_id,
        invalid_msg="Not a valid format.",
        filter=filter_app_id,
    )

    if not app_id:
        if x := search_game():
            app_id = x
        else:
            return LuaResult(None, None, None)

    if source == LuaEndpoint.OUREVERYDAY:
        lua_path = get_oureverday(dest, app_id)
    elif source == LuaEndpoint.MANILUA:
        lua_path = get_manilua(dest, app_id)

    if lua_path is None:
        if prompt_confirm(
            "Could not find it. Try again?", false_msg="No (Add a .lua instead)"
        ):
            return LuaResult(None, None, None)
        print("Switching to manual .lua selection...")
        return LuaResult(None, None, LuaChoice.ADD_LUA)

    return LuaResult(lua_path, None, None)
