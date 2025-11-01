from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from InquirerPy.utils import InquirerPyValidate


def convert_to_path(x: str):
    return Path(x.strip("\"' "))


def prompt_select(
    msg: str,
    choices: list[Any],
    default: Optional[Any] = None,
    fuzzy: bool = False,
    cancellable: bool = False,
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
    if cancellable:
        new_choices.append(Choice(value=None, name="[Back]"))
    cmd = inquirer.fuzzy if fuzzy else inquirer.select  # type: ignore
    return cmd(message=msg, choices=new_choices, default=default, **kwargs).execute()


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
