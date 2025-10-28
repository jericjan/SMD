from enum import Enum
from pathlib import Path
from typing import NamedTuple, Optional


class LuaChoice(Enum):
    ADD_LUA = "Add a .lua file"
    SELECT_SAVED_LUA = "Choose from saved .lua files"
    AUTO_DOWNLOAD = "Automatically download a .lua file"


class MainMenu(Enum):
    MANAGE_LUA = "Manage .lua files"
    CRACK_GAME = "Crack a game (gbe_fork)"
    REMOVE_DRM = "Remove SteamStub DRM (Steamless)"
    SETTINGS = "Settings"
    EXIT = "Exit"


class LuaEndpoint(Enum):
    OUREVERYDAY = "oureveryday (quick but could be limited)"
    MANILUA = "Manilua (more stuff, needs API key)"


class MainReturnCode(Enum):
    LOOP = 0
    EXIT = 1


class SettingItem(NamedTuple):
    name: str
    hidden: bool  # Whether the item is hidden when inputting the data


class Settings(Enum):
    MANILUA_KEY = SettingItem("manilua_key", True)
    STEAM_USER = SettingItem("steam_user", False)
    STEAM_PASS = SettingItem("steam_pass", True)
    STEAM32_ID = SettingItem("steam32_id", False)

    @property
    def key_name(self) -> str:
        return self.value.name

    @property
    def hidden(self) -> bool:
        return self.value.hidden


class LuaResult(NamedTuple):
    path: Optional[Path]  # path on disk if file exists
    contents: Optional[str]  # string contents of file (e.g., from zip read)
    switch_choice: Optional["LuaChoice"]
