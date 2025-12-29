import asyncio
import logging
import shutil
from pathlib import Path
from typing import Any, Optional, cast
from urllib.parse import urljoin

import gevent
from colorama import Fore, Style
from steam.client.cdn import CDNClient, ContentServer  # type: ignore

from smd.http_utils import get_gmrc, get_request_raw
from smd.manifest.crypto import decrypt_and_save_manifest
from smd.manifest.id_resolver import (
    IManifestStrategy,
    InnerDepotManifestStrategy,
    ManifestContext,
    ManifestIDResolver,
    ManualManifestStrategy,
    SharedDepotManifestStrategy,
    StandardManifestStrategy,
)
from smd.prompts import prompt_confirm, prompt_select, prompt_text
from smd.steam_client import SteamInfoProvider, get_product_info
from smd.structs import (  # type: ignore
    DepotManifestMap,
    LuaParsedInfo,
    ManifestGetModes,
)
from smd.zip import read_nth_file_from_zip_bytes

logger = logging.getLogger(__name__)


class ManifestDownloader:
    def __init__(self, provider: SteamInfoProvider, steam_path: Path):
        self.steam_path = steam_path
        self.provider = provider

    def get_dlc_manifest_status(self, depot_ids: list[int]):
        # A dict of Depot IDs mapped to Manifest IDs
        manifest_ids: dict[int, bool] = {}

        while True:
            app_info = get_product_info(self.provider, depot_ids)  # type: ignore
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
            app_id=app_id,
            app_data=main_app_data,
            provider=self.provider,
            auto=auto_fetch,
        )

        strats: list[IManifestStrategy] = []

        if auto_fetch:
            strats.append(StandardManifestStrategy())
            strats.append(SharedDepotManifestStrategy())
            strats.append(InnerDepotManifestStrategy())
        strats.append(ManualManifestStrategy())

        resolver = ManifestIDResolver(strats)

        for pair in lua.depots:
            depot_id = str(pair.depot_id)

            if not pair.decryption_key:
                logger.debug(f"Skipping {depot_id} because it has no decryption key")
                continue

            manifest, strat = resolver.resolve(context, depot_id)
            if manifest == "":
                # Skip, probably because lua file had a base app ID
                # that also had a decryption key
                continue
            print(f"Depot {depot_id} has manifest {manifest} ({strat})")
            manifest_ids[depot_id] = manifest

        return DepotManifestMap(manifest_ids)

    def get_cdn_client(self):
        while True:
            try:
                cdn = CDNClient(self.provider.client)
                break
            except gevent.Timeout:
                print("CDN Client timed out. Trying again.")
        return cdn

    def download_single_manifest(
        self, depot_id: str, manifest_id: str, cdn_client: Optional[CDNClient] = None
    ):
        """Returns an encrypted manifest file as bytes"""
        if cdn_client is None:
            cdn_client = self.get_cdn_client()
        req_code = self.resolve_gmrc(manifest_id)
        cdn_server = cast(ContentServer, cdn_client.get_content_server())
        cdn_server_name = f"http{'s' if cdn_server.https else ''}://{cdn_server.host}"
        manifest_url = urljoin(
            cdn_server_name, f"depot/{depot_id}/manifest/{manifest_id}/5/{req_code}"
        )

        logger.debug(f"Download manifest from {manifest_url}")
        return get_request_raw(manifest_url)

    def resolve_gmrc(self, manifest_id: str):
        while True:
            req_code = asyncio.run(get_gmrc(manifest_id))
            if req_code is not None:
                print(f"Request code is: {req_code}")
                break
            if prompt_confirm(
                "Request code endpoint died. Would you like to try again?",
                false_msg="No (Manually input request code)",
            ):
                continue

            req_code = prompt_text(
                "Paste the Manifest Request Code here:",
                validator=lambda x: x.isdigit(),
            )
            break
        return req_code

    def download_workshop_item(self, app_id: str, ugc_id: str):
        manifest = self.download_single_manifest(app_id, ugc_id)
        if manifest:
            extracted = read_nth_file_from_zip_bytes(0, manifest)
            if not extracted:
                raise Exception("File isn't a ZIP. This shouldn't happen.")
            depotcache = self.steam_path / "depotcache"
            depotcache.mkdir(exist_ok=True)
            final_manifest_loc = (
                depotcache / f"{app_id}_{ugc_id}.manifest"
            )
            with final_manifest_loc.open("wb") as f:
                f.write(extracted.read())

    def download_manifests(
        self, lua: LuaParsedInfo, decrypt: bool = False, auto_manifest: bool = False
    ):
        """Gets latest manifest IDs and downloads respective manifests"""
        cdn = self.get_cdn_client()
        manifest_ids = self.get_manifest_ids(lua, auto_manifest)

        manifest_paths: list[Path] = []
        # Download and decrypt manifests
        for pair in lua.depots:
            depot_id = pair.depot_id
            dec_key = pair.decryption_key
            if dec_key == "":
                logger.debug(f"Skipping {depot_id} because it's not a depot")
                continue
            manifest_id = manifest_ids.get(depot_id)
            if manifest_id is None:
                continue
            print(
                Fore.CYAN
                + f"\nDepot {depot_id} - Manifest {manifest_id}"
                + Style.RESET_ALL
            )

            possible_saved_manifest = (
                Path.cwd() / f"manifests/{depot_id}_{manifest_id}.manifest"
            )
            depotcache = self.steam_path / "depotcache"
            depotcache.mkdir(exist_ok=True)
            final_manifest_loc = (
                depotcache / f"{depot_id}_{manifest_id}.manifest"
            )

            if possible_saved_manifest.exists():
                print("One of the endpoints had a manifest. Skipping download...")
                if not final_manifest_loc.exists():
                    shutil.move(possible_saved_manifest, final_manifest_loc)
                continue
            manifest = self.download_single_manifest(depot_id, manifest_id, cdn)

            if manifest:
                if decrypt:
                    decrypt_and_save_manifest(manifest, final_manifest_loc, dec_key)
                else:
                    extracted = read_nth_file_from_zip_bytes(0, manifest)
                    if not extracted:
                        raise Exception("File isn't a ZIP. This shouldn't happen.")
                    with final_manifest_loc.open("wb") as f:
                        f.write(extracted.read())

                manifest_paths.append(final_manifest_loc)
        return manifest_paths
