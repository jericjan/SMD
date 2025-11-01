import asyncio
import io
import re
import shutil
import time
import traceback
import zipfile
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable, Literal, Optional, cast
from urllib.parse import urljoin

import httpx
from colorama import Fore, Style
from colorama import init as color_init
from pathvalidate import sanitize_filename
from steam.client import SteamClient  # type: ignore
from steam.client.cdn import CDNClient, ContentServer  # type: ignore

from smd.applist import AppListManager
from smd.cracker import GameCracker
from smd.file_access import (
    add_decryption_key_to_config,
    add_new_lua,
    get_steam_libs,
    select_from_saved_luas,
)
from smd.http_utils import get_game_name, get_gmrc, get_named_ids
from smd.lua_downloader import download_lua
from smd.manifest_crypto import decrypt_manifest
from smd.prompts import prompt_dir, prompt_secret, prompt_select, prompt_text
from smd.registry_access import get_steam_path
from smd.storage.settings import get_setting, load_all_settings, set_setting
from smd.storage.vdf import vdf_dump, vdf_load
from smd.structs import (
    AppListChoice,
    GenEmuMode,
    LoggedInUser,
    LuaChoice,
    MainMenu,
    MainReturnCode,
    Settings,
)

VERSION = "2.3.1"


def main() -> MainReturnCode:
    app_id_regex = re.compile(r"addappid\s*\(\s*(\d+)\s*\)")
    depot_dec_key_regex = re.compile(
        r"addappid\s*\(\s*(\d+)\s*,\s*\d\s*,\s*(?:\"|\')(\S+)(?:\"|\')\s*\)"
    )

    client = SteamClient()
    cdn = CDNClient(client)
    saved_lua = Path().cwd() / "saved_lua"
    named_ids = {}
    if not saved_lua.exists():
        saved_lua.mkdir()
    else:
        named_ids = get_named_ids(saved_lua)

    steam_path = get_steam_path()
    if steam_path is None or not steam_path.exists():
        steam_path = prompt_dir(
            "Couldn't find your Steam path. Paste the "
            "path here (The folder that has steam.exe)"
        )
    else:
        print(f"Your steam path is {steam_path}")

    app_list_man = AppListManager(steam_path)

    menu_choice: MainMenu = prompt_select("Choose:", list(MainMenu))

    if menu_choice == MainMenu.EXIT:
        return MainReturnCode.EXIT

    if menu_choice == MainMenu.SETTINGS:
        while True:
            saved_settings = load_all_settings()
            selected_key: Optional[Settings] = prompt_select(
                "Select a setting to change:",
                [
                    (
                        x.clean_name
                        + (" (unset)" if x.key_name not in saved_settings else ""),
                        x,
                    )
                    for x in Settings
                ],
                cancellable=True,
            )
            if not selected_key:
                break
            value = get_setting(selected_key)
            value = value if value else "(unset)"
            print(
                f"{selected_key.clean_name} is set to "
                + Fore.YELLOW
                + ("[ENCRYPTED]" if selected_key.hidden else value)
                + Style.RESET_ALL
            )
            edit = prompt_select(
                "Do you want to edit this setting?", [("Yes", True), ("No", False)]
            )
            if not edit:
                continue
            func = prompt_secret if selected_key.hidden else prompt_text
            new_value = func("Enter the new value:")
            set_setting(selected_key, new_value)

        return MainReturnCode.LOOP_NO_PROMPT

    if menu_choice == MainMenu.OFFLINE_FIX:
        print(
            Fore.YELLOW
            + "Steam will fail to launch when you close it while in OFFLINE Mode. "
            "Set it back to ONLINE to fix it." + Style.RESET_ALL
        )
        loginusers_file = steam_path / "config/loginusers.vdf"
        if not loginusers_file.exists():
            print(
                "loginusers.vdf file can't be found. "
                "Have you already logged in once through Steam?"
            )
            return MainReturnCode.LOOP_NO_PROMPT
        vdf_data = vdf_load(loginusers_file, mapper=OrderedDict)

        vdf_users = vdf_data.get("users")
        if vdf_users is None:
            print("There are no users on this Steam installation...")
            return MainReturnCode.LOOP_NO_PROMPT
        user_ids = vdf_users.keys()
        users: list[LoggedInUser] = []
        for user_id in user_ids:
            x = vdf_users[user_id]
            users.append(
                LoggedInUser(
                    user_id,
                    x.get("PersonaName", "[MISSING]"),
                    x.get("WantsOfflineMode", "[MISSING]"),
                )
            )
        if len(users) == 0:
            print("There are no users on this Steam installation")
            return MainReturnCode.LOOP_NO_PROMPT
        offline_converter: Callable[[str], str] = lambda x: (
            "ONLINE" if x == "0" else "OFFLINE"
        )
        chosen_user: Optional[LoggedInUser] = prompt_select(
            "Select a user: ",
            [
                (
                    f"{x.PERSONA_NAME} - " + offline_converter(x.WANTS_OFFLINE_MODE),
                    x,
                )
                for x in users
            ],
            cancellable=True,
        )
        if chosen_user is None:
            return MainReturnCode.LOOP_NO_PROMPT

        new_value = "0" if chosen_user.WANTS_OFFLINE_MODE == "1" else "1"

        vdf_data["users"][chosen_user.STEAM64_ID]["WantsOfflineMode"] = new_value
        vdf_dump(loginusers_file, vdf_data)
        print(f"{chosen_user.PERSONA_NAME} is now {offline_converter(new_value)}")
        return MainReturnCode.LOOP

    if menu_choice == MainMenu.MANAGE_APPLIST:
        applist_choice: Optional[AppListChoice] = prompt_select(
            "Choose:", list(AppListChoice), cancellable=True
        )
        if applist_choice is None:
            return MainReturnCode.LOOP_NO_PROMPT
        if applist_choice == AppListChoice.DELETE:
            app_list_man.prompt_id_deletion(client)
        elif applist_choice == AppListChoice.ADD:
            validator: Callable[[str], bool] = lambda x: all(
                [y.isdigit() for y in x.split()]
            )
            digit_filter: Callable[[str], list[int]] = lambda x: [
                int(y) for y in x.split()
            ]
            ids_str: list[int] = prompt_text(
                "Input IDs that you would like to add (separate them with spaces)",
                validator=validator,
                filter=digit_filter,
            )
            for id in ids_str:
                app_list_man.add_id(id)

        return MainReturnCode.LOOP_NO_PROMPT

    steam_libs = get_steam_libs(steam_path)
    steam_lib_path: Optional[Path] = prompt_select(
        "Select a Steam library location:",
        steam_libs,
        cancellable=True,
        default=steam_libs[0],
    )
    if steam_lib_path is None:
        return MainReturnCode.LOOP_NO_PROMPT

    print(f"The game will be downloaded to: {steam_lib_path}")

    if menu_choice in (
        MainMenu.CRACK_GAME,
        MainMenu.REMOVE_DRM,
        MainMenu.DL_USER_GAME_STATS,
    ):
        cracker = GameCracker(steam_lib_path, client)
        app_info = cracker.get_game()
        if app_info is None:
            return MainReturnCode.LOOP_NO_PROMPT
        if menu_choice == MainMenu.CRACK_GAME:
            dll = cracker.find_steam_dll(app_info.path)
            if dll is None:
                print(
                    "Could not find steam_api DLL. "
                    "Maybe you haven't downloaded the game yet..."
                )
            else:
                cracker.crack_dll(app_info.app_id, dll)
        elif menu_choice == MainMenu.REMOVE_DRM:
            cracker.apply_steamless(app_info)
        elif menu_choice == MainMenu.DL_USER_GAME_STATS:
            cracker.run_gen_emu(app_info.app_id, GenEmuMode.USER_GAME_STATS)
        return MainReturnCode.LOOP

    lua_choice: Optional[LuaChoice] = prompt_select(
        "Choose:", list(LuaChoice), cancellable=True
    )

    if lua_choice is None:
        return MainReturnCode.LOOP_NO_PROMPT

    while True:
        while True:
            if lua_choice == LuaChoice.SELECT_SAVED_LUA:
                result = select_from_saved_luas(saved_lua, named_ids)
            elif lua_choice == LuaChoice.ADD_LUA:
                result = add_new_lua()
            elif lua_choice == LuaChoice.AUTO_DOWNLOAD:
                result = download_lua(saved_lua)

            if result.path is not None:
                lua_path = result.path
                if result.contents is not None:
                    lua_contents = result.contents
                else:
                    lua_contents = result.path.read_text(encoding="utf-8")
                break

            if result.switch_choice is not None:
                lua_choice = result.switch_choice

        if not (app_id_match := app_id_regex.search(lua_contents)):
            print("App ID not found. Try again.")
            continue

        app_id = app_id_match.group(1)
        print(f"App ID is {app_id}")
        app_list_man.add_id(int(app_id))

        if not (depot_dec_key := depot_dec_key_regex.findall(lua_contents)):
            print("Decryption keys not found. Try again.")
            continue

        for depot_id, _ in depot_dec_key:
            app_list_man.add_id(int(depot_id))

        vdf_file = steam_path / "config/config.vdf"
        shutil.copyfile(vdf_file, (steam_path / "config/config.vdf.backup"))
        add_decryption_key_to_config(vdf_file, depot_dec_key)

        break

    if lua_path.suffix == ".zip":
        with (saved_lua / f"{app_id}.lua").open("w", encoding="utf-8") as f:
            f.write(lua_contents)
    elif not (saved_lua / lua_path.name).exists():
        shutil.copyfile(lua_path, saved_lua / lua_path.name)

    acf_file = steam_lib_path / f"steamapps/appmanifest_{app_id}.acf"

    write_acf = True
    if acf_file.exists():
        write_acf = prompt_select(
            ".acf file found. Is this an update?",
            [("Yes", False), ("No", True)],
        )

    if write_acf:
        app_name = get_game_name(app_id)
        acf_contents: dict[str, dict[str, str]] = {
            "AppState": {
                "AppID": app_id,
                "Universe": "1",
                "name": app_name,
                "installdir": sanitize_filename(app_name),
                "StateFlags": "4",
            }
        }
        vdf_dump(acf_file, acf_contents)
        print(f"Wrote .acf file to {acf_file}")
    else:
        print("Skipped writing to .acf file")

    # A dict of Depot IDs mapped to Manifest IDs
    manifest_ids: dict[str, str] = {}

    # Get manifest IDs. The official API doesn't return these,
    # so using steam module instead
    while True:
        manifest_mode: Literal["Auto", "Manual"] = prompt_select(
            "How would you like to obtain the manifest ID?", ["Auto", "Manual"]
        )
        if manifest_mode == "Auto" and not client.logged_on:
            print("Logging in to Steam anonymously...")
            client.anonymous_login()
        app_info = (
            client.get_product_info([int(app_id)])  # type: ignore
            if manifest_mode == "Auto"
            else None
        )
        depots_dict: dict[str, Any] = (
            app_info.get("apps", {}).get(int(app_id), {}).get("depots", {})
            if app_info
            else {}
        )

        for depot_id, _ in depot_dec_key:
            latest = (
                depots_dict.get(str(depot_id), {})
                .get("manifests", {})
                .get("public", {})
                .get("gid")
            )
            if latest is None:
                if manifest_mode == "Auto":
                    print(
                        "API failed. I need the latest manifest ID for this depot. "
                        "Blank if you want to try the request again."
                    )
                if not (latest := prompt_text(f"Depot {depot_id}: ")):
                    print("Blank entered. Let's try this again.")
                    break
            print(f"Depot {depot_id} has manifest {latest}")
            manifest_ids[depot_id] = latest
        else:
            break  # User did not give a blank, end the loop

    # Download and decrypt manifests
    for depot_id, dec_key in depot_dec_key:
        manifest_id = manifest_ids[depot_id]

        while True:
            print("Getting request code...")
            req_code = asyncio.run(get_gmrc(manifest_id))
            print(f"Request code is: {req_code}")
            if req_code is not None:
                break
            print("openst.top died. Trying again in 1s")
            time.sleep(1)

        # You can get cdn urls by running download_sources in steam console
        cdn_server = cast(ContentServer, cdn.get_content_server())
        cdn_server_name = f"http{'s' if cdn_server.https else ''}://{cdn_server.host}"
        manifest_url = urljoin(
            cdn_server_name, f"depot/{depot_id}/manifest/{manifest_id}/5/{req_code}"
        )

        r = httpx.get(manifest_url, timeout=None)
        r.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(r.content)) as f:
            encrypted = io.BytesIO(f.read("z"))

        output_file = steam_path / f"depotcache/{depot_id}_{manifest_id}.manifest"

        decrypt_manifest(encrypted, output_file, dec_key)

    return MainReturnCode.LOOP


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
