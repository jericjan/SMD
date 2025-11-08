from pathlib import Path
import subprocess
from typing import Union

from smd.utils import root_folder


def run_fzf(choices: Union[list[str], Path]):
    if isinstance(choices, list):
        choices_str = '\n'.join(choices)
    else:
        with choices.open(encoding="utf-8") as f:
            choices_str = f.read()
    proc = subprocess.run(
        [root_folder() / "third_party/fzf/fzf.exe"],
        input=choices_str,
        capture_output=True,
        encoding="utf-8",
    )
    return proc.stdout.strip("\n")
