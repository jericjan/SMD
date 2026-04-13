"""API endpoints are in here"""

import asyncio
import io
import json
import logging
from pathlib import Path
import re
from typing import Optional

from colorama import Fore, Style

from smd.http_utils import download_to_tempfile, get_request
from smd.prompts import prompt_confirm
from smd.steam_client import SteamInfoProvider
from smd.storage.settings import resolve_morrenus_key
from smd.strings import OUREVERYDAY_COMMIT_INFO_URL, OUREVERYDAY_RAW_JSON_URL
from smd.utils import root_folder
from smd.zip import read_lua_from_zip

logger = logging.getLogger(__name__)


def get_oureverday(dest: Path, app_id: str):
    def get_latest_hash():
        commit_data = asyncio.run(
            get_request(
                OUREVERYDAY_COMMIT_INFO_URL,
                "json",
            )
        )
        return commit_data[0].get("id") if commit_data else None

    def download_json():
        latest_hash = get_latest_hash()
        if latest_hash is None:
            return
        json_data = asyncio.run(
            get_request(
                OUREVERYDAY_RAW_JSON_URL.format(latest_hash),
                "json",
            )
        )
        if json_data is None:
            return
        with (
            root_folder(outside_internal=True) / f"oureveryday_{latest_hash}.json"
        ).open("w", encoding="utf-8") as f:
            f.write(json.dumps(json_data))
        return json_data

    if not list(root_folder(outside_internal=True).glob("oureveryday_*.json")):
        print("oureverday json file not found. Downloading...")
        json_data = download_json()
        if json_data is None:
            print("Couldn't download JSON.")
            return
    else:
        filename_re = re.compile(r"oureveryday_([a-f0-9A-F]+)\.json")
        oureveryday_jsons = list(
            root_folder(outside_internal=True).glob("oureveryday_*.json")
        )
        oureveryday_jsons = [x for x in oureveryday_jsons if filename_re.match(x.name)]
        oureveryday_jsons.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        latest_json = oureveryday_jsons[0]
        latest_hash = get_latest_hash()
        if latest_hash is None:
            print("Couldn't get latest hash from the repo")
            return
        current_hash = filename_re.match(latest_json.name)
        assert current_hash is not None
        current_hash = current_hash.group(1)
        if latest_hash != current_hash:
            print("A newer file is available. Downloading...")
            json_data = download_json()
            if json_data is None:
                print("Download failed.")
                return
        else:
            with latest_json.open("r", encoding="utf-8") as f:
                json_data = json.load(f)

    provider = SteamInfoProvider()
    info = provider.get_single_app_info(int(app_id))
    # print(info)
    depots = info.get("depots")
    if depots is None:
        print(f"Couldn't find depots for {app_id}")
        return
    depot_ids = [app_id] + [x for x in depots if x.isnumeric()]

    all_dlc_info = provider.expand_dlc(info)
    # In case API doesnt return one of the IDs (i.e. ID is not a depot)
    depot_ids.extend([str(x) for x in all_dlc_info.keys()])
    dlc_depots: list[str] = []
    for dlc_data in all_dlc_info.values():
        depots = dlc_data.get("depots", {})
        if depots:
            dlc_depots.extend([x for x in depots.keys() if x.isnumeric()])
    depot_ids.extend(dlc_depots)
    depot_ids = list(dict.fromkeys(depot_ids))
    key_matches = {x: json_data.get(x) for x in depot_ids}
    lua_contents = ""
    for depot_id, dec_key in key_matches.items():
        if dec_key is None:
            lua_contents += f"addappid({depot_id})\n"
            continue
        lua_contents += f"addappid({depot_id}, 1, \"{dec_key}\")\n"

    lua_path = dest / f"{app_id}.lua"
    if lua_contents:
        with lua_path.open("w", encoding="utf-8") as f:
            f.write(lua_contents)
        return lua_path


def get_morrenus(dest: Path, app_id: str) -> Optional[Path]:
    url = f"https://manifest.morrenus.xyz/api/v1/manifest/{app_id}"

    morrenus_key = resolve_morrenus_key()

    headers = {
        "Authorization": f"Bearer {morrenus_key}",
    }

    data = asyncio.run(
        get_request(
            "https://manifest.morrenus.xyz/api/v1/user/stats",
            type="json",
            headers=headers,
        )
    )
    if data is None:
        if prompt_confirm("Couldn't get usage stats from Morrenus. Try again?"):
            lua_path = get_morrenus(dest, app_id)
            return lua_path
        return
    usage = data.get("daily_usage")
    limit = data.get("daily_limit")
    state = data.get("can_make_requests")

    if not state:
        print(
            Fore.RED
            + f"Daily limit exceeded! You used {usage if usage else '??'}/"
            f"{limit if limit else '??'}"
            + Style.RESET_ALL
        )
    else:
        if usage is None or limit is None:
            if not prompt_confirm("Could not get usage limits. "
                                  "Would you like to continue regardless?"):
                return
        logger.debug(f"Downloading lua files from {url}")
        lua_bytes = b''
        while True:
            with download_to_tempfile(url, headers) as tf:
                if tf is None:
                    if prompt_confirm("Try again?"):
                        continue
                    break

                data = tf.read()
                print(
                    Fore.GREEN
                    + "Morrenus Daily Limit: "
                    f"{usage+1 if usage is not None else '??'}/"
                    f"{limit if limit is not None else '??'}"
                    + Style.RESET_ALL
                )
                lua_bytes = read_lua_from_zip(io.BytesIO(data), decode=False)
                if lua_bytes is None:
                    tf.seek(0)
                    try:
                        print(
                            Fore.RED
                            + json.dumps(json.load(tf), indent=2)
                            + Style.RESET_ALL
                        )
                    except json.JSONDecodeError:
                        print(
                            "Did not receive a ZIP file or JSON: \n"
                            + tf.read().decode()
                        )
                    except UnicodeDecodeError:
                        pass
            break

        lua_path = dest / f"{app_id}.lua"
        if lua_bytes:
            with lua_path.open("wb") as f:
                f.write(lua_bytes)
            return lua_path
