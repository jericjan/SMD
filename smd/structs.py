"""Aliases, Enums, NamedTuples, etc go here"""

import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Literal, NamedTuple, NewType, Optional, Union


class LuaChoice(Enum):
    ADD_LUA = "Add a .lua file"
    SELECT_SAVED_LUA = "Choose from saved .lua files"
    AUTO_DOWNLOAD = "Automatically download a .lua file"


class LuaChoiceReturnCode(Enum):
    GO_BACK = auto()
    "Exit and go back to the LuaChoice selection screen"
    LOOP = auto()
    "Doesn't actually get read, but basically retry if chosen lua method fails"


class MainMenu(Enum):
    MANAGE_LUA = "Process a .lua file"
    UPDATE_ALL_MANIFESTS = "Update manifests for all outdated games"
    DL_MANIFEST_ONLY = "Download manifests ONLY from a .lua file"
    DL_WORKSHOP_ITEM = "Download workshop item manifest"
    DLC_CHECK = "Check DLC status of a game"
    CRACK_GAME = "Crack a game (gbe_fork)"
    REMOVE_DRM = "Remove SteamStub DRM (Steamless)"
    DL_USER_GAME_STATS = "Download UserGameStatsSchema (achievements w/o gbe_fork)"
    OFFLINE_FIX = "Offline Mode Fix"
    if sys.platform == "win32":
        MANAGE_APPLIST = "Manage AppList IDs"
    elif sys.platform == "linux":
        MANAGE_APPLIST = "Manage SLSSteam IDs"
    else:
        MANAGE_APPLIST = "Manage injected IDs"
    CHECK_UPDATES = "Check for updates"
    INSTALL_MENU = "Install/Uninstall Context Menu"
    SETTINGS = "Settings"
    EXIT = "Exit"


GameSpecificChoices = Literal[
    MainMenu.CRACK_GAME,
    MainMenu.REMOVE_DRM,
    MainMenu.DL_USER_GAME_STATS,
    MainMenu.DLC_CHECK,
    MainMenu.DL_WORKSHOP_ITEM,
]

GAME_SPECIFIC_CHOICES = (
    MainMenu.CRACK_GAME,
    MainMenu.REMOVE_DRM,
    MainMenu.DL_USER_GAME_STATS,
    MainMenu.DLC_CHECK,
    MainMenu.DL_WORKSHOP_ITEM,
)


class AppListChoice(Enum):
    ADD = "Add IDs"
    DELETE = "View/Delete IDs"


class LuaEndpoint(Enum):
    OUREVERYDAY = "oureveryday (quick but could be limited)"
    MORRENUS = "Morrenus (more stuff, needs API key, has a daily limit)"


class MainReturnCode(Enum):
    LOOP = auto()
    LOOP_NO_PROMPT = auto()
    EXIT = auto()





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
    switch_choice: Union["LuaChoice", "LuaChoiceReturnCode"]
    "A LuaChoice to switch to."


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
class AppIDInfo:
    exists: bool
    """Whether this App ID exists in AppList
    (Sometimes a Depot ID is inside the folder but without an App ID)"""
    name: str
    "Name of the app"
    depots: list[int] = field(default_factory=list[int])
    "(Optional) A list of Depot IDs under this app"


OrganizedAppIDs = dict[int, AppIDInfo]
"A dict of IDs where Depot IDs are organized inside their parent App IDs"


class AppListPathAndID(NamedTuple):
    path: Path
    app_id: int


@dataclass
class DepotKeyPair:
    """A depot and its decryption key"""

    depot_id: str
    "Depot ID"
    decryption_key: str
    "Decryption Key of the Depot. Can be blank if it's not a depot"


@dataclass
class RawLua:
    path: Path
    "can be either a lua file or ZIP file"
    contents: str
    "content of the lua file"


@dataclass
class LuaParsedInfo(RawLua):
    app_id: str
    "The base app ID"
    depots: list[DepotKeyPair]


NamedIDs = NewType("NamedIDs", dict[str, str])
"A dict of App IDs mapped to game names"

ProductInfo = NewType("ProductInfo", dict[str, dict[Any, Any]])
"The dict returned by get_product_info"

DepotManifestMap = NewType("DepotManifestMap", dict[str, str])
"Depot IDs mapped to Manifest IDs"


class ManifestGetModes(Enum):
    AUTO = "Auto"
    MANUAL = "Manual"


class DLCTypes(Enum):
    DEPOT = "DOWNLOAD REQUIRED"
    NOT_DEPOT = "PRE-INSTALLED"
    UNRELEASED = "UNRELEASED"


class ContextMenuOptions(Enum):
    INSTALL = "Install"
    UNINSTALL = "Uninstall"


class ReleaseType(Enum):
    PRERELEASE = "Pre-release (Buggy)"
    STABLE = "Stable"


class OSType(Enum):
    WINDOWS = auto()
    LINUX = auto()
    OTHER = auto()
