import hashlib
import shutil
import subprocess
from pathlib import Path
from typing import Any, NamedTuple, Optional

import pyperclip
import vdf  # type: ignore

from utils import enter_path, prompt_select, root_folder
from steam.client import SteamClient  # type: ignore


class AppInfo(NamedTuple):
    app_id: str
    path: Path


class GameCracker:
    def __init__(self, library_path: Path, client: SteamClient):
        self.steamapps_path = library_path / "steamapps"
        self.client = client

    def get_game(self) -> AppInfo:
        games: list[tuple[str, AppInfo]] = []
        for path in self.steamapps_path.glob("*.acf"):
            with path.open(encoding="utf-8") as f:
                app_acf: dict[Any, Any] = vdf.load(f, mapper=vdf.VDFDict)  # type: ignore
            app_state = app_acf.get("AppState", {})
            name = app_state.get("name")
            installdir = app_state.get("installdir")
            app_id = app_state.get("appid")
            games.append(
                (name, AppInfo(app_id, self.steamapps_path / "common" / installdir))
            )
        return prompt_select("Select a game", games, fuzzy=True)

    def find_steam_dll(self, game_path: Path) -> Optional[Path]:
        files = list(game_path.rglob("steam_api*.dll"))
        if len(files) > 1:
            return prompt_select(
                "More than one DLL found. Pick one:", [(x.name, x) for x in files]
            )
        if len(files) == 1:
            return files[0]
        return None

    def crack_dll(self, app_id: str, dll_path: Path):
        gbe_fork_folder = root_folder() / "third_party/gbe_fork/"
        with dll_path.open("rb") as f:
            target_hash = hashlib.md5(f.read()).hexdigest()
        with (gbe_fork_folder / dll_path.name).open("rb") as f:
            source_hash = hashlib.md5(f.read()).hexdigest()
        if source_hash == target_hash:
            print("DLL already cracked.")
            return
        print("DLL has not been cracked")

        api_folder = dll_path.parent
        (api_folder / "steam_appid.txt").write_text(app_id, "utf-8")

        gse_app_folder = Path.home() / f"AppData/Roaming/GSE Saves/{app_id}"

        if not gse_app_folder.exists():
            print("GSE Saves folder doesn't exist. Creating...")
            gse_app_folder.mkdir()

        backup_name = dll_path.parent / ("OG_" + dll_path.name)
        if backup_name.exists():
            backup_name.unlink()
        dll_path.rename(backup_name)

        shutil.copytree(gbe_fork_folder, api_folder, dirs_exist_ok=True)

        # TODO: this sucks btw
        if "64" in dll_path.name:
            (api_folder / "steam_api.dll").unlink()
        else:  # 32
            (api_folder / "steam_api64.dll").unlink()

        pyperclip.copy(str(api_folder.absolute()))
        print(
            "API folder has been copied to clipboard. "
            "Use a tool like Achievement Watcher to generate it."
        )

    def apply_steamless(self, app_info: AppInfo):
        game_exe = self.select_executable(app_info)

        steamless_exe = root_folder() / "third_party/steamless/Steamless.CLI.exe"

        output = subprocess.run(
            [str(steamless_exe.absolute()), str(game_exe.absolute())],
            encoding="utf-8",
            capture_output=True,
        )
        if "Successfully unpacked file!" in output.stdout:
            print("Steamtools applied!")
            unpacked = game_exe.parent / (game_exe.name + ".unpacked.exe")
            game_exe.unlink()
            unpacked.rename(game_exe)

        else:
            print(output.stdout)
            print("Steamtools failed...")

    def _prompt_manual_exe(self, app_info : AppInfo):
        subprocess.run(["explorer", app_info.path])
        while True:
            game_exe = Path(
                input("Drag the game .exe here and press Enter: ").strip("\"'")
            )
            if not game_exe.exists():
                print("Doesn't exist. Try again")
            break
        return game_exe

    def _get_windows_execs(self, info: dict[str, Any], app_id: int) -> list[str]:
        launches = enter_path(info, "apps", app_id, "config", "launch")
        return [
            launch["executable"]
            for launch in launches.values()
            if enter_path(launch, "config", "oslist") == "windows"
        ]

    def select_executable(self, app_info: AppInfo) -> Path:
        """Selects EXE to get used for Steamless"""
        if not self.client.logged_on:
            print("Logging in to Steam anonymously...")
            self.client.anonymous_login()

        info = self.client.get_product_info([int(app_info.app_id)])  # type: ignore
        if not info:
            print("Failed to get app info...")
            return self._prompt_manual_exe(app_info)

        windows_exes = self._get_windows_execs(info, int(app_info.app_id))
        if not windows_exes:
            return self._prompt_manual_exe(app_info)

        if len(windows_exes) == 1:
            return app_info.path / windows_exes[0]

        chosen = prompt_select("Choose the exe:", windows_exes)
        return app_info.path / chosen
