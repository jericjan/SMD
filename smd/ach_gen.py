import json
from pathlib import Path
from typing import Any

import httpx

from smd.prompts import prompt_text
from smd.storage.settings import get_or_compute_setting
from smd.ui.settings.types import Settings


def gen_achievements(app_id: str, steam_settings_dir: Path):
    """Experimental method of generating achievement data for gbe_fork.
    Uses Steam Web API Key instead of a user login."""

    def prompt_web_api_key():
        print(
            "You don't have a Steam Web API Key yet. "
            "Steam needs this in order to generate achievements in experimental mode.\n\n"
        )
        return prompt_text("Paste your Steam Web API Key:")

    api_key = get_or_compute_setting(Settings.STEAM_WEB_API_KEY, prompt_web_api_key)

    lang = "english"

    img_dir = steam_settings_dir / "img"
    img_dir.mkdir(parents=True, exist_ok=True)

    def download_image(client: httpx.Client, url: str):
        """DLs achievement image"""
        if not url:
            return ""

        filename = Path(url).name
        if not filename:
            return url

        filepath = img_dir / filename
        relative_path = f"img/{filename}"

        if filepath.exists():
            return relative_path

        try:
            with client.stream("GET", url) as response:
                if response.status_code == 200:
                    with open(filepath, "wb") as f:
                        for chunk in response.iter_bytes(chunk_size=1024):  # noqa: FURB122
                            f.write(chunk)
                    return relative_path
        except Exception as e:
            print(f"Failed to download asset {url}: {e}")
        return url

    print(f"Fetching public schema database for AppID {app_id}...")
    schema_url = "https://api.steampowered.com/ISteamUserStats/GetSchemaForGame/"
    f"v0002/?key={api_key}&appid={app_id}&l={lang}&format=json"

    with httpx.Client() as client:
        try:
            response = client.get(schema_url).json()
            achievements_schema = (
                response.get("game", {})
                .get("availableGameStats", {})
                .get("achievements", [])
            )
        except Exception as e:
            print(f"Error fetching data from Steam: {e}")
            return

        if not achievements_schema:
            print(
                "No achievements found for this game, or the AppID/API Key is invalid."
            )
            return

        final_schema_list: list[dict[str, Any]] = []
        print(
            f"Found {len(achievements_schema)} achievements. "
            "Processing SHA1 asset hashes..."
        )

        for ach in achievements_schema:
            local_icon_path = download_image(client, ach.get("icon", ""))
            local_icongray_path = download_image(client, ach.get("icongray", ""))

            final_schema_list.append(
                {
                    "description": ach.get("description", ""),
                    "displayName": ach.get("displayName", ach.get("name", "")),
                    "hidden": 1 if ach.get("hidden") == 1 else 0,
                    "icon": local_icon_path,
                    "icongray": local_icongray_path,
                    "name": ach.get("name", ""),
                }
            )

    json_path = steam_settings_dir / "achievements.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(final_schema_list, f, indent=4, ensure_ascii=False)

    print("\nDump Complete!")
    print(f"Schema data saved -> {json_path}")
    print(f"Deduped assets folder -> {img_dir}")
