import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from colorama import Fore, Style
from colorama import init as color_init
from steam.client import SteamClient  # type: ignore

from smd.applist import AppListManager
from smd.prompts import prompt_select
from smd.registry_access import get_steam_path
from smd.structs import GAME_SPECIFIC_CHOICES, MainMenu, MainReturnCode
from smd.ui import UI

VERSION = "2.3.1"


def main() -> MainReturnCode:
    client = SteamClient()
    steam_path = get_steam_path()
    app_list_man = AppListManager(steam_path)
    ui = UI(client, app_list_man, steam_path)
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
           ░               ░   ░        ░ \nVersion: {VERSION}"""
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
