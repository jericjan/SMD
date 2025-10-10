import asyncio
import io
import msvcrt
import re
import shutil
import time
import winreg
import zipfile
from pathlib import Path
from typing import Any, Literal, Union, overload
from urllib.parse import urljoin

import httpx
import vdf  # type: ignore

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


def main():
    app_id_regex = re.compile(r'(?<=addappid\()\d+(?=\))')
    depot_dec_key_regex = re.compile(r'(?<=addappid\()(\d+),\d,(?:\"|\')(\S+)(?:\"|\')\)')

    steam_path = get_steam_path()
    if steam_path is None:
        steam_path = Path(input("Couldn't find your Steam path. Paste the path here (The folder that has steam.exe)"))
    else:
        print(f"Your steam path is {steam_path}")

    vdf_file = (steam_path / "config/config.vdf")
    shutil.copyfile(vdf_file, (steam_path / "config/config.vdf.backup"))

    while True:
        while True:
            lua_path = Path(input("Drag a lua file into here then press Enter:\n"))
            if lua_path.exists():
                break

        with lua_path.open(encoding="utf-8") as f:
            lua_contents = f.read()

        success = True
        if app_id := app_id_regex.search(lua_contents):
            app_id = app_id.group()
            print(f"App ID is {app_id}")
        else:
            success = False
            print("App ID not found. Try again.")

        if depot_dec_key := depot_dec_key_regex.findall(lua_contents):
            with vdf_file.open(encoding="utf-8") as f:
                vdf_data = vdf.load(f, mapper=vdf.VDFDict)  # type: ignore
            for depot_id, dec_key in depot_dec_key:
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

    manifest_ids: dict[str, str] = {}

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
