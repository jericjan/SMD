import gc
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Any

from InquirerPy import inquirer
from InquirerPy.base import BaseComplexPrompt, BaseListPrompt
from InquirerPy.base.control import Choice
from InquirerPy.prompts.input import InputPrompt
from InquirerPy.utils import InquirerPyValidate


def convert_to_path(x: str):
    return Path(x.strip("\"' "))


def _clean_prompt(prompt: BaseComplexPrompt | InputPrompt):
    """Dark voodoo I cooked that actually works??? `prompt_select` leaks way less now"""
    if isinstance(prompt, BaseComplexPrompt):
        prompt.application.reset()  # pyright: ignore[reportUnknownMemberType]
        prompt.application = None  # type: ignore
    if isinstance(prompt, BaseListPrompt):
        prompt.content_control.reset()
        prompt.content_control = None  # type: ignore
    del prompt
    gc.collect()


def prompt_select(
    msg: str,
    choices: list[Any],
    default: Any | None = None,
    fuzzy: bool = False,
    cancellable: bool = False,
    exclude: list[Any] | None = None,
    **kwargs: Any,
) -> Any:
    """Prompts the user for a item select menu

    Args:
        msg (str): The message
        choices (list[Any]): Choices to pick from. Can be:
            - Enum -> Name = Enum.value, Value = Enum
            - Choice
            - tuple of size 2 (e.g. `('Name', 'Value')`)
            - Any object with a `__str__` method -> Value = object
        default (Any | None, optional): The default choice to highlight first. Defaults to None.
        fuzzy (bool, optional): Enable fuzzy searching of items. Defaults to False.
        cancellable (bool, optional): Adds a [Back] button if True. Defaults to False.
        exclude (list[Any] | None, optional): Exclude item from showing up if it's an Enum and is in this list. Defaults to None.

    Returns:
        Any: Type returned is the value in the respective selected Choice
    """
    new_choices: list[Choice] = []
    for c in choices:
        if isinstance(c, Enum):
            if exclude and c in exclude:
                # Skip excluded choice
                continue
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
    obj = cmd(
        message=msg,
        choices=new_choices,
        default=default,
        vi_mode=not fuzzy,
        **kwargs,
    )
    result = obj.execute()
    _clean_prompt(obj)
    return result


def prompt_dir(
    msg: str,
    custom_check: Callable[[Path], bool] | None = None,
    custom_msg: str | None = None,
) -> Path:
    def validator(raw_input: str) -> bool:
        path = convert_to_path(raw_input)

        if not (path.exists() and path.is_dir()):
            return False
        return (not custom_check) or custom_check(path)
    return prompt_text(
        msg,
        validator=validator,
        invalid_msg=custom_msg if custom_msg else "Doesn't exist or not a folder.",
        filter=convert_to_path,
    )


def prompt_file(msg: str, allow_blank: bool = False) -> Path:
    is_file: Callable[[str], bool] = lambda x: (
        convert_to_path(x).exists() and convert_to_path(x).is_file()
    ) or (bool(allow_blank and x == ""))
    return prompt_text(
        msg,
        validator=is_file,
        invalid_msg="Doesn't exist or not a file.",
        filter=convert_to_path,
    )


def prompt_text(
    msg: str,
    validator: InquirerPyValidate | None = None,
    invalid_msg: str = "Invalid input",
    instruction: str = "",
    long_instruction: str = "",
    filter: Callable[[str], Any] | None = None,
):
    obj = inquirer.text(
        msg,
        validate=validator,
        invalid_message=invalid_msg,
        instruction=instruction,
        long_instruction=long_instruction,
        filter=filter,
    )
    res = obj.execute()
    _clean_prompt(obj)
    return res


def prompt_secret(
    msg: str,
    validator: InquirerPyValidate | None = None,
    invalid_msg: str = "Invalid input",
    instruction: str = "",
    long_instruction: str = "",
):
    obj = inquirer.secret(
        message=msg,
        transformer=lambda _: "[hidden]",
        validate=validator,
        invalid_message=invalid_msg,
        instruction=instruction,
        long_instruction=long_instruction,
    )
    res = obj.execute()
    _clean_prompt(obj)
    return res


def prompt_confirm(
    msg: str,
    true_msg: str | None = None,
    false_msg: str | None = None,
    default: bool = True,
) -> bool:
    # inquirer.confirm exists but I prefer this
    return prompt_select(
        msg,
        [
            (true_msg if true_msg else "Yes", True),
            (false_msg if false_msg else "No", False),
        ],
        default=default
    )
