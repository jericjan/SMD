import sys
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from smd.game_specific import GameHandler
from smd.structs import MainReturnCode
from smd.ui.core import UI


@dataclass(frozen=True)
class StandardMenuItem:
    title: str
    action: Callable[[Any], MainReturnCode]
    """Unbound method expecting `self`"""

    @property
    def is_game_specific(self) -> bool:
        return False

    @property
    def can_select_external(self) -> bool:
        return False


@dataclass(frozen=True)
class GameSpecificMenuItem(StandardMenuItem):
    action: Callable[[Any, Any], None]
    """Unbound method expecting `(self, runtime generated var)`"""
    can_select_external: bool = False
    """This item can select outside of just Steam libraries"""

    @property
    def is_game_specific(self) -> bool:
        return True


class MainMenu(Enum):
    MANAGE_LUA = StandardMenuItem("Process a .lua file", UI.process_lua_full)
    UPDATE_ALL_MANIFESTS = StandardMenuItem(
        "Update manifests for all outdated games", UI.update_all_manifests
    )
    DL_MANIFEST_ONLY = StandardMenuItem(
        "Download manifests ONLY from a .lua file", UI.process_lua_minimal
    )
    DL_WORKSHOP_ITEM = GameSpecificMenuItem(
        "Download workshop item manifest",
        GameHandler._dl_workshop_manifest,
        False,  # TODO: should be True and implement the stuff
    )
    DLC_CHECK = GameSpecificMenuItem(
        "Check DLC status of a game", GameHandler._check_dlc, False
    )
    CRACK_GAME = GameSpecificMenuItem(
        "Crack a game (gbe_fork)", GameHandler._find_and_crack_dll, True
    )
    REMOVE_DRM = GameSpecificMenuItem(
        "Remove SteamStub DRM (Steamless)", GameHandler.apply_steamless, True
    )
    DL_USER_GAME_STATS = GameSpecificMenuItem(
        "Download UserGameStatsSchema (achievements w/o gbe_fork)",
        GameHandler._gen_usr_game_stats,
        False,
    )
    OFFLINE_FIX = StandardMenuItem("Offline Mode Fix", UI.offline_fix_menu)
    if sys.platform == "win32":
        MANAGE_APPLIST = StandardMenuItem("Manage AppList IDs", UI.applist_menu)
    elif sys.platform == "linux":
        MANAGE_APPLIST = StandardMenuItem("Manage SLSSteam IDs", UI.applist_menu)
    else:
        MANAGE_APPLIST = StandardMenuItem("Manage injected IDs", UI.applist_menu)
    CHECK_UPDATES = StandardMenuItem("Check for updates", UI.check_updates)
    INSTALL_MENU = StandardMenuItem(
        "Install/Uninstall Context Menu", UI.manage_context_menu
    )
    SETTINGS = StandardMenuItem("Settings", UI.edit_settings_menu)
    EXIT = StandardMenuItem("Exit", lambda _: MainReturnCode.EXIT)
