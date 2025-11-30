import logging
import re
import shutil
from pathlib import Path
from typing import Optional

from colorama import Fore, Style

from smd.lua.choices import add_new_lua, download_lua, select_from_saved_luas
from smd.storage.named_ids import get_named_ids
from smd.structs import DepotKeyPair, LuaChoice, LuaParsedInfo, RawLua  # type: ignore

logger = logging.getLogger(__name__)


class LuaManager:
    def __init__(
        self,
    ):
        self.saved_lua = Path().cwd() / "saved_lua"
        self.named_ids = get_named_ids(self.saved_lua)

    def get_raw_lua(self, choice: LuaChoice, override: Optional[Path] = None) -> RawLua:
        """Return the lua path and contents"""
        while True:
            if choice == LuaChoice.SELECT_SAVED_LUA:
                result = select_from_saved_luas(self.saved_lua, self.named_ids)
            elif choice == LuaChoice.ADD_LUA:
                result = add_new_lua(override)
            elif choice == LuaChoice.AUTO_DOWNLOAD:
                result = download_lua(self.saved_lua)

            if result.path is not None:
                lua_path = result.path
                if result.contents is not None:  # Usually a zip
                    lua_contents = result.contents
                else:
                    try:
                        lua_contents = result.path.read_text(encoding="utf-8")
                    except UnicodeDecodeError:
                        print(
                            Fore.RED + "This file is not a text file!" + Style.RESET_ALL
                        )
                        override = None
                        continue
                break

            if result.switch_choice is not None:
                choice = result.switch_choice
        return RawLua(lua_path, lua_contents)

    def fetch_lua(
        self, choice: LuaChoice, override: Optional[Path] = None
    ) -> LuaParsedInfo:
        """Depending on the choice, fetch a lua file then parse the contents"""
        depot_no_key_regex = re.compile(
            r"^\s*addappid\s*\(\s*(\d+)\s*\)", flags=re.MULTILINE
        )
        # addappid with just 1 arg
        depot_dec_key_regex = re.compile(
            r"^\s*addappid\s*\(\s*(\d+)\s*,\s*\d\s*,\s*(?:\"|\')(\S+)(?:\"|\')\s*\)",
            flags=re.MULTILINE,
        )
        # addappid with decryption key
        general_regex = re.compile(r"^\s*addappid\s*\(\s*(\d+)", flags=re.MULTILINE)
        # any addappid command

        while True:
            ids_with_no_key: list[str] = []
            lua = self.get_raw_lua(choice, override)
            if not (any_addappid := general_regex.search(lua.contents)):
                print("App ID not found. Try again.")
                continue

            app_id = any_addappid.group(1)
            print(f"App ID is {app_id}")

            ids_with_no_key = depot_no_key_regex.findall(lua.contents)

            if not (depot_dec_key := depot_dec_key_regex.findall(lua.contents)):
                print("Decryption keys not found. Try again.")
                continue
            break
        depot_dec_key = [DepotKeyPair(*x) for x in depot_dec_key]
        depot_dec_key.extend([DepotKeyPair(x, "") for x in ids_with_no_key])
        return LuaParsedInfo(lua.path, lua.contents, app_id, depot_dec_key)

    def backup_lua(self, lua: LuaParsedInfo):
        """Saves the lua file for later use"""
        target = self.saved_lua / f"{lua.app_id}.lua"
        if lua.path.suffix == ".zip":
            with target.open("w", encoding="utf-8") as f:
                f.write(lua.contents)
        else:
            try:
                shutil.copyfile(lua.path, target)
            except shutil.SameFileError:
                logger.debug("Skipped backup because it's the same file")
                pass
