import logging
from collections import OrderedDict
from pathlib import Path
from types import TracebackType
from typing import Any, overload

import vdf  # type: ignore

logger = logging.getLogger(__name__)


def vdf_dump(vdf_file: Path, obj: dict[str, Any]):
    with vdf_file.open("w", encoding="utf-8") as f:
        vdf.dump(obj, f, pretty=True)  # type: ignore


@overload
def vdf_load(
    vdf_file: Path, mapper: type[OrderedDict[Any, Any]]
) -> OrderedDict[Any, Any]: ...


@overload
def vdf_load[DictType: dict[Any, Any]](
    vdf_file: Path, mapper: type[DictType]
) -> DictType: ...


@overload
def vdf_load(vdf_file: Path) -> dict[Any, Any]: ...


def vdf_load[DictType: dict[Any, Any]](
    vdf_file: Path, mapper: type[DictType] = dict
) -> DictType:
    with vdf_file.open(encoding="utf-8") as f:
        data: DictType = vdf.load(f, mapper=mapper)  # type: ignore
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
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        exc_traceback: TracebackType | None,
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
    for idx, library in vdf_data["libraryfolders"].items():
        try:
            if (path := Path(library["path"])).exists():
                paths.append(path)
        except KeyError:
            logger.debug(f"Could not find path for library folder at index {idx}")
    return paths
