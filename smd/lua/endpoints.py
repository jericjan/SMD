"""API endpoints are in here"""

import asyncio
import io
import json
import logging
from pathlib import Path
from typing import Optional

from colorama import Fore, Style

from smd.http_utils import download_to_tempfile, get_request
from smd.prompts import prompt_confirm, prompt_secret
from smd.storage.settings import get_setting, set_setting
from smd.structs import Settings
from smd.zip import read_lua_from_zip

logger = logging.getLogger(__name__)


def get_oureverday(dest: Path, app_id: str):
    lua_contents = asyncio.run(
        get_request(
            f"https://raw.githubusercontent.com/SteamAutoCracks/ManifestHub/refs/heads/{app_id}/{app_id}.lua"
        )
    )
    if lua_contents is None:
        return
    lua_path = dest / f"{app_id}.lua"
    with lua_path.open("w", encoding="utf-8") as f:
        f.write(lua_contents)
    return lua_path


def get_morrenus(dest: Path, app_id: str) -> Optional[Path]:
    url = f"https://manifest.morrenus.xyz/api/v1/manifest/{app_id}"

    if (morrenus_key := get_setting(Settings.MORRENUS_KEY)) is None:
        morrenus_key = prompt_secret(
            "Paste your morrenus API key here: ",
            lambda x: x.startswith("smm"),
            "That's not a morrenus key!",
            long_instruction=(
                "Go the morrenus website and request an API key. It's free."
            ),
        ).strip()
        set_setting(Settings.MORRENUS_KEY, morrenus_key)

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
            + f"Daily limit exceeded! You used {usage}/{limit}"
            + Style.RESET_ALL
        )
    else:
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
                    + f"Morrenus Daily Limit: {usage}/{limit}"
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
