"""For managing Greenluma's AppList folder"""

import logging
from pathlib import Path
from typing import Any, Callable, Optional, Union

from colorama import Fore, Style
from rich.console import Console
from rich.table import Table, Column
from steam.client import SteamClient  # type: ignore

from smd.http_utils import get_product_info
from smd.lua.writer import ConfigVDFWriter
from smd.manifest.downloader import ManifestDownloader
from smd.prompts import prompt_confirm, prompt_dir, prompt_select, prompt_text
from smd.storage.settings import get_setting, set_setting
from smd.structs import (
    AppIDInfo,
    AppListChoice,
    AppListFile,
    DepotOrAppID,
    DLCTypes,
    LuaParsedInfo,
    MainReturnCode,
    OrganizedAppIDs,
    ProductInfo,
    Settings,
)
from smd.utils import enter_path

logger = logging.getLogger(__name__)


class ParsedDLC:
    def __init__(self, depot_id: int, data: dict[str, Any], local_ids: list[int]):
        self.id = depot_id
        self.name: str = enter_path(data, "common", "name")
        depots = enter_path(data, "depots")
        self.release_state = enter_path(data, "common", "releasestate")
        self.type = (
            (DLCTypes.DEPOT if depots else DLCTypes.NOT_DEPOT)
            if self.release_state == "released"
            else DLCTypes.UNRELEASED
        )
        self.in_applist = True if depot_id in local_ids else False


class AppListManager:
    def __init__(self, steam_path: Path, client: SteamClient):
        self.max_id_limit = 168
        self.steam_path = steam_path
        self.client = client

        # App ID / Depot IDs mapped to their name and type
        self.id_map: dict[int, DepotOrAppID] = {}

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
        self.fix_names()

    def get_local_ids(self, sort: bool = False) -> list[AppListFile]:
        """Returns a list of tuple(path, app_id) and
        updates self.last_idx to the filename with the largest number"""
        self.last_idx = -1
        ids: list[AppListFile] = []
        for file in self.applist_folder.glob("*.txt"):
            if file.stem.isdigit():
                file_idx = int(file.stem) if file.stem.isnumeric() else -1
                if file_idx > self.last_idx:
                    self.last_idx = file_idx
            ids.append(AppListFile(file, int(file.read_text(encoding="utf-8").strip())))
        if sort:
            ids.sort(key=lambda x: int(x.path.stem))
        return ids

    def add_ids(
        self, data: Union[int, list[int], LuaParsedInfo], skip_check: bool = False
    ):
        """Adds IDs to the AppList folder"""
        if isinstance(data, int):
            app_ids = [data]
        elif isinstance(data, LuaParsedInfo):
            app_ids = [int(data.app_id), *[int(x.depot_id) for x in data.depots]]
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

    def fix_names(self):
        """Fixes filenames if they're wrong (e.g. 0.txt is missing, gap in numbering)"""
        ids = [x.path for x in self.get_local_ids(sort=True)]
        for new_idx, old_path in enumerate(ids):
            new_name = old_path.parent / f"{new_idx}.txt"
            if new_name.name != old_path.name:
                old_path.rename(new_name)

    def tweak_last_digit(self, app_id: int):
        chars = list(str(app_id))
        chars[-1] = "0"
        return int("".join(chars))

    # TODO: move this to http_utils.py?
    def get_product_info_with_retry(self, client: SteamClient, ids: list[int]):
        if not ids:
            raise ValueError("`ids` should not be empty")
        while True:
            info = get_product_info(client, ids)  # type: ignore
            if info is not None:
                return info

    def update_depot_info(self, product_info: ProductInfo):
        """Updates `self.id_map` with data from `product_info`"""
        apps_data = enter_path(product_info, "apps")

        for app_id, app_details in apps_data.items():
            assert isinstance(app_id, int)
            app_name = enter_path(app_details, "common", "name")
            depots = enter_path(app_details, "depots")

            self.id_map[app_id] = DepotOrAppID(app_name, app_id, None)

            for depot_id in depots.keys():
                if depot_id.isdigit():
                    depot_id = int(depot_id)
                    parent_id = app_id if app_id != depot_id else None
                    self.id_map[int(depot_id)] = DepotOrAppID(
                        app_name, int(depot_id), parent_id
                    )

    def prompt_id_deletion(self, client: SteamClient):
        # i'm not using set() cuz that doesn't preserve insertion order lmao
        ids = list(
            dict.fromkeys([int(x.app_id) for x in self.get_local_ids(sort=True)])
        )
        if not ids:
            print(
                "There's nothing inside the AppList folder. "
                "Try adding one manually or automatically when you "
                "add a game with the tool."
            )
            return
        info = self.get_product_info_with_retry(client, list(ids))
        self.update_depot_info(info)

        still_missing: list[int] = []

        for app_id in ids:
            if app_id not in self.id_map:
                # There is a Depot ID in AppList without a corresponding App ID
                still_missing.append(self.tweak_last_digit(app_id))

        if still_missing:
            info = self.get_product_info_with_retry(client, still_missing)
            self.update_depot_info(info)

        organized: OrganizedAppIDs = {}

        for app_id in ids:
            if app_id in self.id_map:
                item = self.id_map[app_id]
                if item.parent_id is not None:  # is a depot
                    if item.parent_id in organized:
                        info = organized[item.parent_id]
                    else:
                        info = AppIDInfo(False, item.name)
                        organized[item.parent_id] = info
                    info.depots.append(item.id)
                    if item.id == item.parent_id:
                        info.exists = True
                else:
                    if app_id in organized:
                        info = organized[app_id]
                        info.exists = True
                    else:
                        organized[app_id] = AppIDInfo(True, item.name)
            else:
                organized[app_id] = AppIDInfo(True, "UNKNOWN GAME")

        menu_items: list[tuple[str, int]] = []

        for app_id, info in organized.items():
            ext = "(MISSING)" if not info.exists else ""
            name = f"{app_id} - {info.name} {ext}"
            menu_items.append((name, app_id))
            depots = info.depots
            for depot in depots:
                menu_items.append((f"└──>{depot}", depot))

        if len(menu_items) < len(ids):
            logger.warning("There are less menu items than actual IDs inside AppList.")

        ids_to_delete: Optional[list[int]] = prompt_select(
            "Select IDs to delete from AppList:",
            menu_items,
            multiselect=True,
            long_instruction="Press Space to select items, "
            "and Enter to confirm selections. Ctrl+Z to cancel.",
            mandatory=False,
        )
        if ids_to_delete is None:
            print("No IDs selected. Doing nothing")
            return
        unique_ids = set(ids_to_delete)
        selected_base_ids = [x for x in unique_ids if x in organized]
        if len(selected_base_ids) > 0:
            for app_id in selected_base_ids:
                name = organized[app_id].name
                depots = organized[app_id].depots
                if len(depots) > 0:
                    if prompt_confirm(
                        f"Would you to select all Depot IDs related to {name}?",
                    ):
                        for x in depots:
                            unique_ids.add(x)
        self.remove_ids(list(unique_ids))

    def get_non_depot_dlcs(self, client: SteamClient, base_id: int):
        info = self.get_product_info_with_retry(client, [base_id])
        dlcs = enter_path(info, "apps", base_id, "extended", "listofdlc")
        logger.debug(f"listofdlc: {dlcs}")
        if not dlcs:
            print("This game has no DLC.")
        else:
            assert isinstance(dlcs, str)
            dlcs = [int(x) for x in dlcs.split(",")]
            dlc_info = self.get_product_info_with_retry(client, dlcs)
            config = ConfigVDFWriter(self.steam_path)
            manifest = ManifestDownloader(self.client, self.steam_path)
            if dlc_info:
                if apps := dlc_info.get("apps"):
                    unowned_non_depot_dlcs: list[int] = []
                    local_ids = [x.app_id for x in self.get_local_ids()]
                    parsed_dlcs: list[ParsedDLC] = [
                        ParsedDLC(int(depot_id), data, local_ids)
                        for depot_id, data in apps.items()
                    ]
                    depot_dlcs = [x.id for x in parsed_dlcs if x.type == DLCTypes.DEPOT]
                    key_map = config.ids_in_config(depot_dlcs)
                    manifest_map = manifest.get_dlc_manifest_status(depot_dlcs)
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

    def display_menu(self, client: SteamClient) -> MainReturnCode:
        applist_choice: Optional[AppListChoice] = prompt_select(
            "Choose:", list(AppListChoice), cancellable=True
        )
        if applist_choice is None:
            return MainReturnCode.LOOP_NO_PROMPT
        if applist_choice == AppListChoice.DELETE:
            self.prompt_id_deletion(client)
        elif applist_choice == AppListChoice.ADD:
            validator: Callable[[str], bool] = lambda x: all(
                [y.isdigit() for y in x.split()]
            )
            digit_filter: Callable[[str], list[int]] = lambda x: [
                int(y) for y in x.split()
            ]
            ids: list[int] = prompt_text(
                "Input IDs that you would like to add (separate them with spaces)",
                validator=validator,
                filter=digit_filter,
            )
            self.add_ids(ids)

        return MainReturnCode.LOOP_NO_PROMPT
