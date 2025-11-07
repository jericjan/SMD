import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import urljoin

from colorama import Fore, Style
from steam.client import SteamClient  # type: ignore
from steam.client.cdn import CDNClient, ContentServer  # type: ignore

from smd.http_utils import get_gmrc, get_product_info, get_request_raw
from smd.manifest.crypto import decrypt_manifest
from smd.prompts import prompt_select, prompt_text
from smd.structs import DepotManifestMap, LuaParsedInfo  # type: ignore

logger = logging.getLogger(__name__)


class ManifestDownloader:
    def __init__(self, client: SteamClient, steam_path: Path):
        self.client = client
        self.steam_path = steam_path

    def get_manifest_ids(self, lua: LuaParsedInfo) -> DepotManifestMap:
        # A dict of Depot IDs mapped to Manifest IDs
        manifest_ids: dict[str, str] = {}

        # Get manifest IDs. The official API doesn't return these,
        # so using steam module instead
        while True:
            manifest_mode: Literal["Auto", "Manual"] = prompt_select(
                "How would you like to obtain the manifest ID?", ["Auto", "Manual"]
            )
            app_info = (
                get_product_info(self.client, [int(lua.app_id)])  # type: ignore
                if manifest_mode == "Auto"
                else None
            )
            depots_dict: dict[str, Any] = (
                app_info.get("apps", {}).get(int(lua.app_id), {}).get("depots", {})
                if app_info
                else {}
            )

            for pair in lua.depots:
                depot_id = pair.depot_id
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
        """Gets latest manifest IDs and downloads respective manifests"""
        cdn = CDNClient(self.client)
        manifest_ids = self.get_manifest_ids(lua)

        # Download and decrypt manifests
        for pair in lua.depots:
            depot_id = pair.depot_id
            dec_key = pair.decryption_key
            manifest_id = manifest_ids[depot_id]
            print(
                Fore.CYAN
                + f"\nDepot {depot_id} - Manifest {manifest_id}"
                + Style.RESET_ALL
            )

            while True:
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

            logger.debug(f"Download manifest from {manifest_url}")
            manifest = get_request_raw(manifest_url)

            if manifest:
                output_file = (
                    self.steam_path / f"depotcache/{depot_id}_{manifest_id}.manifest"
                )
                decrypt_manifest(manifest, output_file, dec_key)
