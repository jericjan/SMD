from collections import OrderedDict
from enum import Enum
from pathlib import Path
from types import TracebackType
from typing import Any, Callable, Optional, TypeVar, Union, cast, overload

import msgpack  # type: ignore
import vdf  # type: ignore
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from InquirerPy.utils import InquirerPyValidate

from crypto import keyring_decrypt, keyring_encrypt
from structs import Settings

_DictType = TypeVar("_DictType", bound=dict[Any, Any])


def prompt_select(
    msg: str,
    choices: list[Any],
    default: Optional[Any] = None,
    fuzzy: bool = False,
    **kwargs: Any,
):
    new_choices: list[Choice] = []
    for c in choices:
        if isinstance(c, Enum):
            new_choices.append(Choice(value=c, name=c.value))
        elif isinstance(c, Choice):
            new_choices.append(c)
        elif isinstance(c, tuple):
            if len(c) == 2:  # type: ignore
                new_choices.append(Choice(value=c[1], name=c[0]))  # type: ignore
        else:
            new_choices.append(Choice(value=c, name=str(c)))
    cmd = inquirer.fuzzy if fuzzy else inquirer.select  # type: ignore
    return cmd(message=msg, choices=new_choices, default=default, **kwargs).execute()


def convert_to_path(x: str):
    return Path(x.strip("\"' "))


def prompt_dir(msg: str) -> Path:
    is_dir: Callable[[str], bool] = (
        lambda x: convert_to_path(x).exists() and convert_to_path(x).is_dir()
    )
    return prompt_text(
        msg,
        validator=is_dir,
        invalid_msg="Doesn't exist or not a folder.",
        filter=convert_to_path,
    )


def prompt_file(msg: str, allow_blank: bool = False) -> Path:
    is_file: Callable[[str], bool] = lambda x: (
        convert_to_path(x).exists() and convert_to_path(x).is_file()
    ) or (True if allow_blank and x == "" else False)
    return prompt_text(
        msg,
        validator=is_file,
        invalid_msg="Doesn't exist or not a file.",
        filter=convert_to_path,
    )


def prompt_text(
    msg: str,
    validator: Optional[InquirerPyValidate] = None,
    invalid_msg: str = "Invalid input",
    instruction: str = "",
    long_instruction: str = "",
    filter: Optional[Callable[[str], Any]] = None,
):
    return inquirer.text(
        msg,
        validate=validator,
        invalid_message=invalid_msg,
        instruction=instruction,
        long_instruction=long_instruction,
        filter=filter,
    ).execute()


def prompt_secret(
    msg: str,
    validator: Optional[InquirerPyValidate] = None,
    invalid_msg: str = "Invalid input",
    instruction: str = "",
    long_instruction: str = "",
):
    return inquirer.secret(
        message=msg,
        transformer=lambda _: "[hidden]",
        validate=validator,
        invalid_message=invalid_msg,
        instruction=instruction,
        long_instruction=long_instruction,
    ).execute()


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


SETTINGS_FILE = Path.cwd() / "settings.bin"


def load_settings() -> dict[Any, Any]:
    """Returns all saved settings as a dict"""
    SETTINGS_FILE.touch(exist_ok=True)
    with SETTINGS_FILE.open("rb") as f:
        try:
            settings = cast("dict[Any, Any]", msgpack.unpackb(f.read()))  # type: ignore
        except ValueError:
            settings: dict[Any, Any] = {}
    return settings


def get_setting(key: Settings):
    value = load_settings().get(key.key_name)
    return keyring_decrypt(value) if (value and key.hidden) else value


def set_setting(key: Settings, value: str):
    settings = load_settings()
    settings[key.key_name] = keyring_encrypt(value) if key.hidden else value
    with SETTINGS_FILE.open("wb") as f:
        f.write(msgpack.packb(settings))  # type: ignore


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
