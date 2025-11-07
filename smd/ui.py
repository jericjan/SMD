import functools
from collections import OrderedDict
from pathlib import Path
from typing import Callable, Optional

from colorama import Fore, Style
from steam.client import SteamClient  # type: ignore

from smd.applist import AppListManager
from smd.game_specific import GameHandler
from smd.lua.manager import LuaManager
from smd.lua.writer import ACFWriter, ConfigVDFWriter
from smd.manifest.downloader import ManifestDownloader
from smd.midi import MidiPlayer
from smd.prompts import prompt_secret, prompt_select, prompt_text
from smd.storage.settings import get_setting, load_all_settings, set_setting
from smd.storage.vdf import get_steam_libs, vdf_dump, vdf_load
from smd.structs import (
    GameSpecificChoices,
    LoggedInUser,
    LuaChoice,
    MainReturnCode,
    MidiFiles,
    Settings,
)


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
        client: SteamClient,
        steam_path: Path,
    ):
        self.steam_client = client
        self.steam_path = steam_path
        self.app_list_man = AppListManager(steam_path)

        if (play_music := get_setting(Settings.PLAY_MUSIC)) is None:
            set_setting(Settings.PLAY_MUSIC, False)
            play_music = False

        if any([not x.value.exists() for x in list(MidiFiles)]) or not play_music:
            self.midi_player = None
        else:
            self.midi_player = MidiPlayer(MidiFiles.MIDI_PLAYER_DLL.value)
            self.midi_player.start()

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
            edit = prompt_select(
                "Do you want to edit this setting?", [("Yes", True), ("No", False)]
            )
            if not edit:
                continue
            if isinstance(value, bool):
                new_value = prompt_select(
                    "Select the new value:", [("Enabled", True), ("Disabled", False)]
                )
            else:
                func = prompt_secret if selected_key.hidden else prompt_text
                new_value = func("Enter the new value:")
            set_setting(selected_key, new_value)

            if selected_key == Settings.PLAY_MUSIC:
                if value is True and new_value is False and self.midi_player:
                    self.midi_player.stop()
                    del self.midi_player
                    self.midi_player = None  # Deallocate from memory
                elif value is False and new_value is True:
                    if self.midi_player is None:
                        self.midi_player = MidiPlayer((MidiFiles.MIDI_PLAYER_DLL.value))
                    self.midi_player.start()

            if selected_key == Settings.APPLIST_FOLDER:
                self.app_list_man = AppListManager(self.steam_path)
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
        return self.app_list_man.display_menu(self.steam_client)

    def select_steam_library(self):
        """Returns success status"""
        steam_libs = get_steam_libs(self.steam_path)
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
        handler = GameHandler(self.steam_path, lib_path, self.steam_client)
        return handler.execute_choice(choice)

    @music_toggle_decorator
    def process_lua_choice(self) -> MainReturnCode:
        if (lib_path := self.select_steam_library()) is None:
            return MainReturnCode.LOOP_NO_PROMPT

        lua_choice: Optional[LuaChoice] = prompt_select(
            "Choose:", list(LuaChoice), cancellable=True
        )

        if lua_choice is None:
            return MainReturnCode.LOOP_NO_PROMPT

        lua_manager = LuaManager()
        downloader = ManifestDownloader(self.steam_client, self.steam_path)
        config = ConfigVDFWriter(self.steam_path)
        acf = ACFWriter(lib_path)

        parsed_lua = lua_manager.fetch_lua(lua_choice)
        print(Fore.YELLOW + "\nAdding to AppList folder:" + Style.RESET_ALL)
        self.app_list_man.add_ids(parsed_lua)
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
