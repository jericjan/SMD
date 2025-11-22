import json
import time
from typing import Any, Optional

import gevent
from steam.client import SteamClient  # type: ignore

from smd.structs import ProductInfo  # type: ignore
import logging

logger = logging.getLogger(__name__)


# TODO: remove all uses outside of SteamInfoProvider
def get_product_info(client: SteamClient, app_ids: list[int]) -> Optional[ProductInfo]:
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
            logger.debug(f"Product info request took: {time.time() - start}s")
        except gevent.Timeout:
            print("Request timed out. Trying again")
            try:
                client.anonymous_login()  # might fix the endless timeout loop
            except RuntimeError:  # Alr logged in error
                pass
            continue
        break
    if info:
        logger.debug(f"get_product_info retured: {json.dumps(info)}")
        return ProductInfo(info)
    return None


class SteamInfoProvider:
    """Wrapper for SteamClient to handle API calls and caching."""

    def __init__(self, client: SteamClient):
        self.client = client
        self._cache: dict[int, Any] = {}

    def get_app_info(self, app_ids: list[int]) -> dict[int, Any]:
        missing = [app_id for app_id in app_ids if app_id not in self._cache]
        if missing:
            info = get_product_info(self.client, missing)
            if info:
                self._cache.update(info.get("apps", {}))

        return {app_id: self._cache.get(app_id, {}) for app_id in app_ids}

    def get_single_app_info(self, app_id: int) -> dict[str, Any]:
        result = self.get_app_info([app_id])
        return result.get(app_id, {})
