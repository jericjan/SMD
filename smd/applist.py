"""For managing Greenluma's AppList folder"""

from pathlib import Path
from typing import Callable, Optional, Union

from colorama import Fore, Style
from steam.client import SteamClient  # type: ignore

from smd.http_utils import get_product_info
from smd.prompts import prompt_dir, prompt_select, prompt_text
from smd.storage.settings import get_setting, set_setting
from smd.structs import (
    AppListChoice,
    AppListFile,
    DepotOrAppID,
    LuaParsedInfo,
    MainReturnCode,
    OrganizedAppIDs,
    ProductInfo,
    Settings,
)
from smd.utils import enter_path


class AppListManager:
    def __init__(self, steam_path: Path):
        self.max_id_limit = 168
        self.steam_path = steam_path
        self.last_idx = 0

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

    def get_local_ids(self, sort: bool = False) -> list[AppListFile]:
        ids: list[AppListFile] = []
        for file in self.applist_folder.glob("*.txt"):
            if file.stem.isdigit():
                if int(file.stem) > self.last_idx:
                    self.last_idx = int(file.stem)
            ids.append(AppListFile(file, int(file.read_text(encoding="utf-8").strip())))
        if sort:
            ids.sort(key=lambda x: int(x.path.stem))
        return ids

    def add_ids(self, app_ids: Union[int, list[int], LuaParsedInfo]):
        """Adds IDs to the AppList folder"""
        if isinstance(app_ids, int):
            app_ids = [app_ids]
        if isinstance(app_ids, LuaParsedInfo):
            app_ids = [int(app_ids.app_id), *[int(x.depot_id) for x in app_ids.depots]]
        for app_id in app_ids:
            local_ids = [x.app_id for x in self.get_local_ids()]
            if app_id not in local_ids:
                new_idx = self.last_idx + 1
                with (self.applist_folder / f"{new_idx}.txt").open("w") as f:
                    f.write(str(app_id))
                self.last_idx = new_idx
                print(
                    f"{app_id} added to AppList. "
                    f"There are now {len(local_ids) + 1} IDs stored."
                )
                if (len(local_ids) + 1) > self.max_id_limit:
                    print(
                        Fore.RED
                        + f"WARNING: You've hit the {self.max_id_limit} ID limit "
                        "for Greenluma. "
                        "I haven't implemented anything to deal with this yet."
                        + Style.RESET_ALL
                    )
            else:
                print(f"{app_id} already in AppList")

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

    def tweak_last_digit(self, app_id: int):
        chars = list(str(app_id))
        chars[-1] = "0"
        return int("".join(chars))

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
            app_name = enter_path(app_details, "common", "name")
            depots = enter_path(app_details, "depots")

            self.id_map[int(app_id)] = DepotOrAppID(app_name, app_id, None)

            for depot_id in depots.keys():
                if depot_id.isdigit():
                    self.id_map[int(depot_id)] = DepotOrAppID(
                        app_name, depot_id, app_id
                    )

    def prompt_id_deletion(self, client: SteamClient):
        ids = [int(x.app_id) for x in self.get_local_ids()]
        if not ids:
            print(
                "There's nothing inside the AppList folder. "
                "Try adding one manually or automatically when you "
                "add a game with the tool."
            )
            return
        info = self.get_product_info_with_retry(client, ids)
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
                    app = enter_path(
                        organized,
                        item.parent_id,
                        mutate=True,
                    )
                    app.setdefault("depots", []).append(item.id)
                    if "exists" not in app:
                        app["exists"] = False
                        app["name"] = item.name
                else:
                    app = enter_path(organized, app_id, mutate=True)
                    app["exists"] = True
                    app["name"] = item.name
            else:
                organized[app_id] = {"exists": True, "name": "UNKNOWN GAME"}

        menu_items: list[tuple[str, int]] = []

        for app_id, val in organized.items():
            ext = "(MISSING)" if not val.get("exists") else ""
            name = f"{app_id} - {val.get('name')} {ext}"
            menu_items.append((name, app_id))
            depots = val.get("depots")
            if depots:
                for depot in depots:
                    menu_items.append((f"└──>{depot}", int(depot)))
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
                name = organized[app_id]["name"]
                depots = organized[app_id].get("depots")
                if depots:
                    select_children: bool = prompt_select(
                        f"Would you to select all Depot IDs related to {name}?",
                        [("Yes", True), ("No", False)],
                    )
                    if select_children:
                        for x in depots:
                            unique_ids.add(int(x))
        self.remove_ids(list(unique_ids))

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
