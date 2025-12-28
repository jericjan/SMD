"""SLSSteam stuff"""

import logging
from pathlib import Path
from typing import Optional, Union

from colorama import Fore, Style
from rich.console import Console
from rich.table import Column, Table

from smd.app_injector.base import AppInjectionManager
from smd.lua.writer import ConfigVDFWriter
from smd.manifest.downloader import ManifestDownloader
from smd.prompts import prompt_confirm, prompt_file
from smd.steam_client import ParsedDLC, SteamInfoProvider
from smd.storage.settings import get_setting, set_setting
from smd.storage.yaml import YAMLParser
from smd.structs import DLCTypes, LuaParsedInfo, Settings
from smd.utils import enter_path

logger = logging.getLogger(__name__)


class SLSManager(AppInjectionManager):
    def __init__(self, steam_path: Path, provider: SteamInfoProvider):
        self.steam_path = steam_path
        self.provider = provider

        saved_path = get_setting(Settings.SLS_CONFIG_LOCATION)
        self.sls_config_path = (
            (Path.home() / ".config/SLSsteam/config.yaml")
            if saved_path is None
            else Path(saved_path)
        )

        if not self.sls_config_path.exists():
            self.sls_config_path = prompt_file(
                "Could not find SLSSteam config file. "
                "Please specify the full path here:"
            )
            set_setting(
                Settings.SLS_CONFIG_LOCATION, str(self.sls_config_path.absolute())
            )
        elif saved_path is None:
            colorized = (
                Fore.YELLOW + str(self.sls_config_path.resolve()) + Style.RESET_ALL
            )
            print(
                f"SLSSteam config file automatically selected: {colorized}\n"
                "Change this in settings if it's the wrong folder."
            )
            set_setting(
                Settings.SLS_CONFIG_LOCATION, str(self.sls_config_path.absolute())
            )

    def get_local_ids(self) -> list[int]:
        parser = YAMLParser(self.sls_config_path)
        data = parser.read()
        return data.get("AdditionalApps", [])

    def add_ids(
        self, data: Union[int, list[int], LuaParsedInfo], skip_check: bool = False
    ):
        parser = YAMLParser(self.sls_config_path)
        yaml_data = parser.read()
        app_ids = yaml_data.get("AdditionalApps", [])
        changes = 0
        if isinstance(data, int):
            data = [data]
        if isinstance(data, LuaParsedInfo):
            data = [int(x.depot_id) for x in data.depots]
        for new_app_id in data:
            if new_app_id not in app_ids:
                print(f"{new_app_id} added to SLSSteam config.")
                app_ids.append(new_app_id)
                changes += 1
            else:
                print(f"{new_app_id} already in SLSSteam config.")

        if changes > 0:
            parser.write(yaml_data)

    def dlc_check(self, provider: SteamInfoProvider, base_id: int) -> None:
        print("Checking for DLC...")
        base_info = provider.get_single_app_info(base_id)
        dlcs = enter_path(base_info, "extended", "listofdlc")
        logger.debug(f"listofdlc: {dlcs}")
        if not dlcs:
            print("This game has no DLC.")
        else:
            assert isinstance(dlcs, str)
            dlcs = [int(x) for x in dlcs.split(",")]
            dlc_info = provider.get_app_info(dlcs)
            config = ConfigVDFWriter(self.steam_path)
            manifest = ManifestDownloader(self.provider, self.steam_path)
            if dlc_info:
                unowned_non_depot_dlcs: list[int] = []
                local_ids = self.get_local_ids()
                parsed_dlcs: list[ParsedDLC] = [
                    ParsedDLC(int(depot_id), data, base_info, local_ids)
                    for depot_id, data in dlc_info.items()
                ]
                depot_dlcs = [x.id for x in parsed_dlcs if x.type == DLCTypes.DEPOT]
                key_map = config.ids_in_config(depot_dlcs)
                manifest_map = (
                    manifest.get_dlc_manifest_status(depot_dlcs) if depot_dlcs else {}
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
