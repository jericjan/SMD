import asyncio
import io
import msvcrt
import re
import shutil
import time
import winreg
import zipfile
from pathlib import Path
from typing import Any, Literal, Optional, Union, overload
from urllib.parse import urljoin

import httpx
import vdf  # type: ignore
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from pathvalidate import sanitize_filename
import json
from decrypt_manifest import decrypt_manifest


def get_steam_path():
    """Get the user's Steam location. Checks CurrentUser first, then LocalMachine"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Valve\Steam") as key:
            return Path(winreg.QueryValueEx(key, "SteamPath")[0])
    except FileNotFoundError:
        pass

    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\WOW6432Node\Valve\Steam"
        ) as key:
            return Path(winreg.QueryValueEx(key, "InstallPath")[0])
    except FileNotFoundError:
        return None


@overload
async def get_request(url: str) -> Union[str, None]:
    ...


@overload
async def get_request(url: str, type: Literal["text"]) -> Union[str, None]:
    ...


@overload
async def get_request(url: str, type: Literal["json"]) -> Union[dict[Any, Any], None]:
    ...


async def get_request(url: str, type: Literal['text', 'json'] = "text", timeout: int = 10) -> Union[str, dict[Any, Any], None]:
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
    print("If it takes too long, press Enter to cancel the request and input manually...")
    while True:
        if msvcrt.kbhit() and msvcrt.getch() == b'\r':
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
        {request_task, cancel_task},
        return_when=asyncio.FIRST_COMPLETED
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
            self.applist_folder = Path(input("Could not find AppList folder. Please specify the full path here:\n"))
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
            print(f"{id} added to AppList. There are now {len(ids) + 1} IDs stored.")            
        else:
            print(f"{id} already in AppList")


def get_steam_libs(steam_path: Path):
    lib_folders = steam_path / "config/libraryfolders.vdf"

    with lib_folders.open(encoding="utf-8") as f:
        vdf_data: dict[Any, Any] = vdf.load(f)  # type: ignore

    paths: list[str] = []
    for library in vdf_data['libraryfolders'].values():
        if Path(path := library['path']).exists():
            paths.append(path)

    return paths


def prompt_select(msg: str, choices: Union[list[str], list[Choice]], default: Optional[Any] = None, indexed: bool = False, fuzzy: bool = False):
    new_choices = (
        [Choice(value=idx, name=(x.name if isinstance(x, Choice) else x)) for idx, x in enumerate(choices)]
        if indexed else choices
    )
    cmd = inquirer.fuzzy if fuzzy else inquirer.select  # type: ignore
    return cmd(
        message=msg,
        choices=new_choices,
        default=default,
    ).execute()


def get_game_name(app_id: str):
    official_info = asyncio.run(get_request(f"https://store.steampowered.com/api/appdetails/?appids={app_id}", "json"))
    if official_info:
        app_name = official_info.get(app_id, {}).get("data", {}).get("name")
        if app_name is None:
            app_name = input("Request succeeded but couldn't find the game name. Type the name of it: ")    
    else:
        app_name = input("Request failed. Type the name of the game: ")    
    return app_name


def get_named_ids(folder: Path):
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


def main():
    app_id_regex = re.compile(r'(?<=addappid\()\d+(?=\))')
    depot_dec_key_regex = re.compile(r'(?<=addappid\()(\d+),\d,(?:\"|\')(\S+)(?:\"|\')\)')

    saved_lua = Path().cwd() / "saved_lua"
    named_ids = {}
    if not saved_lua.exists():
        saved_lua.mkdir()
    else:
        named_ids = get_named_ids(saved_lua)

    steam_path = get_steam_path()
    if steam_path is None:
        steam_path = Path(input("Couldn't find your Steam path. Paste the path here (The folder that has steam.exe)"))
    else:
        print(f"Your steam path is {steam_path}")

    app_list_man = AppListManager(steam_path)

    vdf_file = (steam_path / "config/config.vdf")
    shutil.copyfile(vdf_file, (steam_path / "config/config.vdf.backup"))

    steam_libs = get_steam_libs(steam_path)
    steam_lib_path = prompt_select("Where do you want to download the game?:", steam_libs)
    print(f"The game will be download to: {steam_lib_path}")

    first_choice = prompt_select("Choose:", ["Add a lua file", "Choose from saved .lua files"], indexed=True)

    while True:
        while True:
            if first_choice == 1:
                lua_path: Optional[Path] = prompt_select(
                    "Choose a game:",
                    [
                        Choice(value=saved_lua / f"{app_id}.lua", name=name)
                        for app_id, name in named_ids.items()
                    ] + [Choice(value=None, name="(Add a lua file instead)")],
                    fuzzy=True
                )
                if lua_path is None or not lua_path.exists():
                    first_choice = 0
                    continue
                else:
                    break
            else:
                lua_path = Path(input("Drag a lua file into here then press Enter:\n"))
                if lua_path.exists():
                    break
                else:
                    print("That file does not exist. Try again.")

        with lua_path.open(encoding="utf-8") as f:
            lua_contents = f.read()

        success = True
        if app_id := app_id_regex.search(lua_contents):
            app_id = app_id.group()
            print(f"App ID is {app_id}")
            app_list_man.add_id(app_id)
        else:
            success = False
            print("App ID not found. Try again.")

        if depot_dec_key := depot_dec_key_regex.findall(lua_contents):
            with vdf_file.open(encoding="utf-8") as f:
                vdf_data = vdf.load(f, mapper=vdf.VDFDict)  # type: ignore
            for depot_id, dec_key in depot_dec_key:
                app_list_man.add_id(depot_id)
                print(f"Depot {depot_id} has decryption key {dec_key}...", end="")
                if depot_id not in vdf_data['InstallConfigStore']['Software']['Valve']['Steam']['depots']:
                    vdf_data['InstallConfigStore']['Software']['Valve']['Steam']['depots'][depot_id] = {'DecryptionKey': dec_key}
                    print("Added to config.vdf succesfully.")
                else:
                    print("Already in config.vdf.")
            with vdf_file.open("w", encoding="utf-8") as f:
                vdf.dump(vdf_data, f, pretty=True)  # type: ignore

        else:
            success = False
            print("Decryption keys not found. Try again.")

        if success:
            assert app_id is not None
            break

    if not (saved_lua / lua_path.name).exists():
        shutil.copyfile(lua_path, saved_lua / lua_path.name)

    app_name = get_game_name(app_id)

    acf_contents: dict[str, dict[str, str]] = {
        "AppState":
        {
            "AppID": app_id,
            "Universe": "1",
            "name": app_name,
            "installdir": sanitize_filename(app_name),
            "StateFlags": "4"
        }
    }
    acf_file = steam_lib_path / f"steamapps/appmanifest_{app_id}.acf"

    with acf_file.open("w", encoding="utf-8") as f:
        vdf.dump(acf_contents, f, pretty=True)  # type: ignore
    print(f"Wrote .acf file to {acf_file}")

    manifest_ids: dict[str, str] = {}

    # The official API doesn't return manifest IDs so using this one instead
    app_info = asyncio.run(get_request(f"https://api.steamcmd.net/v1/info/{app_id}", "json"))
    if app_info is None:
        print("Steamcmd api failed. Please supply latest manifest IDs for the following depots:")
        for depot_id, _ in depot_dec_key:
            manifest_ids[depot_id] = input(f"Depot {depot_id}: ")
    else:
        depots_dict: dict[str, Any] = app_info.get("data", {}).get(app_id, {}).get("depots", {})
        for depot_id, _ in depot_dec_key:
            latest = depots_dict.get(depot_id, {}).get("manifests", {}).get("public", {}).get("gid")
            if latest is None:
                latest = input(f"Steamcmd API somehow returned malformed response. Supply latest manifest ID for depot {depot_id}: ")
            print(f"Depot {depot_id} has manifest {latest}")
            manifest_ids[depot_id] = latest

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

        cdn = "https://cache1-man-rise.steamcontent.com/"  # You can get cdn urls by running download_sources in steam console
        manifest_url = urljoin(cdn, f"depot/{depot_id}/manifest/{manifest_id}/5/{req_code}")

        r = httpx.get(manifest_url)
        r.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(r.content)) as f:
            encrypted = io.BytesIO(f.read("z"))

        output_file = (steam_path / f"depotcache/{depot_id}_{manifest_id}.manifest")

        decrypt_manifest(encrypted, output_file, dec_key)


if __name__ == "__main__":
    main()
