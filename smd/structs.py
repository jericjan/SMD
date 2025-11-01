"""Aliases, Enums, NamedTuples, etc go here"""

from enum import Enum
from pathlib import Path
from typing import NamedTuple, Optional, TypedDict


class LuaChoice(Enum):
    ADD_LUA = "Add a .lua file"
    SELECT_SAVED_LUA = "Choose from saved .lua files"
    AUTO_DOWNLOAD = "Automatically download a .lua file"


class MainMenu(Enum):
    MANAGE_LUA = "Manage .lua files"
    CRACK_GAME = "Crack a game (gbe_fork)"
    REMOVE_DRM = "Remove SteamStub DRM (Steamless)"
    DL_USER_GAME_STATS = "Download UserGameStatsSchema (achievements w/o gbe_fork)"
    OFFLINE_FIX = "Offline Mode Fix"
    MANAGE_APPLIST = "Manage AppList IDs"
    SETTINGS = "Settings"
    EXIT = "Exit"


class AppListChoice(Enum):
    ADD = "Add an ID"
    DELETE = "Delete an ID"


class LuaEndpoint(Enum):
    OUREVERYDAY = "oureveryday (quick but could be limited)"
    MANILUA = "Manilua (more stuff, needs API key)"


class MainReturnCode(Enum):
    LOOP = 0
    LOOP_NO_PROMPT = 1
    EXIT = 2


class SettingItem(NamedTuple):
    key_name: str
    clean_name: str
    hidden: bool  # Whether the item is hidden when inputting the data


# Note: values are only obtained through get_setting() in utils.py
class Settings(Enum):
    MANILUA_KEY = SettingItem("manilua_key", "Manilua API Key", True)
    STEAM_USER = SettingItem("steam_user", "Steam Username", False)
    STEAM_PASS = SettingItem("steam_pass", "Steam Password", True)
    STEAM32_ID = SettingItem("steam32_id", "Steam32 ID", False)
    APPLIST_FOLDER = SettingItem("applist_folder", "GreenLuma AppList Folder", False)

    @property
    def key_name(self) -> str:
        return self.value.key_name

    @property
    def clean_name(self) -> str:
        return self.value.clean_name

    @property
    def hidden(self) -> bool:
        return self.value.hidden


class LoggedInUser(NamedTuple):
    """A user in loginusers.vdf"""

    STEAM64_ID: str
    PERSONA_NAME: str
    WANTS_OFFLINE_MODE: str


class LuaResult(NamedTuple):
    path: Optional[Path]  # path on disk if file exists
    contents: Optional[str]  # string contents of file (e.g., from zip read)
    switch_choice: Optional["LuaChoice"]


class GenEmuMode(Enum):
    USER_GAME_STATS = 0
    STEAM_SETTINGS = 1
    ALL = 2  # idk why i have this, it's there if i ever need it


class DepotOrAppID(NamedTuple):
    name: str
    id: str  # app id
    parent_id: Optional[str]  # The parent app ID if it's a depot


class AppIDInfoRequired(TypedDict):
    exists: bool
    name: str


class AppIDInfo(AppIDInfoRequired, total=False):
    children: list[str]


OrganizedAppIDs = dict[int, AppIDInfo]


class AppListFile(NamedTuple):
    path: Path
    app_id: int
