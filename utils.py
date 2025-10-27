from enum import Enum
from pathlib import Path
from typing import Any, Optional, Union, cast

import msgpack  # type: ignore
import vdf  # type: ignore
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from InquirerPy.utils import InquirerPyValidate

from crypto import keyring_decrypt, keyring_encrypt


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


def prompt_text(msg: str, long_instruction: str = ""):
    return inquirer.text(msg, long_instruction=long_instruction).execute().strip()


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


def _load_settings() -> dict[Any, Any]:
    SETTINGS_FILE.touch(exist_ok=True)
    with SETTINGS_FILE.open("rb") as f:
        try:
            settings = cast("dict[Any, Any]", msgpack.unpackb(f.read()))  # type: ignore
        except ValueError:
            settings: dict[Any, Any] = {}
    return settings


def get_setting(key: str, crypt: bool = False):
    value = _load_settings().get(key)
    return keyring_decrypt(value) if (value and crypt) else value


def set_setting(key: str, value: str, crypt: bool = False):
    settings = _load_settings()
    settings[key] = keyring_encrypt(value) if crypt else value
    with SETTINGS_FILE.open("wb") as f:
        f.write(msgpack.packb(settings))  # type: ignore
