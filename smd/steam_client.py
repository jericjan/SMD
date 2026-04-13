from dataclasses import dataclass
import json
import time
from typing import Any, ClassVar, Optional, Union

import gevent
from steam.client import SteamClient  # type: ignore

from smd.structs import DLCTypes, ProductInfo  # type: ignore
import logging

from smd.utils import enter_path

logger = logging.getLogger(__name__)


def get_product_info(provider: "SteamInfoProvider", app_ids: list[int]) -> ProductInfo:
    """Here for backwards compatibility"""
    return ProductInfo({"apps": provider.get_app_info(app_ids), "packages": {}})


def _get_product_info(client: SteamClient, app_ids: list[int]) -> ProductInfo:
    if len(app_ids) == 0:
        raise ValueError("app_ids cannot be empty.")
    if not client.logged_on:
        print("Logging in anonymously...", end="", flush=True)
        client.anonymous_login()
        print(" Done!")
    while True:
        try:
            print("Getting app info...")
            logger.debug(f"Getting info for {', '.join([str(x) for x in app_ids])}")
            start = time.time()
            info = client.get_product_info(  # pyright: ignore[reportUnknownMemberType]
                app_ids
            )
            # only none when app_ids is empty, which never happens
            assert info is not None
            logger.debug(f"Product info request took: {time.time() - start}s")
        except gevent.Timeout:
            print("Request timed out. Trying again")
            try:
                client.anonymous_login()  # might fix the endless timeout loop
            except RuntimeError:  # Alr logged in error
                pass
            continue
        break
    logger.debug(f"get_product_info retured: {json.dumps(info)}")
    return ProductInfo(info)


@dataclass
class SteamInfoProvider:
    """Wrapper for SteamClient to handle API calls and caching.
    Meant to be initialized at any point in code since
    ClassVars will keep share the same data"""

    _client: ClassVar[Optional[SteamClient]] = None
    _cache: ClassVar[dict[int, Any]] = {}
    """A cache of app IDs and their data taken
    from the `apps` key of `get_product_info`.
    Values are False if it's not a base app ID"""

    @property
    def client(self) -> SteamClient:
        client = type(self)._client
        if client is None:
            start_time = time.time()
            client = SteamClient()
            logger.debug(f"Steam client init in {time.time() - start_time}s")
            type(self)._client = client
        return client

    def get_app_info(self, app_ids: list[int]) -> dict[int, Any]:
        missing = [app_id for app_id in app_ids if app_id not in self._cache]
        if missing:
            info = _get_product_info(self.client, missing)
            apps: dict[int, Any] = info.get("apps", {})
            valid_ids = set(apps.keys())
            invalid_ids = set(missing) - valid_ids
            self._cache.update({**apps, **{x: False for x in invalid_ids}})
        else:
            print("Reading app info from cache...")

        return {
            app_id: self._cache.get(app_id, {})
            for app_id in app_ids
            if self._cache.get(app_id, {})
        }

    def get_single_app_info(self, app_id: int) -> dict[str, Any]:
        result = self.get_app_info([app_id])
        return result.get(app_id, {})

    def expand_dlc(self, app_data: dict[str, Any]):
        """
        Given data from get_single_app_info, expand all DLC info using `listofdlc` key.
        """
        extended = app_data.get("extended", {})
        dlc_list_str = extended.get("listofdlc", "")
        if dlc_list_str:
            dlc_ids = [int(x) for x in dlc_list_str.split(",")]
            dlc_data = self.get_app_info(dlc_ids)
        else:
            dlc_data = {}
        return dlc_data


class ParsedDLC:
    def __init__(
        self,
        depot_id: int,
        dlc_data: dict[str, Any],
        parent_data: dict[str, Any],
        local_ids: list[int],
    ):
        self.id = depot_id
        self.name: str = enter_path(dlc_data, "common", "name")
        depots = enter_path(dlc_data, "depots")
        parent_depots: dict[str, Union[dict[str, Any], str]] = enter_path(
            parent_data, "depots"
        )

        parent_depots_resolved = [
            (x.get("dlcappid") if isinstance(x, dict) else None)
            for x in parent_depots.values()
        ]
        self.release_state = enter_path(dlc_data, "common", "releasestate")
        self.type = (
            (
                DLCTypes.DEPOT
                if depots or str(depot_id) in parent_depots_resolved
                else DLCTypes.NOT_DEPOT
            )
            if self.release_state == "released"
            else DLCTypes.UNRELEASED
        )
        self.in_applist = True if depot_id in local_ids else False