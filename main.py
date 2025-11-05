import logging
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from colorama import Fore, Style
from colorama import init as color_init
from steam.client import SteamClient  # type: ignore

from smd.applist import AppListManager
from smd.midi import MidiPlayer
from smd.prompts import prompt_select
from smd.registry_access import get_steam_path
from smd.storage.settings import get_setting, set_setting
from smd.structs import (
    GAME_SPECIFIC_CHOICES,
    MainMenu,
    MainReturnCode,
    MidiFiles,
    Settings,
)
from smd.ui import UI
from smd.utils import root_folder

VERSION = "3.1.0"

logger = logging.getLogger(__name__)
logging.basicConfig(filename="debug.log", encoding="utf-8", level=logging.DEBUG)


def main() -> MainReturnCode:
    print("\n==========================================\n")
    logger.debug(f"Root folder is {root_folder()}")
    client = SteamClient()
    steam_path = get_steam_path()
    logger.debug(f"Steam path is {steam_path.resolve()}")
    app_list_man = AppListManager(steam_path)
    logger.debug(f"AppList path is {app_list_man.applist_folder.resolve()}")

    if (play_music := get_setting(Settings.PLAY_MUSIC)) is None:
        set_setting(Settings.PLAY_MUSIC, False)
        play_music = False

    if any([not x.value.exists() for x in list(MidiFiles)]) or not play_music:
        player = None
    else:
        player = MidiPlayer((MidiFiles.MIDI_PLAYER_DLL.value))
        player.start()

    ui = UI(client, app_list_man, steam_path, player)
    menu_choice: MainMenu = prompt_select("Choose:", list(MainMenu))

    if menu_choice == MainMenu.EXIT:
        return MainReturnCode.EXIT

    if menu_choice == MainMenu.SETTINGS:
        return ui.edit_settings_menu()

    if menu_choice == MainMenu.OFFLINE_FIX:
        return ui.offline_fix_menu()

    if menu_choice == MainMenu.MANAGE_APPLIST:
        return ui.applist_menu()

    if menu_choice in GAME_SPECIFIC_CHOICES:
        return ui.handle_game_specific(menu_choice)

    if TYPE_CHECKING:  # For pyright to complain when i add shit to MainMenu
        _x: Literal[MainMenu.MANAGE_LUA] = menu_choice  # noqa: F841

    return ui.process_lua_choice()


if __name__ == "__main__":
    color_init()
    version_txt = f"Version: {VERSION}"
    print(
        Fore.GREEN
        + f"""  ██████       ███▄ ▄███▓     ▓█████▄
▒██    ▒      ▓██▒▀█▀ ██▒     ▒██▀ ██▌
░ ▓██▄        ▓██    ▓██░     ░██   █▌
  ▒   ██▒     ▒██    ▒██      ░▓█▄   ▌
▒██████▒▒ ██▓ ▒██▒   ░██▒ ██▓ ░▒████▓  ██▓
▒ ▒▓▒ ▒ ░ ▒▓▒ ░ ▒░   ░  ░ ▒▓▒  ▒▒▓  ▒  ▒▓▒
░ ░▒  ░ ░ ░▒  ░  ░      ░ ░▒   ░ ▒  ▒  ░▒
░  ░  ░   ░   ░      ░    ░    ░ ░  ░  ░
      ░    ░         ░     ░     ░      ░
           ░               ░   ░        ░

┌────────────────────────────────────────┐
│{version_txt.center(40)}│
└────────────────────────────────────────┘ """
        + Style.RESET_ALL
    )
    while True:
        try:
            return_code = main()
        except Exception:
            print(
                "There was an error. You can also find this in crash.log:\n" + Fore.RED
            )
            with Path("crash.log").open("w+", encoding="utf-8") as f:
                traceback.print_exc(file=f)
                f.seek(0)
                print(f.read())
            print(Style.RESET_ALL, end="")
            input("Press Enter to restart the program...")
            continue

        if return_code == MainReturnCode.EXIT:
            break
        elif return_code == MainReturnCode.LOOP_NO_PROMPT:
            continue
        elif return_code == MainReturnCode.LOOP:
            if exit := prompt_select(
                "Go back to the Main Menu?", [("Yes", False), ("No (Exit)", True)]
            ):
                break
    print(Fore.GREEN + "\nSee You Next Time!\n" + Style.RESET_ALL)
