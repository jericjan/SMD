import asyncio
import functools
import os
import shutil
import subprocess
import zipfile
from collections import OrderedDict
from pathlib import Path
from typing import Callable, Optional

from colorama import Fore, Style

from smd.applist import AppListManager
from smd.game_specific import GameHandler
from smd.http_utils import get_request
from smd.lua.manager import LuaManager
from smd.lua.writer import ACFWriter, ConfigVDFWriter
from smd.manifest.downloader import ManifestDownloader
from smd.midi import MidiPlayer
from smd.prompts import (
    prompt_confirm,
    prompt_dir,
    prompt_secret,
    prompt_select,
    prompt_text,
)
from smd.registry_access import set_stats_and_achievements
from smd.steam_client import SteamInfoProvider
from smd.storage.settings import get_setting, load_all_settings, set_setting
from smd.storage.vdf import get_steam_libs, vdf_dump, vdf_load
from smd.strings import VERSION
from smd.structs import (
    GameSpecificChoices,
    GreenLumaVersions,
    LoggedInUser,
    LuaChoice,
    MainReturnCode,
    MidiFiles,
    Settings,
)
from smd.utils import enter_path, root_folder


def music_toggle_decorator(func):  # type: ignore
    """
    A decorator that mutes/unmutes channels before/after a method call.
    The wrapper will receive the class instance as its first argument.
    """

    @functools.wraps(func)  # type: ignore
    def wrapper(self: "UI", *args, **kwargs):  # type: ignore
        if self.midi_player:
            self.midi_player.set_range(0, 5, 0)

        result = func(self, *args, **kwargs)  # type: ignore
        if self.midi_player:
            self.midi_player.set_range(0, 5, 1)

        return result  # type: ignore

    return wrapper  # type: ignore


class UI:
    def __init__(
        self,
        provider: SteamInfoProvider,
        steam_path: Path,
    ):
        self.provider = provider
        self.steam_path = steam_path
        self.app_list_man = AppListManager(steam_path, self.provider)

        self.init_midi_player()

    def init_midi_player(self):
        if (play_music := get_setting(Settings.PLAY_MUSIC)) is None:
            set_setting(Settings.PLAY_MUSIC, False)
            play_music = False

        if any([not x.value.exists() for x in list(MidiFiles)]) or not play_music:
            self.midi_player = None
        else:
            self.midi_player = MidiPlayer(MidiFiles.MIDI_PLAYER_DLL.value)
            self.midi_player.start()

    def kill_midi_player(self):
        if self.midi_player:
            self.midi_player.stop()
            del self.midi_player
            self.midi_player = None  # prolly does nothing but whatever

    @music_toggle_decorator
    def edit_settings_menu(self) -> MainReturnCode:
        while True:
            saved_settings = load_all_settings()
            selected_key: Optional[Settings] = prompt_select(
                "Select a setting to change:",
                [
                    (
                        x.clean_name
                        + (" (unset)" if x.key_name not in saved_settings else ""),
                        x,
                    )
                    for x in Settings
                ],
                cancellable=True,
            )
            if not selected_key:
                break
            value = get_setting(selected_key)
            value = value if value is not None else "(unset)"
            print(
                f"{selected_key.clean_name} is set to "
                + Fore.YELLOW
                + ("[ENCRYPTED]" if selected_key.hidden else str(value))
                + Style.RESET_ALL
            )
            if not prompt_confirm("Do you want to edit this setting?"):
                continue

            # TODO: move this functionality somewhere else / automate it
            if isinstance(value, bool):
                new_value = prompt_select(
                    "Select the new value:", [("Enabled", True), ("Disabled", False)]
                )
            elif selected_key == Settings.GL_VERSION:
                new_value = prompt_select(
                    "Select the new value:", [x.value for x in GreenLumaVersions]
                )
            else:
                func = prompt_secret if selected_key.hidden else prompt_text
                new_value = func("Enter the new value:")
            set_setting(selected_key, new_value)

            if selected_key == Settings.PLAY_MUSIC:
                if value is True and new_value is False:
                    self.kill_midi_player()
                elif value is False and new_value is True:
                    self.init_midi_player()

            if selected_key == Settings.APPLIST_FOLDER:
                self.app_list_man = AppListManager(self.steam_path, self.provider)
        return MainReturnCode.LOOP_NO_PROMPT

    @music_toggle_decorator
    def offline_fix_menu(self) -> MainReturnCode:
        print(
            Fore.YELLOW
            + "Steam will fail to launch when you close it while in OFFLINE Mode. "
            "Set it back to ONLINE to fix it." + Style.RESET_ALL
        )
        loginusers_file = self.steam_path / "config/loginusers.vdf"
        if not loginusers_file.exists():
            print(
                "loginusers.vdf file can't be found. "
                "Have you already logged in once through Steam?"
            )
            return MainReturnCode.LOOP_NO_PROMPT
        vdf_data = vdf_load(loginusers_file, mapper=OrderedDict)

        vdf_users = vdf_data.get("users")
        if vdf_users is None:
            print("There are no users on this Steam installation...")
            return MainReturnCode.LOOP_NO_PROMPT
        user_ids = vdf_users.keys()
        users: list[LoggedInUser] = []
        for user_id in user_ids:
            x = vdf_users[user_id]
            users.append(
                LoggedInUser(
                    user_id,
                    x.get("PersonaName", "[MISSING]"),
                    x.get("WantsOfflineMode", "[MISSING]"),
                )
            )
        if len(users) == 0:
            print("There are no users on this Steam installation")
            return MainReturnCode.LOOP_NO_PROMPT
        offline_converter: Callable[[str], str] = lambda x: (
            "ONLINE" if x == "0" else "OFFLINE"
        )
        chosen_user: Optional[LoggedInUser] = prompt_select(
            "Select a user: ",
            [
                (
                    f"{x.persona_name} - " + offline_converter(x.wants_offline_mode),
                    x,
                )
                for x in users
            ],
            cancellable=True,
        )
        if chosen_user is None:
            return MainReturnCode.LOOP_NO_PROMPT

        new_value = "0" if chosen_user.wants_offline_mode == "1" else "1"

        vdf_data["users"][chosen_user.steam64_id]["WantsOfflineMode"] = new_value
        vdf_dump(loginusers_file, vdf_data)
        print(f"{chosen_user.persona_name} is now {offline_converter(new_value)}")
        return MainReturnCode.LOOP

    @music_toggle_decorator
    def applist_menu(self) -> MainReturnCode:
        return self.app_list_man.display_menu(self.provider)

    def select_steam_library(self):
        """Returns success status"""
        steam_libs = get_steam_libs(self.steam_path)
        if len(steam_libs) == 1:
            return steam_libs[0]
        steam_lib_path: Optional[Path] = prompt_select(
            "Select a Steam library location:",
            steam_libs,
            cancellable=True,
            default=steam_libs[0],
        )
        return steam_lib_path

    @music_toggle_decorator
    def handle_game_specific(self, choice: GameSpecificChoices) -> MainReturnCode:
        if (lib_path := self.select_steam_library()) is None:
            return MainReturnCode.LOOP_NO_PROMPT
        handler = GameHandler(
            self.steam_path, lib_path, self.provider, self.app_list_man
        )
        return handler.execute_choice(choice)

    @music_toggle_decorator
    def process_lua_minimal(self) -> MainReturnCode:
        """Processes a .lua file but only does the lua input, lua backup, and manifest
        download steps"""

        print(
            Fore.YELLOW + "This is the minimal version of the lua processing logic. "
            "Only use this when updating a game or if you want to export manifest "
            "files to a different folder." + Style.RESET_ALL
        )
        if not prompt_confirm("Continue?"):
            return MainReturnCode.LOOP_NO_PROMPT

        lua_choice: Optional[LuaChoice] = prompt_select(
            "Choose:", list(LuaChoice), cancellable=True
        )

        if lua_choice is None:
            return MainReturnCode.LOOP_NO_PROMPT

        lua_manager = LuaManager()
        downloader = ManifestDownloader(self.provider, self.steam_path)

        parsed_lua = lua_manager.fetch_lua(lua_choice)
        lua_manager.backup_lua(parsed_lua)
        print(Fore.YELLOW + "\nDownloading Manifests:" + Style.RESET_ALL)
        manifests = downloader.download_manifests(parsed_lua)
        move_files = prompt_confirm(
            "Manifests are now in the depotcache folder. "
            "Would you like to transfer these files to another folder?",
            default=False
        )
        if move_files:
            dst = prompt_dir("Paste in here the folder you'd like to move them to:")
            for file in manifests:
                shutil.move(file, dst / file.name)
                print(f"{file.name} moved")
        print(
            Fore.GREEN + "\nSuccess! ", end=""
        )
        if not move_files:
            print(
                "Close Steam and run DLLInjector again "
                "(or not depending on how you installed Greenluma). "
                'Your game should show up in the library ready to "update"'
                , end=""
            )
        print(Style.RESET_ALL)
        return MainReturnCode.LOOP

    @music_toggle_decorator
    def process_lua_full(self) -> MainReturnCode:
        """Processes a .lua file and goes through all the usual steps"""
        if (lib_path := self.select_steam_library()) is None:
            return MainReturnCode.LOOP_NO_PROMPT

        lua_choice: Optional[LuaChoice] = prompt_select(
            "Choose:", list(LuaChoice), cancellable=True
        )

        if lua_choice is None:
            return MainReturnCode.LOOP_NO_PROMPT

        lua_manager = LuaManager()
        downloader = ManifestDownloader(self.provider, self.steam_path)
        config = ConfigVDFWriter(self.steam_path)
        acf = ACFWriter(lib_path)

        parsed_lua = lua_manager.fetch_lua(lua_choice)
        set_stats_and_achievements(int(parsed_lua.app_id))
        print(Fore.YELLOW + "\nAdding to AppList folder:" + Style.RESET_ALL)
        self.app_list_man.add_ids(parsed_lua)
        self.app_list_man.dlc_check(self.provider, int(parsed_lua.app_id))
        print(Fore.YELLOW + "\nAdding Decryption Keys:" + Style.RESET_ALL)
        config.add_decryption_keys_to_config(parsed_lua)
        lua_manager.backup_lua(parsed_lua)
        print(Fore.YELLOW + "\nACF Writing:" + Style.RESET_ALL)
        acf.write_acf(parsed_lua)
        print(Fore.YELLOW + "\nDownloading Manifests:" + Style.RESET_ALL)
        downloader.download_manifests(parsed_lua)
        print(
            Fore.GREEN + "\nSuccess! Close Steam and run DLLInjector again "
            "(or not depending on how you installed Greenluma). "
            'Your game should show up in the library ready to "update"'
            + Style.RESET_ALL
        )
        return MainReturnCode.LOOP

    def check_updates(self, test: bool = False) -> MainReturnCode:
        print("Making request to github...", end="", flush=True)
        resp = None
        while resp is None:
            resp = asyncio.run(
                get_request(
                    "https://api.github.com/repos/jericjan/smd/releases/latest", "json"
                )
            )
        print("Done!")
        remote_version = resp.get("tag_name")
        print(f"Local Version: {VERSION}")
        print(f"Remote Version: {remote_version}")
        if VERSION == remote_version and test is False:
            print(Fore.GREEN + "You're up to date!" + Style.RESET_ALL)
            return MainReturnCode.LOOP_NO_PROMPT
        print(Fore.RED + "Your SMD is outdated." + Style.RESET_ALL)
        if not prompt_confirm("Would you like to update?"):
            return MainReturnCode.LOOP_NO_PROMPT
        download_url = enter_path(resp, "assets", 0, "browser_download_url")
        if not download_url:
            print("Couldn't find the download URL :(")
            return MainReturnCode.LOOP_NO_PROMPT
        print(f"Download URL: {download_url}")
        aria2c_exe = root_folder() / "third_party/aria2c/aria2c.exe"
        subprocess.run(
            [
                aria2c_exe,
                "-x",
                "64",
                "-k",
                "1K",
                "-s",
                "64",
                "-d",
                str(Path.cwd().resolve()),
                download_url,
            ]
        )
        zip_name = Path(download_url).name
        print(
            Fore.GREEN
            + "\n\nThe cursed update is about to begin. Prepare yourself."
            + Style.RESET_ALL
        )
        tmp_dir = Path.cwd() / "tmp"
        zip_path = Path.cwd() / zip_name
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp_dir)
        zip_path.unlink(missing_ok=True)
        updater = Path.cwd() / "tmp_updater.bat"
        with updater.open("w", encoding="utf-8") as f:
            nul = [">", "NUL"]
            internal_dir = str(Path.cwd() / "_internal")
            smd_exe = str(Path.cwd() / "SMD.exe")
            tmp_dir = str(Path.cwd() / "tmp")
            convert = subprocess.list2cmdline
            f.writelines(
                [
                    "@echo off\n",
                    "echo Killing SMD...\n",
                    f"taskkill /F /PID {os.getpid()}\n",
                    "echo SMD killed. Deleting old files...\n",
                    convert(["rmdir", "/s", "/q", internal_dir, *nul]) + "\n",
                    convert(["del", "/q", smd_exe, *nul]) + "\n",
                    "echo Old files deleted. Moving in new files...\n",
                    convert(["robocopy", "/E", "/MOVE", tmp_dir, str(Path.cwd()), *nul])
                    + "\n",
                    convert(["rmdir", "/s", "/q", tmp_dir, *nul]) + "\n",
                    "echo UPDATE COMPLETE!!!! You can close this now\n",
                    '(goto) 2>nul & del "%~f0"',
                ]
            )
        command = convert(["cmd", "/k", str(updater.resolve())])
        subprocess.Popen(command, creationflags=subprocess.DETACHED_PROCESS, shell=True)
        return MainReturnCode.LOOP_NO_PROMPT
