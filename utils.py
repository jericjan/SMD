from enum import Enum
from pathlib import Path
from typing import Any, Optional, Union

import vdf  # type: ignore
from InquirerPy import inquirer
from InquirerPy.base.control import Choice


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
