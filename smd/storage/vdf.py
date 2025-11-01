from collections import OrderedDict
from pathlib import Path
from types import TracebackType
from typing import Any, Optional, TypeVar, overload

import vdf  # type: ignore

from smd.structs import DepotKeyPair
from smd.utils import enter_path

_DictType = TypeVar("_DictType", bound=dict[Any, Any])


def vdf_dump(vdf_file: Path, obj: dict[str, Any]):
    with vdf_file.open("w", encoding="utf-8") as f:
        vdf.dump(obj, f, pretty=True)  # type: ignore


@overload
def vdf_load(
    vdf_file: Path, mapper: type[OrderedDict[Any, Any]]
) -> OrderedDict[Any, Any]: ...


@overload
def vdf_load(vdf_file: Path, mapper: type[_DictType]) -> _DictType: ...


@overload
def vdf_load(vdf_file: Path) -> dict[Any, Any]: ...


def vdf_load(vdf_file: Path, mapper: type[_DictType] = dict) -> _DictType:
    with vdf_file.open(encoding="utf-8") as f:
        data: _DictType = vdf.load(f, mapper=mapper)  # type: ignore
    return data


class VDFLoadAndDumper:
    """For when you need to load and dump a vdf file in one line.
    Use `vdf_load` or `vdf_dump` to do just one of the two"""

    def __init__(self, path: Path):
        self.path = path
        self.data = vdf.VDFDict()

    def __enter__(self):
        self.data = vdf_load(self.path, mapper=vdf.VDFDict)
        return self.data

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        exc_traceback: Optional[TracebackType],
    ):
        if exc_type is None:
            vdf_dump(self.path, self.data)


def get_steam_libs(steam_path: Path):
    """Get list of Steam library paths by the user

    Args:
        steam_path (Path): Steam install path

    Returns:
        list[Path]: list of Steam library paths
    """
    lib_folders = steam_path / "config/libraryfolders.vdf"

    vdf_data = vdf_load(lib_folders)
    paths: list[Path] = []
    for library in vdf_data["libraryfolders"].values():
        if (path := Path(library["path"])).exists():
            paths.append(path)

    return paths


def add_decryption_key_to_config(vdf_file: Path, depot_dec_key: list[DepotKeyPair]):
    """Adds decryption keys to config.vdf"""
    with VDFLoadAndDumper(vdf_file) as vdf_data:
        for depot_id, dec_key in depot_dec_key:
            print(f"Depot {depot_id} has decryption key {dec_key}...", end="")
            depots = enter_path(
                vdf_data,
                "InstallConfigStore",
                "Software",
                "Valve",
                "Steam",
                "depots",
                mutate=True,
            )
            if depot_id not in depots:
                depots[depot_id] = {"DecryptionKey": dec_key}
                print("Added to config.vdf succesfully.")
            else:
                print("Already in config.vdf.")
