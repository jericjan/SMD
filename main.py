import asyncio
import io
import json
import msvcrt
import re
import shutil
import time
import winreg
import zipfile
from base64 import b64decode, b64encode
from enum import Enum
from pathlib import Path
from tempfile import TemporaryFile
from types import TracebackType
from typing import Any, Literal, NamedTuple, Optional, Union, cast, overload
from urllib.parse import urljoin

import httpx
import vdf  # type: ignore
from colorama import Fore, Style
from colorama import init as color_init
from pathvalidate import sanitize_filename
from steam.client import SteamClient  # type: ignore
from steam.client.cdn import CDNClient, ContentServer  # type: ignore

from cracker import GameCracker
from decrypt_manifest import decrypt_manifest
from utils import enter_path, get_setting, prompt_secret, prompt_select, set_setting

VERSION = "1.1"


class LuaChoice(Enum):
    ADD_LUA = "Add a .lua file"
    SELECT_SAVED_LUA = "Choose from saved .lua files"
    AUTO_DOWNLOAD = "Automatically download a .lua file"


class MainMenu(Enum):
    MANAGE_LUA = "Manage .lua files"
    CRACK_GAME = "Crack a game (gbe_fork)"
    REMOVE_DRM = "Remove SteamStub DRM (Steamless)"
    EXIT = "Exit"


class LuaEndpoint(Enum):
    OUREVERYDAY = "oureveryday (quick but could be limited)"
    MANILUA = "Manilua (more stuff, needs API key)"


class MainReturnCode(Enum):
    LOOP = 0
    EXIT = 1


class LuaResult(NamedTuple):
    path: Optional[Path]  # path on disk if file exists
    contents: Optional[str]  # string contents of file (e.g., from zip read)
    switch_choice: Optional["LuaChoice"]


def get_steam_path():
    """Get the user's Steam location.
    Checks CurrentUser first, then LocalMachine"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Valve\Steam") as key:
            return Path(winreg.QueryValueEx(key, "SteamPath")[0])
    except FileNotFoundError:
        pass

    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"
        ) as key:
            return Path(winreg.QueryValueEx(key, "InstallPath")[0])
    except FileNotFoundError:
        return None


@overload
async def get_request(url: str) -> Union[str, None]: ...


@overload
async def get_request(url: str, type: Literal["text"]) -> Union[str, None]: ...


@overload
async def get_request(
    url: str, type: Literal["json"]
) -> Union[dict[Any, Any], None]: ...


async def get_request(
    url: str, type: Literal["text", "json"] = "text", timeout: int = 10
) -> Union[str, dict[Any, Any], None]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)

        if response.status_code == 200:
            try:
                return response.text if type == "text" else response.json()
            except ValueError:
                return
        else:
            print(f"❌ Request failed with status code: {response.status_code}")
            print(f"Response: {response.text}")

    except httpx.RequestError as e:
        print(f"An error occurred: {e}")


async def wait_for_enter():
    print(
        "If it takes too long, press Enter to cancel the request "
        "and input manually..."
    )
    while True:
        if msvcrt.kbhit() and msvcrt.getch() == b"\r":
            return
        await asyncio.sleep(0.05)


async def get_gmrc(manifest_id: Union[str, int]) -> Union[str, None]:
    """Gets a manifest request code, given a manifest ID

    Args:
        manifest_id (Union[str, int]): The manifest ID

    Returns:
        str: The request code
    """
    url = f"http://gmrc.openst.top/manifest/{manifest_id}"
    print(f"Requesting from URL: {url}")

    request_task = asyncio.create_task(get_request(url))
    cancel_task = asyncio.create_task(wait_for_enter())

    done, pending = await asyncio.wait(
        {request_task, cancel_task}, return_when=asyncio.FIRST_COMPLETED
    )

    result = None
    if request_task in done:
        result = request_task.result()

    if cancel_task in done:
        if not request_task.done():
            print("Cancelling request...", end="")
            request_task.cancel()

    for t in pending:
        t.cancel()

    try:
        if result is None:
            result = await request_task
    except asyncio.CancelledError:
        print("✅")
        result = input("Please provide the manifest request code: ")

    return result


class AppListManager:
    def __init__(self, steam_path: Path):
        self.max_id_limit = 168
        self.steam_path = steam_path
        self.applist_folder = steam_path / "AppList"
        self.last_idx = 0
        if not self.applist_folder.exists():
            self.applist_folder = Path(
                input(
                    "Could not find AppList folder. "
                    "Please specify the full path here:\n"
                ).strip("\"'")
            )
            # TODO: save this path in a settings.json or smth

    def get_local_ids(self):
        ids: list[str] = []
        for file in self.applist_folder.glob("*.txt"):
            if file.stem.isdigit():
                if int(file.stem) > self.last_idx:
                    self.last_idx = int(file.stem)
            ids.append(file.read_text(encoding="utf-8").strip())
        return ids

    def add_id(self, id: str):
        ids = self.get_local_ids()
        if id not in ids:
            new_idx = self.last_idx + 1
            with (self.applist_folder / f"{new_idx}.txt").open("w") as f:
                f.write(id)
            self.last_idx = new_idx
            print(
                f"{id} added to AppList. "
                f"There are now {len(ids) + 1} IDs stored."
            )
            if (len(ids) + 1) > self.max_id_limit:
                print(
                    Fore.RED + f"WARNING: You've hit the {self.max_id_limit} ID limit "
                    "for Greenluma. "
                    "I haven't implemented anything to deal with this yet."
                    + Style.RESET_ALL
                )
        else:
            print(f"{id} already in AppList")


def get_steam_libs(steam_path: Path):
    """Get list of Steam library paths by the user

    Args:
        steam_path (Path): Steam install path

    Returns:
        list[Path]: list of Steam library paths
    """
    lib_folders = steam_path / "config/libraryfolders.vdf"

    with lib_folders.open(encoding="utf-8") as f:
        vdf_data: dict[Any, Any] = vdf.load(f)  # type: ignore

    paths: list[Path] = []
    for library in vdf_data["libraryfolders"].values():
        if (path := Path(library["path"])).exists():
            paths.append(path)

    return paths


def get_game_name(app_id: str):
    official_info = asyncio.run(
        get_request(
            f"https://store.steampowered.com/api/appdetails/?appids={app_id}",
            "json",
        )
    )
    if official_info:
        app_name = official_info.get(app_id, {}).get("data", {}).get("name")
        if app_name is None:
            app_name = input(
                "Request succeeded but couldn't find the game name. "
                "Type the name of it: "
            )
    else:
        app_name = input("Request failed. Type the name of the game: ")
    return app_name


def get_named_ids(folder: Path):
    """Gets names of games from lua files

    Args:
        folder (Path): Folder with .lua files in it

    Returns:
        dict: a dict in the format (game_id, game_name)
    """
    saved_ids = [x.stem for x in folder.glob("*.lua")]
    id_names_file = folder / "names.json"
    named_ids: dict[str, str] = {}
    if not id_names_file.exists():
        with id_names_file.open("w", encoding="utf-8") as f:
            json.dump({}, f)
    else:
        with id_names_file.open("r", encoding="utf-8") as f:
            named_ids = json.load(f)
    new_ids = 0
    for saved_id in saved_ids:
        if saved_id not in named_ids.keys():
            new_ids += 1
            name = get_game_name(saved_id)
            named_ids[saved_id] = name

    if new_ids > 0:
        with id_names_file.open("w", encoding="utf-8") as f:
            json.dump(named_ids, f, indent=2)
    return named_ids


def find_lua_in_zip(path: Path):
    """Given a zip path, return the string contents,
    blank if it can't be found"""
    lua_contents = ""
    with zipfile.ZipFile(path) as zf:
        for file in zf.filelist:
            if file.filename.endswith(".lua"):
                print(f".lua found: {file.filename}")
                lua_contents = zf.read(file).decode(encoding="utf-8")
                break  # lua found in ZIP, stop searching
    return lua_contents


def select_from_saved_luas(saved_lua: Path, named_ids: dict[str, str]) -> LuaResult:
    """Prompt the user to select a saved lua file

    Args:
        saved_lua (Path): Path to the folder with saved lua files
        named_ids (dict[str, str]): A dict of (game_id, game_name)

    Returns:
        LuaResult:
    """
    if len(named_ids) == 0:
        print("You don't have any saved .lua files. Try adding some first.")
        return LuaResult(None, None, LuaChoice.ADD_LUA)
    lua_path: Optional[Path] = prompt_select(
        "Choose a game:",
        [(name, saved_lua / f"{app_id}.lua") for app_id, name in named_ids.items()]
        + [("(Add a lua file instead)", None)],
        fuzzy=True,
    )
    if lua_path is None or not lua_path.exists():
        return LuaResult(None, None, LuaChoice.ADD_LUA)
    return LuaResult(lua_path, None, None)


def add_new_lua() -> LuaResult:
    """Prompts user to add a new .lua file

    Returns:
        LuaResult:
    """
    lua_path = Path(
        input(
            "Drag a .lua file (or .zip w/ .lua inside) into here "
            "then press Enter.\n"
            "Leave it blank to switch to selecting a saved .lua:\n"
        ).strip("\"'")
    )
    if not lua_path.exists():
        print("That file does not exist. Try again.")
        return LuaResult(None, None, None)

    if lua_path.samefile(Path.cwd()):  # Blank input
        # Switch to other option
        return LuaResult(None, None, LuaChoice.SELECT_SAVED_LUA)

    if lua_path.suffix == ".zip":
        lua_contents = find_lua_in_zip(lua_path)
        if lua_contents == "":
            print("Could not find .lua in ZIP file.")
            return LuaResult(None, None, None)
        return LuaResult(lua_path, lua_contents, None)
    return LuaResult(lua_path, None, None)


class VDFManager:
    def __init__(self, path: Path):
        self.path = path
        self.data = vdf.VDFDict()

    def __enter__(self):
        with self.path.open(encoding="utf-8") as f:
            self.data: vdf.VDFDict = vdf.load(f, mapper=vdf.VDFDict)  # type: ignore
        return self.data

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        exc_traceback: Optional[TracebackType],
    ):
        with self.path.open("w", encoding="utf-8") as f:
            vdf.dump(self.data, f, pretty=True)  # type: ignore


def add_decryption_key_to_config(vdf_file: Path, depot_dec_key: list[tuple[str, str]]):
    with VDFManager(vdf_file) as vdf_data:
        for depot_id, dec_key in depot_dec_key:
            print(f"Depot {depot_id} has decryption key {dec_key}...", end="")
            depots = enter_path(
                vdf_data,
                "InstallConfigStore",
                "Software",
                "Valve",
                "Steam",
                "depots",
                mutate=True,
            )
            if depot_id not in depots:
                depots[depot_id] = {"DecryptionKey": dec_key}
                print("Added to config.vdf succesfully.")
            else:
                print("Already in config.vdf.")


def get_oureverday(dest: Path, app_id: str):
    lua_contents = asyncio.run(get_request(
        f"https://raw.githubusercontent.com/SteamAutoCracks/ManifestHub/refs/heads/{app_id}/{app_id}.lua"
    ))
    if lua_contents is None:
        return
    lua_path = (dest / f"{app_id}.lua")
    with lua_path.open("w", encoding="utf-8") as f:
        f.write(lua_contents)
    return lua_path


def get_manilua(dest: Path, app_id: str):
    url = f"https://www.piracybound.com/api/game/{app_id}"
    chunk_size = (1024**2) // 2  # 0.5 MiB

    if (manilua_key := get_setting("manilua_key")) is None:
        manilua_key = prompt_secret(
            "Paste your manilua API key here: ",
            lambda x: x.startswith("manilua"),
            "That's not a manilua key!",
            long_instruction=(
                "Go the manilua website and request an API key. It's free."
            ),
        ).strip()
        manilua_key = b64encode(manilua_key.encode()).decode()
        set_setting("manilua_key", manilua_key)

    manilua_key = b64decode(manilua_key).decode()

    headers = {
        "Authorization": f"Bearer {manilua_key}",
    }

    with httpx.stream("GET", url, headers=headers) as response:
        try:
            total = int(response.headers.get('Content-Length', '0'))
        except Exception as e:
            print(f"Could not parse Content-Length header: {e}")
            total = 0

        bytes_downloaded = 0
        with TemporaryFile(buffering=chunk_size) as f:
            for chunk in response.iter_bytes(chunk_size=chunk_size):
                if not chunk:
                    continue
                f.write(chunk)
                bytes_downloaded += len(chunk)
                print(f"Downloaded {bytes_downloaded} / {total}")

            f.seek(0)
            data = f.read()
    lua_bytes = b''
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            files = zf.filelist
            for file in files:
                if file.filename.endswith("lua"):
                    lua_bytes = zf.read(file.filename)
                    break
            else:  # lua not found
                print("Could not find the lua in the ZIP")
                return
    except zipfile.BadZipFile:
        f.seek(0)
        try:
            print(Fore.RED + json.dumps(json.load(f)) + Style.RESET_ALL)
        except json.JSONDecodeError:
            print(
                "Did not receive a ZIP file or JSON: \n"
                + f.read().decode()
            )

    lua_path = dest / f"{app_id}.lua"
    if len(lua_bytes) > 0:
        with lua_path.open("wb") as f:
            f.write(lua_bytes)
        return lua_path


def download_lua(dest: Path) -> LuaResult:
    """Downloads a lua file from two endpoints"""
    source: LuaEndpoint = prompt_select("Select an endpoint:", list(LuaEndpoint))

    while True:
        app_id = input('Enter the App ID or Store link: ').strip()
        if match := re.search(r"(?<=store\.steampowered\.com\/app\/)\d+|\d+", app_id):
            app_id = match.group()
            break
        print("Not a valid format. Just type the App ID.")

    if source == LuaEndpoint.OUREVERYDAY:
        lua_path = get_oureverday(dest, app_id)
    elif source == LuaEndpoint.MANILUA:
        lua_path = get_manilua(dest, app_id)

    if lua_path is None:
        restart = prompt_select(
            "Could not find it. Try again?",
            [("Yes", True), ("No (Add a .lua instead)", False)],
        )
        if restart:
            return LuaResult(None, None, None)
        print("Switching to manual .lua selection...")
        return LuaResult(None, None, LuaChoice.ADD_LUA)

    return LuaResult(lua_path, None, None)


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
    if steam_path is None:
        steam_path = Path(
            input(
                "Couldn't find your Steam path. Paste the "
                "path here (The folder that has steam.exe)"
            ).strip("\"'")
        )
    else:
        print(f"Your steam path is {steam_path}")

    app_list_man = AppListManager(steam_path)

    vdf_file = steam_path / "config/config.vdf"
    shutil.copyfile(vdf_file, (steam_path / "config/config.vdf.backup"))

    steam_libs = get_steam_libs(steam_path)
    steam_lib_path: Path = prompt_select(
        "Where do you want to download the game?:", steam_libs
    )
    print(f"The game will be download to: {steam_lib_path}")

    menu_choice: MainMenu = prompt_select("Choose:", list(MainMenu))

    if menu_choice == MainMenu.EXIT:
        return MainReturnCode.EXIT

    if menu_choice in (MainMenu.CRACK_GAME, MainMenu.REMOVE_DRM):
        cracker = GameCracker(steam_lib_path, client)
        app_info = cracker.get_game()
        if menu_choice == MainMenu.CRACK_GAME:
            dll = cracker.find_steam_dll(app_info.path)
            if dll is None:
                print(
                    "Could not find steam_api DLL. "
                    "Maybe you haven't downloaded the game yet..."
                )
            else:
                cracker.crack_dll(app_info.app_id, dll)
        else:
            cracker.apply_steamless(app_info)
        return MainReturnCode.LOOP

    lua_choice: LuaChoice = prompt_select("Choose:", list(LuaChoice))

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
        app_list_man.add_id(app_id)

        if not (depot_dec_key := depot_dec_key_regex.findall(lua_contents)):
            print("Decryption keys not found. Try again.")
            continue

        for depot_id, _ in depot_dec_key:
            app_list_man.add_id(depot_id)

        add_decryption_key_to_config(vdf_file, depot_dec_key)

        break

    if lua_path.suffix == ".zip":
        with (saved_lua / f"{app_id}.lua").open("w", encoding="utf-8") as f:
            f.write(lua_contents)
    elif not (saved_lua / lua_path.name).exists():
        shutil.copyfile(lua_path, saved_lua / lua_path.name)

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
    acf_file = steam_lib_path / f"steamapps/appmanifest_{app_id}.acf"

    write_acf = True
    if acf_file.exists():
        write_acf = prompt_select(
            ".acf file found. Is this an update?",
            [("Yes", False), ("No", True)],
        )

    if write_acf:
        with acf_file.open("w", encoding="utf-8") as f:
            vdf.dump(acf_contents, f, pretty=True)  # type: ignore
        print(f"Wrote .acf file to {acf_file}")
    else:
        print("Skipped writing to .acf file")

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
                if not (latest := input(f"Depot {depot_id}: ").strip()):
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
    print(Fore.GREEN + f"""  ██████       ███▄ ▄███▓     ▓█████▄
▒██    ▒      ▓██▒▀█▀ ██▒     ▒██▀ ██▌
░ ▓██▄        ▓██    ▓██░     ░██   █▌
  ▒   ██▒     ▒██    ▒██      ░▓█▄   ▌
▒██████▒▒ ██▓ ▒██▒   ░██▒ ██▓ ░▒████▓  ██▓
▒ ▒▓▒ ▒ ░ ▒▓▒ ░ ▒░   ░  ░ ▒▓▒  ▒▒▓  ▒  ▒▓▒
░ ░▒  ░ ░ ░▒  ░  ░      ░ ░▒   ░ ▒  ▒  ░▒
░  ░  ░   ░   ░      ░    ░    ░ ░  ░  ░
      ░    ░         ░     ░     ░      ░
           ░               ░   ░        ░ \nVersion: {VERSION}""" + Style.RESET_ALL)
    while True:
        if main() == MainReturnCode.EXIT:
            break
        elif not (
            choice := prompt_select(
                "Go back to the Main Menu?", [("Yes", True), ("No", False)]
            )
        ):
            break
