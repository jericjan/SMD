import functools
import os
import shutil
import subprocess
import sys
import zipfile
from collections import OrderedDict
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, Union

from colorama import Fore, Style

from smd.app_injector.applist import AppListManager
from smd.game_specific import GameHandler
from smd.lua.manager import LuaManager
from smd.lua.writer import ACFWriter, ConfigVDFWriter
from smd.manifest.downloader import ManifestDownloader
from smd.midi import MidiPlayer
from smd.processes import SteamProcess
from smd.prompts import (
    prompt_confirm,
    prompt_dir,
    prompt_file,
    prompt_secret,
    prompt_select,
    prompt_text,
)
from smd.app_injector.sls import SLSManager
from smd.steam_client import SteamInfoProvider
from smd.storage.acf import ACFParser
from smd.storage.settings import (
    clear_setting,
    get_setting,
    load_all_settings,
    set_setting,
)
from smd.storage.vdf import get_steam_libs, vdf_dump, vdf_load
from smd.strings import VERSION
from smd.structs import (
    ContextMenuOptions,
    GameSpecificChoices,
    LoggedInUser,
    LuaChoice,
    MainReturnCode,
    MidiFiles,
    OSType,
    ReleaseType,
    SettingCustomTypes,
    SettingOperations,
    Settings,
)
from smd.updater import Updater
from smd.utils import enter_path, root_folder

if sys.platform == "win32":
    from smd.registry_access import (
        install_context_menu,
        set_stats_and_achievements,
        uninstall_context_menu,
    )
else:
    install_context_menu = lambda: None  # noqa: E731
    set_stats_and_achievements = lambda *args: False  # type: ignore # noqa: E731
    uninstall_context_menu = lambda: None  # noqa: E731


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
        os_type: OSType
    ):
        self.provider = provider
        self.steam_path = steam_path
        self.app_list_man = (
            AppListManager(steam_path, self.provider)
            if os_type == OSType.WINDOWS
            else None
        )
        self.os_type = os_type
        self.sls_man = (
            SLSManager(steam_path, provider) if os_type == OSType.LINUX else None
        )

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
        win_only = [Settings.APPLIST_FOLDER, Settings.GL_VERSION]
        linux_only = [Settings.SLS_CONFIG_LOCATION]
        if self.os_type == OSType.WINDOWS:
            ignore = linux_only
        elif self.os_type == OSType.LINUX:
            ignore = win_only
        else:
            ignore = []

        while True:
            saved_settings = load_all_settings()
            selected_key: Optional[Settings] = prompt_select(
                "Select a setting to change:",
                [
                    (
                        x.clean_name
                        + (
                            " (unset)"
                            if x.key_name not in saved_settings
                            else (
                                f": {saved_settings.get(x.key_name)}"
                                if not x.hidden
                                else ": [ENCRYPTED]"
                            )
                        ),
                        x,
                    )
                    for x in Settings if x not in ignore
                ],
                cancellable=True,
            )
            if not selected_key:
                break
            value = saved_settings.get(selected_key.key_name)
            value = value if value is not None else "(unset)"
            print(
                f"{selected_key.clean_name} is set to "
                + Fore.YELLOW
                + ("[ENCRYPTED]" if selected_key.hidden else str(value))
                + Style.RESET_ALL
            )
            operation: Optional[SettingOperations] = prompt_select(
                "What do you want to do with this setting?",
                list(SettingOperations),
                cancellable=True,
            )

            if operation is None:
                continue

            if operation == SettingOperations.DELETE:
                clear_setting(selected_key)
                continue

            if operation == SettingOperations.EDIT:
                new_settings_value: Union[str, bool]
                if selected_key.type == bool:
                    new_settings_value = prompt_confirm(
                        "Select the new value:", "Enable", "Disable"
                    )
                elif isinstance(selected_key.type, list):
                    enum_val: Enum = prompt_select(
                        "Select the new value:", selected_key.type
                    )
                    new_settings_value = enum_val.value
                elif selected_key.type == str:
                    func = prompt_secret if selected_key.hidden else prompt_text
                    new_settings_value = func("Enter the new value:")
                elif selected_key.type == SettingCustomTypes.DIR:
                    new_settings_value = str(
                        prompt_dir("Enter the new directory:").resolve()
                    )
                elif selected_key.type == SettingCustomTypes.FILE:
                    new_settings_value = str(
                        prompt_file("Enter the new file path:").resolve()
                    )
                else:
                    raise Exception("Unhandled setting type. Shouldn't happen.")
                set_setting(selected_key, new_settings_value)

                if selected_key == Settings.PLAY_MUSIC:
                    if value is True and new_settings_value is False:
                        self.kill_midi_player()
                    elif value is False and new_settings_value is True:
                        self.init_midi_player()

                if (
                    selected_key == Settings.APPLIST_FOLDER
                    and self.os_type == OSType.WINDOWS
                ):
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
        if self.app_list_man is None:
            print("Not supported for this OS")
            return MainReturnCode.LOOP_NO_PROMPT
        return self.app_list_man.display_menu(self.provider)

    def select_steam_library(self):
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
        injection_manager = self.app_list_man or self.sls_man
        if injection_manager is None:
            print("Unsupported OS for this action.")
            return MainReturnCode.LOOP_NO_PROMPT

        if (lib_path := self.select_steam_library()) is None:
            return MainReturnCode.LOOP_NO_PROMPT
        handler = GameHandler(
            self.steam_path, lib_path, self.provider, injection_manager
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

        lua_manager = LuaManager()
        downloader = ManifestDownloader(self.provider, self.steam_path)
        steam_proc = (
            SteamProcess(self.steam_path, self.app_list_man.applist_folder)
            if self.app_list_man
            else None
        )

        parsed_lua = lua_manager.fetch_lua()
        if parsed_lua is None:
            return MainReturnCode.LOOP_NO_PROMPT
        lua_manager.backup_lua(parsed_lua)
        print(Fore.YELLOW + "\nDownloading Manifests:" + Style.RESET_ALL)
        decrypt = prompt_confirm(
            "Would you like to also decrypt the manifest files?"
            " (Usually not needed)",
            default=False,
        )
        manifests = downloader.download_manifests(parsed_lua, decrypt=decrypt)
        move_files = prompt_confirm(
            "Manifests are now in the depotcache folder. "
            "Would you like to transfer these files to another folder?",
            default=False,
        )
        if move_files:
            dst = prompt_dir("Paste in here the folder you'd like to move them to:")
            for file in manifests:
                shutil.move(file, dst / file.name)
                print(f"{file.name} moved")
        if steam_proc:
            auto_launch = steam_proc.prompt_launch_or_restart()
        else:
            auto_launch = False

        print(Fore.GREEN + "\nSuccess! ", end="")
        if not move_files:
            extra_msg = (
                "Close Steam and run DLLInjector again "
                "(or not depending on how you installed Greenluma). "
            ) if not auto_launch else ""
            print(
                extra_msg + 'Your game should show up in the library ready to "update"',
                end="",
            )
        print(Style.RESET_ALL)
        return MainReturnCode.LOOP

    @music_toggle_decorator
    def process_lua_full(self, file: Optional[Path] = None) -> MainReturnCode:
        """Processes a .lua file and goes through all the usual steps"""
        if (lib_path := self.select_steam_library()) is None:
            return MainReturnCode.LOOP_NO_PROMPT

        lua_manager = LuaManager()
        downloader = ManifestDownloader(self.provider, self.steam_path)
        config = ConfigVDFWriter(self.steam_path)
        acf = ACFWriter(lib_path)
        steam_proc = (
            SteamProcess(self.steam_path, self.app_list_man.applist_folder)
            if self.app_list_man
            else None
        )
        parsed_lua = lua_manager.fetch_lua(
            LuaChoice.ADD_LUA if file else None, override_path=file
        )
        if parsed_lua is None:
            return MainReturnCode.LOOP_NO_PROMPT
        set_stats_and_achievements(int(parsed_lua.app_id))
        if self.app_list_man:
            print(Fore.YELLOW + "\nAdding to AppList folder:" + Style.RESET_ALL)
            self.app_list_man.add_ids(parsed_lua)
            self.app_list_man.dlc_check(self.provider, int(parsed_lua.app_id))
        elif self.sls_man:
            print(Fore.YELLOW + "\nAdding to SLSSteam config:" + Style.RESET_ALL)
            self.sls_man.add_ids(parsed_lua)
            self.sls_man.dlc_check(self.provider, int(parsed_lua.app_id))
        print(Fore.YELLOW + "\nAdding Decryption Keys:" + Style.RESET_ALL)
        config.add_decryption_keys_to_config(parsed_lua)
        lua_manager.backup_lua(parsed_lua)
        print(Fore.YELLOW + "\nACF Writing:" + Style.RESET_ALL)
        acf.write_acf(parsed_lua)
        print(Fore.YELLOW + "\nDownloading Manifests:" + Style.RESET_ALL)
        downloader.download_manifests(parsed_lua)
        if steam_proc:
            auto_launch = steam_proc.prompt_launch_or_restart()
        else:
            auto_launch = False
        extra_msg = (
            "Close Steam and run DLLInjector again "
            "(or not depending on how you installed Greenluma). "
        ) if not auto_launch else ""
        print(
            Fore.GREEN + f"\nSuccess! {extra_msg}"
            'Your game should show up in the library ready to "update"'
            + Style.RESET_ALL
        )
        return MainReturnCode.LOOP

    def manage_context_menu(self) -> MainReturnCode:
        choice: Optional[ContextMenuOptions] = prompt_select(
            "Select an operation for the context menu:",
            list(ContextMenuOptions),
            cancellable=True,
        )
        if choice is None:
            return MainReturnCode.LOOP_NO_PROMPT
        if choice == ContextMenuOptions.INSTALL:
            install_context_menu()
        elif choice == ContextMenuOptions.UNINSTALL:
            uninstall_context_menu()
        return MainReturnCode.LOOP_NO_PROMPT

    def check_updates(self, test: bool = False) -> MainReturnCode:
        if self.os_type == OSType.LINUX:
            print("Updating isn't supported yet on linux.")
            return MainReturnCode.LOOP_NO_PROMPT

        if not getattr(sys, "frozen", False):
            print("Program isn't frozen. You can't update.")
            return MainReturnCode.LOOP_NO_PROMPT

        release_type: Optional[ReleaseType] = prompt_select(
            "Which type of release would you like to update to?",
            list(ReleaseType),
            cancellable=True,
        )
        if release_type is None:
            return MainReturnCode.LOOP_NO_PROMPT
        print("Making request to github...", end="", flush=True)
        if release_type == ReleaseType.STABLE:
            resp = Updater.get_latest_stable()
        elif release_type == ReleaseType.PRERELEASE:
            resp = Updater.get_latest_prerelease()
        print("Done!")
        if resp is None:
            print("Could not find a release that matched your request :(")
            return MainReturnCode.LOOP_NO_PROMPT
        remote_version = resp.get("tag_name")
        print(f"Your Version: {VERSION}")
        print(f"Latest Version: {remote_version}")
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
                    "echo UPDATE COMPLETE!!!! You can close this now\n",
                    '(goto) 2>nul & del "%~f0"',
                ]
            )
        command = convert(["cmd", "/k", str(updater.resolve())])
        subprocess.Popen(
            command, creationflags=subprocess.DETACHED_PROCESS, shell=True  # type:ignore
        )
        return MainReturnCode.LOOP_NO_PROMPT

    def update_all_manifests(self) -> MainReturnCode:
        if self.app_list_man is None and self.sls_man is None:
            print("This OS is not supported for this action.")
            return MainReturnCode.LOOP_NO_PROMPT
        steam_libs = get_steam_libs(self.steam_path)
        if self.app_list_man:
            applist_ids = [x.app_id for x in self.app_list_man.get_local_ids()]
        elif self.sls_man:
            applist_ids = self.sls_man.get_local_ids()
        else:
            raise Exception("Unreachable code.")

        lua_manager = LuaManager()
        downloader = ManifestDownloader(self.provider, self.steam_path)
        steam_proc = (
            SteamProcess(self.steam_path, self.app_list_man.applist_folder)
            if self.app_list_man
            else None
        )
        explored_ids: list[int] = []
        for lib in steam_libs:
            steamapps = lib / "steamapps"
            acf_files = steamapps.glob("*.acf")
            for acf_file in acf_files:
                acf = ACFParser(acf_file)
                if not acf.needs_update():
                    continue
                if acf.id not in applist_ids:
                    continue
                if acf.id in explored_ids:
                    continue
                print(
                    Fore.YELLOW + f"\n{acf.name} needs an update!\n" + Style.RESET_ALL
                )
                explored_ids.append(acf.id)
                in_backup = str(acf.id) in lua_manager.named_ids
                # TODO: DRY this
                parsed_lua = lua_manager.fetch_lua(
                    LuaChoice.ADD_LUA,
                    lua_manager.saved_lua / f"{acf.id}.lua" if in_backup else None,
                )
                if parsed_lua is None:
                    return MainReturnCode.LOOP_NO_PROMPT
                if not in_backup:
                    lua_manager.backup_lua(parsed_lua)
                print(
                    Fore.YELLOW
                    + "\nDownloading Manifests:"
                    + Style.RESET_ALL
                )
                downloader.download_manifests(parsed_lua, auto_manifest=True)
        if steam_proc:
            steam_proc.prompt_launch_or_restart()
        print(
            Fore.GREEN + "\nSuccess! All game manifests have been updated!\n"
            "Try updating them via Steam."
            + Style.RESET_ALL
        )
        return MainReturnCode.LOOP
