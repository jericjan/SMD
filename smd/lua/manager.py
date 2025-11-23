import re
import shutil
from pathlib import Path

from smd.lua.choices import add_new_lua, download_lua, select_from_saved_luas
from smd.storage.named_ids import get_named_ids
from smd.structs import DepotKeyPair, LuaChoice, LuaParsedInfo, RawLua  # type: ignore


class LuaManager:
    def __init__(
        self,
    ):
        self.saved_lua = Path().cwd() / "saved_lua"
        self.named_ids = get_named_ids(self.saved_lua)

    def get_raw_lua(self, choice: LuaChoice) -> RawLua:
        """Return the lua path and contents"""
        while True:
            if choice == LuaChoice.SELECT_SAVED_LUA:
                result = select_from_saved_luas(self.saved_lua, self.named_ids)
            elif choice == LuaChoice.ADD_LUA:
                result = add_new_lua()
            elif choice == LuaChoice.AUTO_DOWNLOAD:
                result = download_lua(self.saved_lua)

            if result.path is not None:
                lua_path = result.path
                if result.contents is not None:  # Usually a zip
                    lua_contents = result.contents
                else:
                    lua_contents = result.path.read_text(encoding="utf-8")
                break

            if result.switch_choice is not None:
                choice = result.switch_choice
        return RawLua(lua_path, lua_contents)

    def fetch_lua(self, choice: LuaChoice) -> LuaParsedInfo:
        """Depending on the choice, fetch a lua file then parse the contents"""
        app_id_regex = re.compile(r"^\s*addappid\s*\(\s*(\d+)\s*\)")
        depot_dec_key_regex = re.compile(
            r"^\s*addappid\s*\(\s*(\d+)\s*,\s*\d\s*,\s*(?:\"|\')(\S+)(?:\"|\')\s*\)"
        )
        extra_no_key_ids: list[str] = []
        while True:
            lua = self.get_raw_lua(choice)
            if not (app_id_match := app_id_regex.findall(lua.contents)):
                print("App ID not found. Try again.")
                continue

            app_id = app_id_match[0]
            print(f"App ID is {app_id}")

            if len(app_id_match) > 1:
                extra_no_key_ids = app_id_match[1:]

            if not (depot_dec_key := depot_dec_key_regex.findall(lua.contents)):
                print("Decryption keys not found. Try again.")
                continue
            break
        depot_dec_key = [DepotKeyPair(*x) for x in depot_dec_key]
        depot_dec_key.extend([DepotKeyPair(x, "") for x in extra_no_key_ids])
        return LuaParsedInfo(lua.path, lua.contents, app_id, depot_dec_key)

    def backup_lua(self, lua: LuaParsedInfo):
        """Saves the lua file for later use"""
        target = self.saved_lua / f"{lua.app_id}.lua"
        if lua.path.suffix == ".zip":
            with target.open("w", encoding="utf-8") as f:
                f.write(lua.contents)
        try:
            shutil.copyfile(lua.path, target)
        except shutil.SameFileError:
            logger.debug("Skipped backup because it's the same file")
            pass
