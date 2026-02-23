
from abc import ABC, abstractmethod
from typing import Callable, Optional, Union

from smd.prompts import prompt_confirm, prompt_select, prompt_text
from smd.steam_client import SteamInfoProvider, get_product_info
from smd.structs import AppIDInfo, AppListChoice, DepotOrAppID, LuaParsedInfo, MainReturnCode, OrganizedAppIDs, ProductInfo
from smd.utils import enter_path


class AppInjectionManager(ABC):
    def __init__(self, provider: SteamInfoProvider):
        # App ID / Depot IDs mapped to their name and type
        self.id_map: dict[int, DepotOrAppID] = {}
        self.provider = provider

    @abstractmethod
    def add_ids(
        self, data: Union[int, list[int], LuaParsedInfo], skip_check: bool = False
    ) -> None:
        pass

    @abstractmethod
    def dlc_check(self, provider: SteamInfoProvider, base_id: int) -> None:
        pass

    @abstractmethod
    def prompt_id_deletion(self):
        pass

    def prompt_add_ids(self):
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

    def display_menu(self) -> MainReturnCode:
        applist_choice: Optional[AppListChoice] = prompt_select(
            "Choose:", list(AppListChoice), cancellable=True
        )
        if applist_choice is None:
            return MainReturnCode.LOOP_NO_PROMPT
        if applist_choice == AppListChoice.DELETE:
            self.prompt_id_deletion()
        elif applist_choice == AppListChoice.ADD:
            self.prompt_add_ids()

        return MainReturnCode.LOOP_NO_PROMPT

    def tweak_last_digit(self, app_id: int):
        chars = list(str(app_id))
        chars[-1] = "0"
        return int("".join(chars))

    def _update_depot_info(self, product_info: ProductInfo):
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

    def _populate_id_map(self, app_ids: list[int]):
        """populates `self.id_map` but with an extra layer of recursion in case an ID
        has been added that does not come with the parent ID"""
        info = get_product_info(self.provider, list(app_ids))
        self._update_depot_info(info)

        still_missing: list[int] = []

        for app_id in app_ids:
            if app_id not in self.id_map:
                # There is a Depot ID in AppList without a corresponding base App ID
                still_missing.append(self.tweak_last_digit(app_id))

        if still_missing:
            info = get_product_info(self.provider, still_missing)
            self._update_depot_info(info)

    def _organize_ids(self, ids: list[int]):
        """Organize Depot IDs inside parent App IDs"""
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
        return organized

    def _menu_items_from_organized(self, organized: OrganizedAppIDs):
        """Convert organized IDs into menu items for prompt_select"""
        menu_items: list[tuple[str, int]] = []

        for app_id, info in organized.items():
            ext = "(MISSING)" if not info.exists else ""
            name = f"{app_id} - {info.name} {ext}"
            menu_items.append((name, app_id))
            depots = info.depots
            for depot in depots:
                menu_items.append((f"└──>{depot}", depot))
        return menu_items

    def _prompt_include_depots(
        self, selected_ids: set[int], organized: OrganizedAppIDs
    ):
        """Prompts to select depots related to selected parent IDs.
        Modified selected_ids in-place."""
        selected_base_ids = [
            x for x in selected_ids if x in organized and organized[x].depots
        ]
        if len(selected_base_ids) > 0:
            for app_id in selected_base_ids:
                name = organized[app_id].name
                depots = organized[app_id].depots
                if prompt_confirm(
                    f"Would you to select all Depot IDs related to {name}?",
                ):
                    selected_ids.update(depots)