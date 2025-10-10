import io
import re
import time
import zipfile
from pathlib import Path
from typing import Literal, Union, cast
from urllib.parse import urljoin

import requests

from decrypt_manifest import decrypt_manifest


def get_request(url: str, type: Literal['text', 'json'] = "text"):
    try:
        response = requests.get(url)

        if response.status_code == 200:
            try:
                return response.text if type == "text" else response.json()
            except requests.exceptions.JSONDecodeError:
                return
        else:
            print(f"❌ Request failed with status code: {response.status_code}")
            print(f"Response: {response.text}")

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")

def get_gmrc(manifest_id: Union[str, int]):
    get_request(f"http://gmrc.openst.top/manifest/{manifest_id}")

def main():
    app_id_regex = re.compile(r'(?<=addappid\()\d+(?=\))')
    depot_dec_key_regex = re.compile(r'(?<=addappid\()(\d+),\d,(?:\"|\')(\S+)(?:\"|\')\)')

    while True:
        while True:
            lua_path = Path(input("Drag a lua file into here then press Enter."))
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
            for depot_id, dec_key in depot_dec_key:
                print(f"Depot {depot_id} has decryption key {dec_key}")            
        else:
            success = False
            print("Decryption keys not found. Try again.")

        if success:
            break

    manifest_ids: dict[str, str] = {}

    app_info: Union[dict[str, str], None] = get_request(f"https://api.steamcmd.net/v1/info/{app_id}", "json")
    if app_info is None:
        print("Steamcmd api failed. Please supply latest manifest IDs for the following depots:")
        for depot_id, _ in depot_dec_key:
            manifest_ids[depot_id] = input(f"Depot {depot_id}: ")
    else:
        depots_dict: dict[str, str] = app_info.get("data", {}).get(app_id, {}).get("depots", {})  # type: ignore
        for depot_id, _ in depot_dec_key:
            latest = depots_dict.get(depot_id, {}).get("manifests", {}).get("public", {}).get("gid")
            print(f"Depot {depot_id} has manifest {latest}")
            manifest_ids[depot_id] = cast(str, latest)
    
    for depot_id, dec_key in depot_dec_key:
        manifest_id = manifest_ids[depot_id]

        while True:
            print("Getting request code...")
            req_code = get_gmrc(manifest_id)
            print(f"Request code is: {req_code}")
            if req_code is not None:
                break
            print("openst.top died. Trying again in 1s")
            time.sleep(1)

        cdn = "https://cache1-man-rise.steamcontent.com/"  # You can get cdn urls by running download_sources in steam console
        manifest_url = urljoin(cdn, f"depot/{depot_id}/manifest/{manifest_id}/5/{req_code}")

        r = requests.get(manifest_url)
        r.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(r.content)) as f:
            encrypted = io.BytesIO(f.read("z"))

        decrypt_manifest(encrypted, f"{depot_id}_{manifest_id}.manifest", dec_key)


if __name__ == "__main__":
    main()