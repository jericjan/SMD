import asyncio
import json
import msvcrt
from pathlib import Path
from typing import Any, Literal, Union, overload

import httpx

from smd.prompts import prompt_text
from smd.structs import NamedIDs


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
            response = await client.get(url)

        if response.status_code == 200:
            try:
                return response.text if type == "text" else response.json()
            except ValueError:
                return
        else:
            print(f"❌ Request failed with status code: {response.status_code}")
            print(f"Response: {response.text}")

    except httpx.RequestError as e:
        print(f"An error occurred: {e}")


async def wait_for_enter():
    print(
        "If it takes too long, press Enter to cancel the request "
        "and input manually..."
    )
    while True:
        if msvcrt.kbhit() and msvcrt.getch() == b"\r":
            return
        await asyncio.sleep(0.05)


async def get_gmrc(manifest_id: Union[str, int]) -> Union[str, None]:
    """Gets a manifest request code, given a manifest ID

    Args:
        manifest_id (Union[str, int]): The manifest ID

    Returns:
        str: The request code
    """
    url = f"http://gmrc.openst.top/manifest/{manifest_id}"
    print(f"Requesting from URL: {url}")

    request_task = asyncio.create_task(get_request(url))
    cancel_task = asyncio.create_task(wait_for_enter())

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


def load_named_ids(file: Path) -> NamedIDs:
    if not file.exists():
        return NamedIDs({})
    with file.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_named_ids(file: Path, data: NamedIDs):
    with file.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_named_ids(folder: Path) -> NamedIDs:
    """Gets names of games from lua files.
    Try to read saved names first, then request names of newer files.
    If there are untracked files, update `names.json` accordingly

    Args:
        folder (Path): Folder with .lua files in it

    Returns:
        dict: a dict in the format (game_id, game_name)
    """
    if not folder.exists():
        folder.mkdir()
        return NamedIDs({})

    id_names_file = folder / "names.json"
    named_ids: NamedIDs = load_named_ids(id_names_file)

    new_ids = False
    saved_ids = [x.stem for x in folder.glob("*.lua")]
    for saved_id in saved_ids:
        if saved_id not in named_ids:
            new_ids = True
            named_ids[saved_id] = get_game_name(saved_id)

    if new_ids:
        save_named_ids(id_names_file, named_ids)
    return named_ids
