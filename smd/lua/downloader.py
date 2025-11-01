"""API endpoints are in here"""

import asyncio
import io
import json
import re
import zipfile
from pathlib import Path
from tempfile import TemporaryFile

import httpx
from colorama import Fore, Style

from smd.http_utils import get_request
from smd.prompts import prompt_secret, prompt_select, prompt_text
from smd.storage.settings import get_setting, set_setting
from smd.structs import LuaChoice, LuaEndpoint, LuaResult, Settings


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
    chunk_size = (1024**2) // 2  # 0.5 MiB

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

    with httpx.stream("GET", url, headers=headers) as response:
        try:
            total = int(response.headers.get("Content-Length", "0"))
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
    lua_bytes = b""
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
            print("Did not receive a ZIP file or JSON: \n" + f.read().decode())

    lua_path = dest / f"{app_id}.lua"
    if len(lua_bytes) > 0:
        with lua_path.open("wb") as f:
            f.write(lua_bytes)
        return lua_path


def download_lua(dest: Path) -> LuaResult:
    """Downloads a lua file from the available endpoints"""

    reg = re.compile(r"(?<=store\.steampowered\.com\/app\/)\d+|\d+")

    def validate_app_id(x: str) -> bool:
        return bool(reg.search(x))

    def filter_app_id(x: str) -> str:
        match = reg.search(x)
        assert match is not None  # lmao
        return match.group()

    source: LuaEndpoint = prompt_select("Select an endpoint:", list(LuaEndpoint))

    app_id = prompt_text(
        "Enter the App ID or Store link:",
        validator=validate_app_id,
        invalid_msg="Not a valid format.",
        filter=filter_app_id,
    )

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
