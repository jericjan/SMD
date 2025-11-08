"""Aliases, Enums, NamedTuples, etc go here"""

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Literal, NamedTuple, NewType, Optional

from smd.utils import root_folder


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


GameSpecificChoices = Literal[
    MainMenu.CRACK_GAME,
    MainMenu.REMOVE_DRM,
    MainMenu.DL_USER_GAME_STATS,
]

GAME_SPECIFIC_CHOICES = (
    MainMenu.CRACK_GAME,
    MainMenu.REMOVE_DRM,
    MainMenu.DL_USER_GAME_STATS,
)


class AppListChoice(Enum):
    ADD = "Add IDs"
    DELETE = "View/Delete IDs"


class LuaEndpoint(Enum):
    OUREVERYDAY = "oureveryday (quick but could be limited)"
    MANILUA = "Manilua (more stuff, needs API key)"


class MainReturnCode(Enum):
    LOOP = auto()
    LOOP_NO_PROMPT = auto()
    EXIT = auto()


class SettingItem(NamedTuple):
    key_name: str
    "The key name of the setting (used in the savefile)"
    clean_name: str
    "The name of the setting as displayed in the Settings menu"
    hidden: bool
    "Whether the item is hidden (e.g. sensitive info)"


# Note: values are only obtained through get_setting() in utils.py
class Settings(Enum):
    MANILUA_KEY = SettingItem("manilua_key", "Manilua API Key", True)
    STEAM_USER = SettingItem("steam_user", "Steam Username", False)
    STEAM_PASS = SettingItem("steam_pass", "Steam Password", True)
    STEAM32_ID = SettingItem("steam32_id", "Steam32 ID", False)
    APPLIST_FOLDER = SettingItem("applist_folder", "GreenLuma AppList Folder", False)
    PLAY_MUSIC = SettingItem("play_music", "Play Music", False)

    @property
    def key_name(self) -> str:
        "The key name of the setting (used in the savefile)"
        return self.value.key_name

    @property
    def clean_name(self) -> str:
        "The name of the setting as displayed in the Settings menu"
        return self.value.clean_name

    @property
    def hidden(self) -> bool:
        "Whether the item is hidden (e.g. sensitive info)"
        return self.value.hidden


class LoggedInUser(NamedTuple):
    """A user in loginusers.vdf"""
    steam64_id: str
    persona_name: str
    wants_offline_mode: str
    "Either 0 or 1 (str)"


class LuaResult(NamedTuple):
    path: Optional[Path]
    "The lua file's path if it exists"
    contents: Optional[str]
    "The string contents of the lua file"
    switch_choice: Optional["LuaChoice"]
    "A LuaChoice to switch to"


class GenEmuMode(Enum):
    USER_GAME_STATS = auto()
    STEAM_SETTINGS = auto()
    ALL = auto()  # idk why i have this, it's there if i ever need it


class DepotOrAppID(NamedTuple):
    name: str
    "Name of the app"
    id: int
    "The App/Depot ID"
    parent_id: Optional[int]
    "The parent App ID (if it's a depot)"


@dataclass
class AppIDInfo():
    exists: bool
    """Whether this App ID exists in AppList
    (Sometimes a Depot ID is inside the folder but without an App ID)"""
    name: str
    "Name of the app"
    depots: list[int] = field(default_factory=list[int])
    "(Optional) A list of Depot IDs under this app"


OrganizedAppIDs = dict[int, AppIDInfo]
"A dict of IDs where Depot IDs are organized inside their parent App IDs"


class AppListFile(NamedTuple):
    path: Path
    app_id: int


@dataclass
class DepotKeyPair():
    depot_id: str
    "Depot ID"
    decryption_key: str
    "Decryption Key of the Depot"


@dataclass
class RawLua:
    path: Path
    contents: str


@dataclass
class LuaParsedInfo(RawLua):
    app_id: str
    "The base app ID"
    depots: list[DepotKeyPair]


NamedIDs = NewType("NamedIDs", dict[str, str])
"A dict of App IDs mapped to game names"

ProductInfo = NewType("ProductInfo", dict[str, dict[Any, Any]])
"The dict returned by get_product_info"

DepotManifestMap = NewType("DepotManifestMap",  dict[str, str])
"Depot IDs mapped to Manifest IDs"


class MidiFiles(Enum):
    MIDI_PLAYER_DLL = root_folder() / "c/midi_player_lib.dll"
    SOUNDFONT = root_folder() / "c/Extended_Super_Mario_64_Soundfont.sf2"
    MIDI = root_folder() / "c/th105_broken_moon_redpaper_.mid"


class ManifestGetModes(Enum):
    AUTO = "Auto"
    MANUAL = "Manual"


class DLCTypes(Enum):
    DEPOT = "DEPOT"
    NOT_DEPOT = "NOT A DEPOT"
    UNRELEASED = "UNRELEASED"
