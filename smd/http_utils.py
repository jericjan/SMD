import asyncio
import json
import logging
import msvcrt
import time
from contextlib import contextmanager
from tempfile import TemporaryFile
from typing import TYPE_CHECKING, Any, Generator, Literal, Optional, Union, overload

import gevent
import httpx
from steam.client import SteamClient  # type: ignore
from tqdm import tqdm  # type: ignore

from smd.prompts import prompt_confirm, prompt_text
from smd.structs import ProductInfo  # type: ignore

if TYPE_CHECKING:
    from tempfile import _TemporaryFileWrapper  # pyright: ignore[reportPrivateUsage]

logger = logging.getLogger(__name__)


@overload
async def get_request(url: str) -> Union[str, None]: ...


@overload
async def get_request(url: str, type: Literal["text"]) -> Union[str, None]: ...


@overload
async def get_request(
    url: str, type: Literal["json"]
) -> Union[dict[Any, Any], None]: ...


async def get_request(
    url: str, type: Literal["text", "json"] = "text", timeout: int = 10
) -> Union[str, dict[Any, Any], None]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            logger.debug(f"Making request to {url}")
            response = await client.get(url)

        if response.status_code == 200:
            try:
                logger.debug(f"Received {response.content}")
                return response.text if type == "text" else response.json()
            except ValueError:
                return
        else:
            print(f"Error {response.status_code}")
            print(f"Response: {response.text}")

    except httpx.RequestError as e:
        print(f"An error occurred: {repr(e)}")


def get_request_raw(url: str):
    resp = None
    while True:
        try:
            resp = httpx.get(url, timeout=None)
        except httpx.HTTPError as e:
            print(f"Network error: {repr(e)}")
            if prompt_confirm("Try again?"):
                continue
        break
    if resp:
        return resp.content


async def _wait_for_enter():
    print(
        "If it takes too long, press Enter to cancel the request "
        "and input manually..."
    )
    while True:
        if msvcrt.kbhit() and msvcrt.getch() == b"\r":
            return
        await asyncio.sleep(0.05)


# Lowkey don't remember why i wrote it like this.
# It uses a default timeout of 10s but i think it still got stuck?
async def get_gmrc(manifest_id: Union[str, int]) -> Union[str, None]:
    """Gets a manifest request code, given a manifest ID

    Args:
        manifest_id (Union[str, int]): The manifest ID

    Returns:
        str: The request code
    """
    url = f"http://gmrc.openst.top/manifest/{manifest_id}"
    print(f"Getting request code from: {url}")

    request_task = asyncio.create_task(get_request(url))
    cancel_task = asyncio.create_task(_wait_for_enter())

    done, pending = await asyncio.wait(
        {request_task, cancel_task}, return_when=asyncio.FIRST_COMPLETED
    )

    result = None
    if request_task in done:
        result = request_task.result()

    if cancel_task in done:
        if not request_task.done():
            print("Cancelling request...", end="")
            request_task.cancel()

    for t in pending:
        t.cancel()

    try:
        if result is None:
            result = await request_task
    except asyncio.CancelledError:
        print("✅")
        result = prompt_text("Please provide the manifest request code:")

    return result


def get_game_name(app_id: str):
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


def get_product_info(client: SteamClient, app_ids: list[int]) -> Optional[ProductInfo]:
    if not client.logged_on:
        print("Logging in anonymously...")
        client.anonymous_login()
    while True:
        try:
            start = time.time()
            info = client.get_product_info(  # pyright: ignore[reportUnknownMemberType]
                app_ids
            )
            logger.debug(f"Product info request took: {time.time() - start}s")
        except gevent.Timeout:
            print("Request timed out. Trying again")
            try:
                client.anonymous_login()  # might fix the endless timeout loop
            except RuntimeError:  # Alr logged in error
                pass
            continue
        break
    if info:
        logger.debug(f"get_product_info retured: {json.dumps(info)}")
        return ProductInfo(info)
    return None


@contextmanager
def download_to_tempfile(
    url: str, headers: Optional[dict[str, str]] = None, chunk_size: int = (1024**2) // 2
) -> Generator[Union["_TemporaryFileWrapper[bytes]", None], None, None]:
    """Downloads and yields a tempfile, Defaults to 0.5MiB for chunk size"""
    temp_f = TemporaryFile()
    try:
        with httpx.stream(
            "GET", url, headers=headers, follow_redirects=True, timeout=None
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
                miniters=1
            ) as pbar:
                for chunk in response.iter_bytes(chunk_size=chunk_size):
                    temp_f.write(chunk)
                    pbar.update(len(chunk))
        temp_f.seek(0)
        yield temp_f
    except httpx.HTTPError as e:
        print(f"Network error: {repr(e)}")
        yield None
    finally:
        temp_f.close()
