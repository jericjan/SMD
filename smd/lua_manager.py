import asyncio
import io
import re
import shutil
import time
import zipfile
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import urljoin

import httpx
from pathvalidate import sanitize_filename
from steam.client import SteamClient  # type: ignore
from steam.client.cdn import CDNClient, ContentServer  # type: ignore

from smd.applist import AppListManager
from smd.http_utils import get_game_name, get_gmrc
from smd.lua_downloader import download_lua
from smd.lua_selection import add_new_lua, select_from_saved_luas
from smd.manifest_crypto import decrypt_manifest
from smd.prompts import prompt_select, prompt_text
from smd.storage.named_ids import get_named_ids
from smd.storage.vdf import add_decryption_key_to_config, vdf_dump
from smd.structs import DepotManifestMap, LuaChoice, LuaParsedInfo  # type: ignore
from smd.utils import get_product_info


class LuaManager:
    def __init__(
        self,
        client: SteamClient,
        app_list_man: AppListManager,
        steam_path: Path,
    ):
        self.client = client
        self.saved_lua = Path().cwd() / "saved_lua"
        self.named_ids = get_named_ids(self.saved_lua)
        self.app_list_man = app_list_man
        self.steam_path = steam_path

    def get_lua_info(self, choice: LuaChoice) -> LuaParsedInfo:
        app_id_regex = re.compile(r"addappid\s*\(\s*(\d+)\s*\)")
        depot_dec_key_regex = re.compile(
            r"addappid\s*\(\s*(\d+)\s*,\s*\d\s*,\s*(?:\"|\')(\S+)(?:\"|\')\s*\)"
        )
        while True:
            while True:
                if choice == LuaChoice.SELECT_SAVED_LUA:
                    result = select_from_saved_luas(self.saved_lua, self.named_ids)
                elif choice == LuaChoice.ADD_LUA:
                    result = add_new_lua()
                elif choice == LuaChoice.AUTO_DOWNLOAD:
                    result = download_lua(self.saved_lua)

                if result.path is not None:
                    lua_path = result.path
                    if result.contents is not None:
                        lua_contents = result.contents
                    else:
                        lua_contents = result.path.read_text(encoding="utf-8")
                    break

                if result.switch_choice is not None:
                    choice = result.switch_choice

            if not (app_id_match := app_id_regex.search(lua_contents)):
                print("App ID not found. Try again.")
                continue

            app_id = app_id_match.group(1)
            print(f"App ID is {app_id}")
            self.app_list_man.add_id(int(app_id))

            if not (depot_dec_key := depot_dec_key_regex.findall(lua_contents)):
                print("Decryption keys not found. Try again.")
                continue

            for depot_id, _ in depot_dec_key:
                self.app_list_man.add_id(int(depot_id))

            vdf_file = self.steam_path / "config/config.vdf"
            shutil.copyfile(vdf_file, (self.steam_path / "config/config.vdf.backup"))
            add_decryption_key_to_config(vdf_file, depot_dec_key)

            break
        return LuaParsedInfo(app_id, depot_dec_key, lua_path, lua_contents)

    def backup_lua(self, lua: LuaParsedInfo):
        if lua.path.suffix == ".zip":
            with (self.saved_lua / f"{lua.id}.lua").open("w", encoding="utf-8") as f:
                f.write(lua.contents)
        elif not (self.saved_lua / lua.path.name).exists():
            shutil.copyfile(lua.path, self.saved_lua / lua.path.name)

    def get_manifest_ids(
        self, lua: LuaParsedInfo
    ) -> DepotManifestMap:
        # A dict of Depot IDs mapped to Manifest IDs
        manifest_ids: dict[str, str] = {}

        # Get manifest IDs. The official API doesn't return these,
        # so using steam module instead
        while True:
            manifest_mode: Literal["Auto", "Manual"] = prompt_select(
                "How would you like to obtain the manifest ID?", ["Auto", "Manual"]
            )
            app_info = (
                get_product_info(self.client, [int(lua.id)])  # type: ignore
                if manifest_mode == "Auto"
                else None
            )
            depots_dict: dict[str, Any] = (
                app_info.get("apps", {}).get(int(lua.id), {}).get("depots", {})
                if app_info
                else {}
            )

            for depot_id, _ in lua.depots:
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
        return DepotManifestMap(manifest_ids)

    def download_manifests(
        self,
        lua: LuaParsedInfo,
    ):
        cdn = CDNClient(self.client)
        manifest_ids = self.get_manifest_ids(lua)
        # Download and decrypt manifests
        for depot_id, dec_key in lua.depots:
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
            cdn_server_name = (
                f"http{'s' if cdn_server.https else ''}://{cdn_server.host}"
            )
            manifest_url = urljoin(
                cdn_server_name, f"depot/{depot_id}/manifest/{manifest_id}/5/{req_code}"
            )

            r = httpx.get(manifest_url, timeout=None)
            r.raise_for_status()

            with zipfile.ZipFile(io.BytesIO(r.content)) as f:
                encrypted = io.BytesIO(f.read("z"))

            output_file = (
                self.steam_path / f"depotcache/{depot_id}_{manifest_id}.manifest"
            )
            decrypt_manifest(encrypted, output_file, dec_key)
