import asyncio
from typing import Any, Optional
import httpx
import json

from smd.http_utils import get_request
from smd.strings import GITHUB_USERNAME, REPO_NAME, VERSION


class Updater:
    @staticmethod
    def get_latest_stable() -> dict[str, Any]:
        resp = None
        while resp is None:
            resp = asyncio.run(
                get_request(
                    "https://api.github.com/repos/"
                    f"{GITHUB_USERNAME}/{REPO_NAME}/releases/latest",
                    "json",
                )
            )
        return resp

    @staticmethod
    def get_latest_prerelease() -> Optional[dict[str, Any]]:
        """Returns none of prerelease newer than current version can't be found"""
        url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/releases"
        while True:
            resp = httpx.get(url)
            releases = json.loads(resp.text)
            for release in releases:
                tag = release.get("tag_name")
                if tag == VERSION:
                    return
                if release.get("prerelease") is True:
                    return release
            if "next" in resp.links:
                url = resp.links["next"]["url"]
            else:
                break
