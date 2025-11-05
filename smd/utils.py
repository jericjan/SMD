"""Miscellaneous stuff used across various files"""

import logging
from pathlib import Path
from typing import Any, Union

import vdf  # type: ignore

logger = logging.getLogger(__name__)


def root_folder():
    """Returns the executable's root folder"""
    # Go up one more level cuz we in `smd` subfolder
    return Path(__file__).resolve().parent.parent


def enter_path(
    obj: Union[vdf.VDFDict, dict[Any, Any]],
    *paths: Union[int, str],
    mutate: bool = False,
    ignore_case: bool = False,
) -> Any:
    """
    Walks or creates nested dicts in a VDFDict/dict
    """
    current = obj
    for key in paths:
        # try normal case, then lower if ignore_case is True
        original_key = key
        if isinstance(key, str) and ignore_case:
            key = key.lower()

        key_map = {}
        for x in current:  # pyright: ignore[reportUnknownVariableType]
            if ignore_case and isinstance(x, str):
                key_map[x.lower()] = x
            else:
                key_map[x] = x

        if key in key_map:
            current = current[  # pyright: ignore[reportUnknownVariableType]
                key_map[key]
            ]
        else:
            # key not found
            if not mutate:
                return type(current)()
            # create a new key that's the same type as current
            new_node = type(current)()
            current[original_key] = new_node
            current = new_node

    return current  # pyright: ignore[reportUnknownVariableType]
