import asyncio
import logging
from collections.abc import Generator
from contextlib import contextmanager
from tempfile import TemporaryFile
from typing import TYPE_CHECKING, Any, Literal, overload
from urllib.parse import urlparse

import httpx
from tqdm import tqdm  # type: ignore

from smd.prompts import prompt_confirm, prompt_text

if TYPE_CHECKING:
    from tempfile import _TemporaryFileWrapper  # pyright: ignore[reportPrivateUsage]

logger = logging.getLogger(__name__)


@overload
async def get_request(
    url: str,
    type: Literal["text"] = "text",
    timeout: int = 10,
    headers: dict[str, str] | None = None,
    print_on_err: bool = True,
) -> str | None: ...


@overload
async def get_request(
    url: str,
    type: Literal["json"],
    timeout: int = 10,
    headers: dict[str, str] | None = None,
    print_on_err: bool = True,
) -> dict[Any, Any] | None: ...


async def get_request(
    url: str,
    type: Literal["text", "json"] = "text",
    timeout: int = 10,
    headers: dict[str, str] | None = None,
    print_on_err: bool = True,
) -> str | dict[Any, Any] | None:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            logger.debug(f"Making request to {url}")
            response = await client.get(url, headers=headers)

        if response.status_code == 200:
            try:
                logger.debug(f"Received {response.content}")
                return response.text if type == "text" else response.json()
            except ValueError:
                return
        elif print_on_err:
            print(f"Error {response.status_code}")
            print(f"Response: {response.text}")
        else:
            logger.debug(
                f"URL request to '{url}' failed with Error {response.status_code}. Response: {response.text}"
            )
    except httpx.RequestError as e:
        print(f"An error occurred: {e!r}")


def get_request_raw(url: str):
    resp = None
    while True:
        try:
            resp = httpx.get(url, timeout=None)
        except httpx.HTTPError as e:
            print(f"Network error: {e!r}")
            if prompt_confirm("Try again?"):
                continue
        break
    if resp:
        return resp.content


def get_base_domain(url: str):
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    return base_url


def get_game_name(app_id: str) -> str:
    """Converts an App ID to a game name"""
    official_info = asyncio.run(
        get_request(
            f"https://store.steampowered.com/api/appdetails/?appids={app_id}",
            "json",
        )
    )
    if official_info:
        app_name = official_info.get(app_id, {}).get("data", {}).get("name")
        if app_name is None:
            app_name = prompt_text(
                "Request succeeded but couldn't find the game name. "
                "Type the name of it: "
            )
    else:
        app_name = prompt_text("Request failed. Type the name of the game: ")
    return app_name


@contextmanager
def download_to_tempfile(
    url: str,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
    chunk_size: int = (1024**2) // 2,
) -> Generator["_TemporaryFileWrapper[bytes] | None", None, None]:
    """Downloads and yields a tempfile, Defaults to 0.5MiB for chunk size"""
    temp_f = TemporaryFile()  # noqa: SIM115
    success = True
    try:
        with httpx.stream(
            "GET",
            url,
            headers=headers,
            params=params,
            follow_redirects=True,
            timeout=None,
        ) as response:

            try:
                total = int(response.headers.get("Content-Length", "0"))
            except Exception as e:
                print(f"Could not parse Content-Length header: {e}")
                total = 0
            logger.debug(f"Total size is {total}")
            with tqdm(
                desc="Downloading",
                total=total,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                miniters=1,
            ) as pbar:
                for chunk in response.iter_bytes(chunk_size=chunk_size):
                    temp_f.write(chunk)
                    pbar.update(len(chunk))
        temp_f.seek(0)
    except httpx.HTTPError as e:
        print(f"Network error: {e!r}")
        success = False

    try:
        yield temp_f if success else None
    finally:
        temp_f.close()
