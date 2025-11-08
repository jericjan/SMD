"""API endpoints are in here"""

import asyncio
import io
import json
import logging
from pathlib import Path

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


def get_manilua(dest: Path, app_id: str):
    url = f"https://www.piracybound.com/api/game/{app_id}"

    if (manilua_key := get_setting(Settings.MANILUA_KEY)) is None:
        manilua_key = prompt_secret(
            "Paste your manilua API key here: ",
            lambda x: x.startswith("manilua"),
            "That's not a manilua key!",
            long_instruction=(
                "Go the manilua website and request an API key. It's free."
            ),
        ).strip()
        set_setting(Settings.MANILUA_KEY, manilua_key)

    headers = {
        "Authorization": f"Bearer {manilua_key}",
    }

    logger.debug(f"Downloading lua files from {url}")
    lua_bytes = b''
    while True:
        with download_to_tempfile(url, headers) as tf:
            if tf is None:
                if prompt_confirm("Try again?"):
                    continue
                break

            data = tf.read()
            lua_bytes = read_lua_from_zip(io.BytesIO(data), decode=False)
            if lua_bytes is None:
                tf.seek(0)
                try:
                    print(
                        Fore.RED + json.dumps(json.load(tf), indent=2) + Style.RESET_ALL
                    )
                except json.JSONDecodeError:
                    print(
                        "Did not receive a ZIP file or JSON: \n" + tf.read().decode()
                    )
        break

    lua_path = dest / f"{app_id}.lua"
    if lua_bytes:
        with lua_path.open("wb") as f:
            f.write(lua_bytes)
        return lua_path
