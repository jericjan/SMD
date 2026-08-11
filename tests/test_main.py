import asyncio

from smd.http_utils import get_gmrc


def test_gmrc():
    a = asyncio.run(get_gmrc(4740032384826825263))
    assert a.isdecimal() if a else False
