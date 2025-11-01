import re
import shutil
from pathlib import Path

from steam.client import SteamClient  # type: ignore

from smd.lua.downloader import download_lua
from smd.lua.selection import add_new_lua, select_from_saved_luas
from smd.storage.named_ids import get_named_ids
from smd.structs import LuaChoice, LuaParsedInfo  # type: ignore


class LuaManager:
    def __init__(
        self,
        client: SteamClient,
        steam_path: Path,
    ):
        self.client = client
        self.saved_lua = Path().cwd() / "saved_lua"
        self.named_ids = get_named_ids(self.saved_lua)
        self.steam_path = steam_path

    def get_lua_info(self, choice: LuaChoice) -> LuaParsedInfo:
        app_id_regex = re.compile(r"addappid\s*\(\s*(\d+)\s*\)")
        depot_dec_key_regex = re.compile(
            r"addappid\s*\(\s*(\d+)\s*,\s*\d\s*,\s*(?:\"|\')(\S+)(?:\"|\')\s*\)"
        )
        while True:
            while True:
                if choice == LuaChoice.SELECT_SAVED_LUA:
                    result = select_from_saved_luas(self.saved_lua, self.named_ids)
                elif choice == LuaChoice.ADD_LUA:
                    result = add_new_lua()
                elif choice == LuaChoice.AUTO_DOWNLOAD:
                    result = download_lua(self.saved_lua)

                if result.path is not None:
                    lua_path = result.path
                    if result.contents is not None:
                        lua_contents = result.contents
                    else:
                        lua_contents = result.path.read_text(encoding="utf-8")
                    break

                if result.switch_choice is not None:
                    choice = result.switch_choice

            if not (app_id_match := app_id_regex.search(lua_contents)):
                print("App ID not found. Try again.")
                continue

            app_id = app_id_match.group(1)
            print(f"App ID is {app_id}")

            if not (depot_dec_key := depot_dec_key_regex.findall(lua_contents)):
                print("Decryption keys not found. Try again.")
                continue
            break
        return LuaParsedInfo(app_id, depot_dec_key, lua_path, lua_contents)

    def backup_lua(self, lua: LuaParsedInfo):
        """Saves the lua file for later use"""
        if lua.path.suffix == ".zip":
            with (self.saved_lua / f"{lua.id}.lua").open("w", encoding="utf-8") as f:
                f.write(lua.contents)
        elif not (self.saved_lua / lua.path.name).exists():
            shutil.copyfile(lua.path, self.saved_lua / lua.path.name)


