import argparse
import logging
import sys
import time
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from colorama import Fore, Style
from colorama import init as color_init
from steam.client import SteamClient  # type: ignore

from smd.prompts import prompt_confirm, prompt_select
from smd.steam_client import SteamInfoProvider
from smd.steam_path import init_steam_path
from smd.storage.settings import resolve_advanced_mode
from smd.strings import VERSION
from smd.structs import GAME_SPECIFIC_CHOICES, MainMenu, MainReturnCode
from smd.ui import UI
from smd.utils import root_folder

logger = logging.getLogger("smd")
logger.setLevel(logging.DEBUG)

fh = logging.FileHandler("debug.log")
fh.setFormatter(
    logging.Formatter(
        "%(asctime)s::%(name)s::%(levelname)s::%(message)s",
        datefmt="%m/%d/%Y %I:%M:%S %p",
    )
)
logger.addHandler(fh)


def dump_crash():
    print(
        "There was an error. You can also find this in crash.log:\n" + Fore.RED
    )
    with Path("crash.log").open("w+", encoding="utf-8") as f:
        traceback.print_exc(file=f)
        f.seek(0)
        print(f.read())
    print(Style.RESET_ALL, end="")


def main(ui: UI, args: argparse.Namespace) -> MainReturnCode:

    logger.debug(f"Root folder is {root_folder()}")

    logger.debug(f"Steam path is {steam_path.resolve()}")

    logger.debug(f"AppList path is {ui.app_list_man.applist_folder.resolve()}")

    print("\n==========================================\n")
    advanced_mode = resolve_advanced_mode()
    exclude = [MainMenu.DL_MANIFEST_ONLY] if not advanced_mode else []
    if first_launch:
        logger.debug(f"Took {time.time() - start_time}s to start")
    if args.file and first_launch:
        menu_choice = MainMenu.MANAGE_LUA
    else:
        menu_choice: MainMenu = prompt_select(
            "Choose:", list(MainMenu), exclude=exclude
        )

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

    if menu_choice == MainMenu.CHECK_UPDATES:
        return ui.check_updates()

    if menu_choice == MainMenu.DL_MANIFEST_ONLY:
        return ui.process_lua_minimal()

    if TYPE_CHECKING:  # For pyright to complain when i add shit to MainMenu
        _x: Literal[MainMenu.MANAGE_LUA] = menu_choice  # noqa: F841

    if args.file:
        return ui.process_lua_full(Path(args.file))
    return ui.process_lua_full()


if __name__ == "__main__":
    start_time = time.time()
    parser = argparse.ArgumentParser(
                        prog='SMD',
                        description='Steam Manifest Decryptor',
                        epilog='bottom text')
    parser.add_argument(
        "-f", "--file", help="A .lua file or ZIP file you want to process"
    )
    args = parser.parse_args()
    logger.debug(f"Received args: {args}")
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
    try:
        client = SteamClient()
        logger.debug(f"Steam client init in {time.time() - start_time}s")
        provider = SteamInfoProvider(client)
        steam_path = init_steam_path()
        logger.debug(f"Steam path init in {time.time() - start_time}s")
        ui = UI(provider, steam_path)
    except Exception:
        dump_crash()
        input("Press Enter to exit the program...")
        sys.exit()
    logger.debug(f"Init finished in {time.time() - start_time}s")
    return_code = None
    first_launch = True
    while True:
        try:
            return_code = main(ui, args)
            first_launch = False
        except KeyboardInterrupt:
            print(Fore.RED + "\nWait, don't go—\n" + Style.RESET_ALL)
            return_code = None
            break
        except Exception:
            dump_crash()
            input("Press Enter to restart the program...")
            continue

        if return_code == MainReturnCode.EXIT:
            break
        elif return_code == MainReturnCode.LOOP_NO_PROMPT:
            continue
        elif return_code == MainReturnCode.LOOP:
            if not prompt_confirm("Go back to the Main Menu?", false_msg="No (Exit)"):
                break
    if return_code is not None:
        print(Fore.GREEN + "\nSee You Next Time!\n" + Style.RESET_ALL)
