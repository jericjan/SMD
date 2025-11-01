"""gbe_fork and Steamless stuff in here"""

import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Literal, NamedTuple, Optional, overload

import vdf  # type: ignore
from steam.client import SteamClient  # type: ignore

from smd.prompts import prompt_file, prompt_secret, prompt_select, prompt_text
from smd.storage.settings import get_setting, set_setting
from smd.structs import (
    GameSpecificChoices,
    GenEmuMode,
    MainMenu,
    MainReturnCode,
    Settings,
)
from smd.utils import enter_path, root_folder


class AppInfo(NamedTuple):
    app_id: str
    path: Path


class GameCracker:
    def __init__(self, library_path: Path, client: SteamClient):
        self.steamapps_path = library_path / "steamapps"
        self.client = client

    def get_game(self) -> Optional[AppInfo]:
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
        return prompt_select("Select a game", games, fuzzy=True, cancellable=True)

    def find_steam_dll(self, game_path: Path) -> Optional[Path]:
        files = list(game_path.rglob("steam_api*.dll"))
        if len(files) > 1:
            return prompt_select(
                "More than one DLL found. Pick one:",
                [(str(x.relative_to(game_path)), x) for x in files],
            )
        if len(files) == 1:
            return files[0]
        return None

    @overload
    def run_gen_emu(
        self, app_id: str, mode: Literal[GenEmuMode.USER_GAME_STATS]
    ) -> None: ...

    @overload
    def run_gen_emu(
        self,
        app_id: str,
        mode: Literal[GenEmuMode.STEAM_SETTINGS, GenEmuMode.ALL],
        dst_steam_settings_folder: Path,
    ) -> None: ...

    def run_gen_emu(
        self,
        app_id: str,
        mode: GenEmuMode,
        dst_steam_settings_folder: Optional[Path] = None,
    ):
        if mode in (GenEmuMode.STEAM_SETTINGS, GenEmuMode.ALL):
            if dst_steam_settings_folder is None:
                raise ValueError(
                    "dst_steam_settings_folder is required for STEAM_SETTINGS or ALL."
                )

        tools_folder = root_folder() / "third_party/gbe_fork_tools/generate_emu_config/"
        config_exe = tools_folder / "generate_emu_config.exe"
        if (
            (user := get_setting(Settings.STEAM_USER)) is None
            or (password := get_setting(Settings.STEAM_PASS)) is None
            or (steam32_id := get_setting(Settings.STEAM32_ID)) is None
        ):
            print(
                "No steam credentials saved. Please provide them. "
                "This is all stored locally."
            )
            user = prompt_text("Username:")
            password = prompt_secret("Password:")
            steam32_id = prompt_text(
                "Your Steam32 ID:",
                long_instruction="You can try visiting https://steamid.xyz/ "
                "to find it.",
            )
            set_setting(Settings.STEAM_USER, user)
            set_setting(Settings.STEAM_PASS, password)
            set_setting(Settings.STEAM32_ID, steam32_id)

        env = os.environ.copy()
        env["GSE_CFG_USERNAME"] = user
        env["GSE_CFG_PASSWORD"] = password

        extra_args: list[str] = []
        if mode == GenEmuMode.USER_GAME_STATS:
            extra_args.extend(["-skip_con", "-skip_inv"])
        subprocess.run(
            [str(config_exe.absolute()), "-clean", *extra_args, app_id],
            env=env,
            cwd=str(tools_folder.absolute()),
        )
        backup_folder = tools_folder / f"backup/{app_id}"
        src_steam_settings = tools_folder / f"output/{app_id}/steam_settings"

        steam_root = self.steamapps_path.parent
        steam_stats_folder = steam_root / "appcache/stats"

        if mode == GenEmuMode.USER_GAME_STATS or mode == GenEmuMode.ALL:
            bin_files = backup_folder.glob("*.bin")
            bin_file_count = 0
            for bin_file in bin_files:
                bin_file_count += 1
                shutil.copy(bin_file, steam_stats_folder)
                print(f"{bin_file.name} copied to {str(steam_stats_folder)}")

            if bin_file_count == 0:
                id_64 = prompt_text(
                    "No .bin files found. Go to https://steamladder.com/ and "
                    "find the game you want, "
                    "then copy the Steam64 ID of a random user that owns that game"
                ).strip()
                with Path(
                    r"third_party\gbe_fork_tools\generate_emu_config\top_owners_ids.txt"
                ).open("w", encoding="utf-8") as f:
                    f.write(id_64)
                self.run_gen_emu(app_id, GenEmuMode.USER_GAME_STATS)

            src_user_stats = root_folder() / "static/UserGameStats_steamid_appid.bin"
            dst_user_stats = (
                steam_stats_folder / f"UserGameStats_{steam32_id}_{app_id}.bin"
            )
            if not dst_user_stats.exists():
                shutil.copy(src_user_stats, dst_user_stats)
                print(
                    f"{str(src_user_stats.relative_to(root_folder()))} copied to "
                    + str(dst_user_stats)
                )
            else:
                print(f"{dst_user_stats.name} already exists. Skipping this step.")

        if mode == GenEmuMode.STEAM_SETTINGS or mode == GenEmuMode.ALL:
            assert dst_steam_settings_folder is not None
            shutil.copytree(
                src_steam_settings, dst_steam_settings_folder, dirs_exist_ok=True
            )
            print(
                f"{str(src_steam_settings.relative_to(root_folder()))} copied to "
                + str(dst_steam_settings_folder)
            )

    def _crack_dll_core(self, app_id: str, dll_path: Path):
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

        gse_app_folder = Path.home() / f"AppData/Roaming/GSE Saves/{app_id}"

        if not gse_app_folder.exists():
            print("GSE Saves folder doesn't exist. Creating...")
            gse_app_folder.mkdir()

        backup_name = dll_path.parent / ("OG_" + dll_path.name)
        if backup_name.exists():
            backup_name.unlink()
        dll_path.rename(backup_name)

        shutil.copytree(gbe_fork_folder, api_folder, dirs_exist_ok=True)
        (api_folder / "steam_appid.txt").write_text(app_id, "utf-8")

        # TODO: this sucks btw
        if "64" in dll_path.name:
            (api_folder / "steam_api.dll").unlink()
        else:  # 32
            (api_folder / "steam_api64.dll").unlink()

    def crack_dll(self, app_id: str, dll_path: Path):
        self._crack_dll_core(app_id, dll_path)
        gen_achievements = prompt_select(
            "Would you like to generate config files for gbe_fork? "
            "(Contains achievement data)",
            [("Yes", True), ("No", False)],
        )
        if gen_achievements:
            self.run_gen_emu(
                app_id, GenEmuMode.STEAM_SETTINGS, dll_path.parent / "steam_settings"
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

    def _prompt_manual_exe(self, app_info: AppInfo):
        subprocess.run(["explorer", app_info.path])
        game_exe = prompt_file(
            "Drag the game .exe here and press Enter:",
        )
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

    def execute_choice(self, choice: GameSpecificChoices) -> MainReturnCode:
        app_info = self.get_game()
        if app_info is None:
            return MainReturnCode.LOOP_NO_PROMPT
        if choice == MainMenu.CRACK_GAME:
            dll = self.find_steam_dll(app_info.path)
            if dll is None:
                print(
                    "Could not find steam_api DLL. "
                    "Maybe you haven't downloaded the game yet..."
                )
            else:
                self.crack_dll(app_info.app_id, dll)
        elif choice == MainMenu.REMOVE_DRM:
            self.apply_steamless(app_info)
        elif choice == MainMenu.DL_USER_GAME_STATS:
            self.run_gen_emu(app_info.app_id, GenEmuMode.USER_GAME_STATS)
        return MainReturnCode.LOOP
