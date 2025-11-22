import asyncio
import logging
import time
from pathlib import Path
from typing import Any, cast
from urllib.parse import urljoin

from colorama import Fore, Style
import gevent
from steam.client import SteamClient  # type: ignore
from steam.client.cdn import CDNClient, ContentServer  # type: ignore

from smd.http_utils import get_gmrc, get_product_info, get_request_raw
from smd.manifest.crypto import decrypt_manifest
from smd.prompts import prompt_select, prompt_text
from smd.structs import (  # type: ignore
    DepotKeyPair,
    DepotManifestMap,
    LuaParsedInfo,
    ManifestGetModes,
)

logger = logging.getLogger(__name__)


class ManifestDownloader:
    def __init__(self, client: SteamClient, steam_path: Path):
        self.client = client
        self.steam_path = steam_path

    def get_dlc_manifest_status(
        self, depot_ids: list[int]
    ):
        # A dict of Depot IDs mapped to Manifest IDs
        manifest_ids: dict[int, bool] = {}

        while True:
            app_info = (
                get_product_info(self.client, depot_ids)  # type: ignore
            )
            if app_info is None:
                continue
            for depot_id in depot_ids:
                depots_dict: dict[str, Any] = (
                    app_info.get("apps", {}).get(depot_id, {}).get("depots", {})
                )

                manifest = (
                    depots_dict.get(str(depot_id), {})
                    .get("manifests", {})
                    .get("public", {})
                    .get("gid")
                )
                if manifest is not None:
                    print(f"Depot {depot_id} has manifest {manifest}")
                manifest_file = (
                    self.steam_path / f"depotcache/{depot_id}_{manifest}.manifest"
                )
                manifest_ids[depot_id] = manifest_file.exists()
            break
        return manifest_ids

    def get_manifest_ids(
        self, lua: LuaParsedInfo, depth: int = 0, auto: bool = False
    ) -> DepotManifestMap:
        # A dict of Depot IDs mapped to Manifest IDs
        manifest_ids: dict[str, str] = {}

        # Get manifest IDs. The official API doesn't return these,
        # so using steam module instead
        while True:
            manifest_mode: ManifestGetModes = (
                prompt_select(
                    "How would you like to obtain the manifest ID?",
                    list(ManifestGetModes),
                )
                if not auto
                else ManifestGetModes.AUTO
            )
            app_info = (
                get_product_info(self.client, [int(lua.app_id)])  # type: ignore
                if manifest_mode == ManifestGetModes.AUTO
                else None
            )
            depots_dict: dict[str, Any] = (
                app_info.get("apps", {}).get(int(lua.app_id), {}).get("depots", {})
                if app_info
                else {}
            )

            for pair in lua.depots:
                depot_id = pair.depot_id
                if pair.decryption_key == "":
                    logger.debug(
                        f"Skipping {depot_id} because it has no decryption key"
                    )
                    continue
                manifest = (
                    depots_dict.get(str(depot_id), {})
                    .get("manifests", {})
                    .get("public", {})
                    .get("gid")
                )
                sub_manifest = None
                if manifest is None:
                    if manifest_mode == ManifestGetModes.AUTO:
                        if depth < 1:
                            sub = LuaParsedInfo(
                                lua.path, lua.contents, lua.app_id, lua.depots
                            )
                            sub.app_id = depot_id
                            # decryption key not needed
                            sub.depots = [DepotKeyPair(depot_id, "")]
                            print("This might be an inner depot...")
                            sub_manifest = self.get_manifest_ids(
                                sub, depth + 1, True
                            ).get(depot_id)
                        if sub_manifest is None:
                            print(
                                "API failed. "
                                "I need the latest manifest ID for this depot. "
                                "Blank if you want to try the request again."
                            )
                    if sub_manifest is None and not (
                        manifest := prompt_text(f"Depot {depot_id}: ")
                    ):
                        print("Blank entered. Let's try this again.")
                        break
                if manifest is not None:
                    print(f"Depot {depot_id} has manifest {manifest}")
                manifest = sub_manifest if sub_manifest else manifest
                manifest_ids[depot_id] = manifest
            else:
                break  # User did not give a blank, end the loop
        return DepotManifestMap(manifest_ids)

    def download_manifests(
        self,
        lua: LuaParsedInfo,
    ):
        """Gets latest manifest IDs and downloads respective manifests"""
        while True:
            try:
                cdn = CDNClient(self.client)
                break
            except gevent.Timeout:
                print("CDN Client timed out. Trying again.")
        manifest_ids = self.get_manifest_ids(lua)

        # Download and decrypt manifests
        for pair in lua.depots:
            depot_id = pair.depot_id
            dec_key = pair.decryption_key
            if dec_key == "":
                logger.debug(f"Skipping {depot_id} because it's not a depot")
                continue
            manifest_id = manifest_ids[depot_id]
            print(
                Fore.CYAN
                + f"\nDepot {depot_id} - Manifest {manifest_id}"
                + Style.RESET_ALL
            )

            possible_saved_manifest = (
                Path.cwd() / f"manifests/{depot_id}_{manifest_id}.manifest"
            )
            final_manifest_loc = (
                self.steam_path / f"depotcache/{depot_id}_{manifest_id}.manifest"
            )

            if possible_saved_manifest.exists():
                print("One of the endpoints had a manifest. Skipping download...")
                if not final_manifest_loc.exists():
                    possible_saved_manifest.rename(final_manifest_loc)
                continue
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
                decrypt_manifest(manifest, final_manifest_loc, dec_key)
