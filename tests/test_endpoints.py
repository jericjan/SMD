import logging
from pathlib import Path

from smd.lua.endpoints import get_oureverday

logger = logging.getLogger("smd")
logger.setLevel(logging.DEBUG)

fh = logging.FileHandler("debug.log")
fh.setFormatter(
    logging.Formatter(
        "%(asctime)s::%(name)s::%(levelname)s::%(message)s",
        datefmt="%m/%d/%Y %I:%M:%S %p",
    )
)
logger.addHandler(fh)


def test_oureveryday():
    get_oureverday(Path().cwd() / "saved_lua", "1091500")
