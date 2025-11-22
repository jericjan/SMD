import asyncio
import logging
import time
from pathlib import Path
from typing import Any, cast
from urllib.parse import urljoin

import gevent
from colorama import Fore, Style
from steam.client import SteamClient  # type: ignore
from steam.client.cdn import CDNClient, ContentServer  # type: ignore

from smd.http_utils import get_gmrc, get_request_raw
from smd.manifest.crypto import decrypt_manifest
from smd.manifest.strategies import (
    DirectManifestStrategy,
    IManifestStrategy,
    InnerDepotManifestStrategy,
    ManifestContext,
    ManifestResolver,
    ManualManifestStrategy,
    SharedDepotManifestStrategy,
)
from smd.prompts import prompt_select
from smd.steam_client import SteamInfoProvider, get_product_info
from smd.structs import (  # type: ignore
    DepotManifestMap,
    LuaParsedInfo,
    ManifestGetModes,
)

logger = logging.getLogger(__name__)


class ManifestDownloader:
    def __init__(self, client: SteamClient, steam_path: Path):
        self.client = client
        self.steam_path = steam_path
        self.provider = SteamInfoProvider(client)

    def get_dlc_manifest_status(self, depot_ids: list[int]):
        # A dict of Depot IDs mapped to Manifest IDs
        manifest_ids: dict[int, bool] = {}

        while True:
            app_info = get_product_info(self.client, depot_ids)  # type: ignore
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
        self, lua: LuaParsedInfo, auto: bool = False
    ) -> DepotManifestMap:
        """Returns a dict of depot IDs mapped to manifest IDs"""
        # A dict of Depot IDs mapped to Manifest IDs
        manifest_ids: dict[str, str] = {}
        app_id = int(lua.app_id)
        if not auto:
            mode = prompt_select(
                "How would you like to obtain the manifest ID?",
                list(ManifestGetModes),
            )
            auto_fetch = mode == ManifestGetModes.AUTO
        else:
            auto_fetch = True

        main_app_data = {}
        if auto_fetch:
            main_app_data = self.provider.get_single_app_info(app_id)

        context = ManifestContext(
            app_id=app_id, app_data=main_app_data, provider=self.provider
        )

        strats: list[IManifestStrategy] = []

        if auto_fetch:
            strats.append(DirectManifestStrategy())
            strats.append(SharedDepotManifestStrategy())
            strats.append(InnerDepotManifestStrategy())
        strats.append(ManualManifestStrategy())

        resolver = ManifestResolver(strats)

        for pair in lua.depots:
            depot_id = str(pair.depot_id)

            if not pair.decryption_key:
                logger.debug(f"Skipping {depot_id} because it has no decryption key")
                continue

            manifest, strat = resolver.resolve(context, depot_id)
            print(f"Depot {depot_id} has manifest {manifest} ({strat})")
            manifest_ids[depot_id] = manifest

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
