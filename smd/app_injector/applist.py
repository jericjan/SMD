"""For managing Greenluma's AppList folder"""

import logging
from collections import defaultdict
from pathlib import Path
from typing import Optional, Union

from colorama import Fore, Style
from rich.console import Console
from rich.table import Column, Table

from smd.app_injector.base import AppInjectionManager
from smd.lua.writer import ConfigVDFWriter
from smd.manifest.downloader import ManifestDownloader
from smd.prompts import prompt_confirm, prompt_dir, prompt_select
from smd.steam_client import ParsedDLC, SteamInfoProvider, get_product_info
from smd.storage.settings import get_setting, set_setting
from smd.structs import (
    AppListPathAndID,
    DLCTypes,
    LuaParsedInfo,
    Settings,
)
from smd.utils import enter_path

logger = logging.getLogger(__name__)


class AppListManager(AppInjectionManager):
    def __init__(self, steam_path: Path, provider: SteamInfoProvider):
        super().__init__(provider)
        self.max_id_limit = 134
        self.steam_path = steam_path

        saved_applist = get_setting(Settings.APPLIST_FOLDER)
        self.applist_folder = (
            steam_path / "AppList" if saved_applist is None else Path(saved_applist)
        )

        if not self.applist_folder.exists():
            self.applist_folder = prompt_dir(
                "Could not find AppList folder. " "Please specify the full path here:"
            )
            set_setting(Settings.APPLIST_FOLDER, str(self.applist_folder.absolute()))
        elif saved_applist is None:
            colorized = (
                Fore.YELLOW + str(self.applist_folder.resolve()) + Style.RESET_ALL
            )
            print(
                f"AppsList folder automatically selected: {colorized}\n"
                "Change this in settings if it's the wrong folder."
            )
            set_setting(Settings.APPLIST_FOLDER, str(self.applist_folder.absolute()))

        if saved_applist:
            colorized = (
                Fore.YELLOW + str(self.applist_folder.resolve()) + Style.RESET_ALL
            )
            print(f"Your AppList folder is {colorized}")
            print(
                Fore.LIGHTBLACK_EX
                + "If you are using Stealth Mode (Any folder), make sure"
                " this points to the folder you put GreenLuma in" + Style.RESET_ALL
            )
        self.fix_names()

    def get_local_filenames(self, sort: bool = False) -> list[Path]:
        """get_local_ids but just filenames and no last_idx editing"""
        files: list[Path] = []
        for file in self.applist_folder.glob("*.txt"):
            if not file.stem.isdigit():
                logger.debug(f"[get_local_filenames] Ignored {file.name}")
                continue
            files.append(file)
        if sort:
            files.sort(key=lambda x: int(x.stem) if x.stem.isnumeric() else -1)
        return files

    def get_local_ids(self, sort: bool = False) -> list[AppListPathAndID]:
        """Returns a list of tuple(path, app_id) and
        updates self.last_idx to the filename with the largest number"""
        self.last_idx = -1
        ids: list[AppListPathAndID] = []
        for file in self.applist_folder.glob("*.txt"):
            if not file.stem.isdigit():
                logger.debug(f"[get_local_ids] Ignored {file.name}")
                continue
            file_idx = int(file.stem)
            if file_idx > self.last_idx:
                self.last_idx = file_idx

            contents = file.read_text(encoding="utf-8").strip()

            if contents.isnumeric():
                appid = int(contents)
            else:
                raise Exception(
                    f"{file.name} does not contain a "
                    "number. Text files in AppList should only contain the number "
                    "of their App ID. Please fix this and launch SMD again."
                )
            ids.append(AppListPathAndID(file, appid))
        if sort:
            ids.sort(key=lambda x: int(x.path.stem) if x.path.stem.isnumeric() else -1)
        return ids

    def add_ids(
        self, data: Union[int, list[int], LuaParsedInfo], skip_check: bool = False
    ):
        """Adds IDs to the AppList folder"""
        if isinstance(data, int):
            app_ids = [data]
        elif isinstance(data, LuaParsedInfo):
            app_ids = [int(x.depot_id) for x in data.depots]
        else:
            app_ids = data

        local_ids = [] if skip_check else [x.app_id for x in self.get_local_ids()]
        for app_id in app_ids:
            if app_id in local_ids:
                print(f"{app_id} already in AppList")
                continue
            new_idx = self.last_idx + 1
            with (self.applist_folder / f"{new_idx}.txt").open("w") as f:
                f.write(str(app_id))
            self.last_idx = new_idx
            id_count = new_idx + 1
            print(
                f"{app_id} added to AppList. " f"There are now {id_count} IDs stored."
            )
            if id_count > self.max_id_limit:
                print(
                    Fore.RED + f"WARNING: You've hit the {self.max_id_limit} ID limit "
                    "for Greenluma. "
                    "I haven't implemented anything to deal with this yet."
                    + Style.RESET_ALL
                )

    def remove_ids(self, ids_to_delete: list[int]):
        """became unused and replaced with delete_paths"""
        local_ids = self.get_local_ids(sort=True)
        remaining_ids = [*local_ids]
        for local_id in local_ids:
            if local_id.app_id in ids_to_delete:
                local_id.path.unlink(missing_ok=True)
                remaining_ids.remove(local_id)
                print(f"{local_id.path.name} deleted")
        for new_idx, remaining_id in enumerate(remaining_ids):
            new_name = remaining_id.path.parent / f"{new_idx}.txt"
            if remaining_id.path.name != new_name.name:
                remaining_id.path.rename(new_name)

    def delete_paths(self, paths_to_delete: list[Path], all_paths: list[Path]):
        """Deletes all paths_to_delete and renames remaining files.
        Assumes all_paths is already sorted in ascending order"""
        remaining_paths = [*all_paths]
        for path in paths_to_delete:
            path.unlink(missing_ok=True)
            remaining_paths.remove(path)
            print(f"{path.name} deleted")
        for new_idx, path in enumerate(remaining_paths):
            new_name = path.parent / f"{new_idx}.txt"
            if path.name != new_name.name:
                path.rename(new_name)

    def fix_names(self):
        """Fixes filenames if they're wrong (e.g. 0.txt is missing, gap in numbering)"""
        ids = self.get_local_filenames(sort=True)
        for new_idx, old_path in enumerate(ids):
            new_name = old_path.parent / f"{new_idx}.txt"
            if new_name.name != old_path.name:
                old_path.rename(new_name)

    def _get_paths_from_ids(
        self, app_ids: set[int], path_and_ids: list[AppListPathAndID]
    ):
        """Converts IDs to Paths"""
        file_map: defaultdict[int, list[Path]] = defaultdict(list)
        # app id mapped to files that have that ID
        for x in path_and_ids:
            file_map[x.app_id].append(x.path)
        paths_to_delete: list[Path] = []
        for app_id in app_ids:
            for path in file_map[app_id]:
                paths_to_delete.append(path)
        return paths_to_delete

    def prompt_id_deletion(self):
        """Show all AppList IDs and let the user delete them"""

        path_and_ids = self.get_local_ids(sort=True)
        if not path_and_ids:
            print(
                "There's nothing inside the AppList folder. "
                "Try adding one manually or automatically when you "
                "add a game with the tool."
            )
            return

        # i'm not using set() cuz that doesn't preserve insertion order lmao
        local_ids = list(dict.fromkeys([int(x.app_id) for x in path_and_ids]))

        self._populate_id_map(local_ids)

        organized = self._organize_ids(local_ids)

        # list of tuple(app name, app id)
        menu_items = self._menu_items_from_organized(organized)
        if len(menu_items) < len(local_ids):
            logger.warning("There are less menu items than actual IDs inside AppList.")

        ids_to_delete_list: Optional[list[int]] = prompt_select(
            "Select IDs to delete from AppList:",
            menu_items,
            multiselect=True,
            long_instruction="Press Space to select items, "
            "and Enter to confirm selections. Ctrl+Z to cancel.",
            mandatory=False,
        )
        if ids_to_delete_list is None:
            print("No IDs selected. Doing nothing")
            return
        ids_to_delete = set(ids_to_delete_list)
        self._prompt_include_depots(ids_to_delete, organized)

        paths_to_delete = self._get_paths_from_ids(ids_to_delete, path_and_ids)
        all_paths = [x.path for x in path_and_ids]
        self.delete_paths(paths_to_delete, all_paths)

    def dlc_check(self, provider: SteamInfoProvider, base_id: int):
        print("Checking for DLC...")
        base_info = get_product_info(provider, [base_id])
        base_info_trimmed = enter_path(base_info, "apps", base_id)
        dlcs = enter_path(base_info_trimmed, "extended", "listofdlc")
        logger.debug(f"listofdlc: {dlcs}")
        if not dlcs:
            print("This game has no DLC.")
        else:
            assert isinstance(dlcs, str)
            dlcs = [int(x) for x in dlcs.split(",")]
            dlc_info = get_product_info(provider, dlcs)
            config = ConfigVDFWriter(self.steam_path)
            manifest = ManifestDownloader(self.provider, self.steam_path)
            if dlc_info:
                if apps := dlc_info.get("apps"):
                    unowned_non_depot_dlcs: list[int] = []
                    local_ids = [x.app_id for x in self.get_local_ids()]
                    parsed_dlcs: list[ParsedDLC] = [
                        ParsedDLC(int(depot_id), data, base_info_trimmed, local_ids)
                        for depot_id, data in apps.items()
                    ]
                    depot_dlcs = [x.id for x in parsed_dlcs if x.type == DLCTypes.DEPOT]
                    key_map = config.ids_in_config(depot_dlcs)
                    manifest_map = (
                        manifest.get_dlc_manifest_status(depot_dlcs)
                        if depot_dlcs
                        else {}
                    )
                    non_depot_dlc_count = 0
                    console = Console()
                    table = Table(
                        "ID",
                        "Name",
                        "Type",
                        Column(header="In AppList?", justify="center"),
                        Column(header="Has Key?", justify="center"),
                        Column(header="Has Manifest?", justify="center"),
                    )
                    bool_map: dict[Optional[bool], str] = {
                        True: "[green]O[/green]",
                        False: "[red]X[/red]",
                        None: "N/A",
                    }
                    for dlc in parsed_dlcs:
                        if dlc.type == DLCTypes.NOT_DEPOT:
                            non_depot_dlc_count += 1
                            if not dlc.in_applist:
                                unowned_non_depot_dlcs.append(dlc.id)
                        table.add_row(
                            str(dlc.id),
                            dlc.name,
                            dlc.type.value,
                            bool_map[dlc.in_applist],
                            bool_map[key_map.get(dlc.id)],
                            bool_map[manifest_map.get(dlc.id)],
                        )
                    console.print(table)
                    print(
                        Fore.YELLOW + "NOTE: Pre-installed DLCs don't need "
                        "decryption key & manifest\n"
                        "Keys and manifests are only required "
                        "when you don't have the DLC downlaoded yet." + Style.RESET_ALL
                    )
                    if len(unowned_non_depot_dlcs) > 0:
                        print(
                            "This game has pre-installed DLCs that aren't "
                            "in the AppList."
                        )
                        if prompt_confirm("Do you want to add these to the AppList?"):
                            self.add_ids(unowned_non_depot_dlcs, skip_check=False)
                    elif len(unowned_non_depot_dlcs) == 0 and non_depot_dlc_count > 0:
                        print("All pre-installed DLCs are already enabled.")
                    elif non_depot_dlc_count == 0:
                        print(
                            "This game has no pre-installed DLCs :(\n"
                            "You'll have to find a lua that has "
                            "decryption keys for them."
                        )
