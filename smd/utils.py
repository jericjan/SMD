"""Miscellaneous stuff used across various files"""

from pathlib import Path
from typing import Any, Optional, Union

import vdf  # type: ignore
from steam.client import SteamClient  # type: ignore

from smd.structs import ProductInfo  # type: ignore


def root_folder():
    """Returns the executable's root folder"""
    return Path(__file__).resolve().parent


def enter_path(
    obj: Union[vdf.VDFDict, dict[Any, Any]],
    *paths: Union[int, str],
    mutate: bool = False,
) -> Any:
    """
    Walks or creates nested dicts in a VDFDict/dict
    """
    current = obj
    for key in paths:
        if mutate:
            current = current.setdefault(key, {})  # type: ignore
        else:
            current = current.get(key, {})  # type: ignore
    return current  # type: ignore


def get_product_info(client: SteamClient, app_ids: list[int]) -> Optional[ProductInfo]:
    if not client.logged_on:
        print("Logging in anonymously...")
        client.anonymous_login()
    info = client.get_product_info(app_ids)  # pyright: ignore[reportUnknownMemberType]
    if info:
        return ProductInfo(info)
    return None
