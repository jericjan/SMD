"""Miscellaneous stuff used across various files"""

import logging
import sys
from pathlib import Path
from typing import Any, Optional, Union

import vdf  # type: ignore

logger = logging.getLogger(__name__)


def root_folder(outside_internal: bool = False):
    """Returns the executable's root folder"""
    # Go up one more level cuz we in `smd` subfolder
    root = Path(__file__).resolve().parent.parent
    is_frozen = getattr(sys, "frozen", False)
    if outside_internal and is_frozen:
        return root.parent
    return root


def enter_path(
    obj: Union[vdf.VDFDict, dict[Any, Any]],
    *paths: Union[int, str],
    mutate: bool = False,
    ignore_case: bool = False,
    default: Optional[Any] = None,
) -> Any:
    """
    Walks or creates nested dicts in a VDFDict/dict.
    Returns an empty dict-like if not found.
    `default` key only works when `mutate` is False.
    """
    current = obj
    for key in paths:
        if isinstance(key, int):
            try:
                current = current[key]  # pyright: ignore[reportUnknownVariableType]
            except IndexError:
                return type(current)()
            continue
        # try normal case, then lower if ignore_case is True
        original_key = key
        if ignore_case:
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
                return default if default else type(current)()
            # create a new key that's the same type as current
            new_node = type(current)()
            current[original_key] = new_node
            current = new_node

    return current  # pyright: ignore[reportUnknownVariableType]
