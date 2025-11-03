import shutil
from dataclasses import dataclass
from pathlib import Path

from pathvalidate import sanitize_filename

from smd.http_utils import get_game_name
from smd.prompts import prompt_select
from smd.storage.vdf import VDFLoadAndDumper, vdf_dump
from smd.structs import LuaParsedInfo
from smd.utils import enter_path


@dataclass
class ACFWriter:
    steam_lib_path: Path

    def write_acf(self, lua: LuaParsedInfo):
        acf_file = self.steam_lib_path / f"steamapps/appmanifest_{lua.app_id}.acf"
        do_write_acf = True
        if acf_file.exists():
            do_write_acf = prompt_select(
                ".acf file found. Is this an update?",
                [("Yes", False), ("No", True)],
            )

        if do_write_acf:
            app_name = get_game_name(lua.app_id)
            acf_contents: dict[str, dict[str, str]] = {
                "AppState": {
                    "AppID": lua.app_id,
                    "Universe": "1",
                    "name": app_name,
                    "installdir": sanitize_filename(app_name),
                    "StateFlags": "4",
                }
            }
            vdf_dump(acf_file, acf_contents)
            print(f"Wrote .acf file to {acf_file}")
        else:
            print("Skipped writing to .acf file")


@dataclass
class ConfigVDFWriter:
    steam_path: Path

    def add_decryption_keys_to_config(self, lua: LuaParsedInfo):
        """Adds decryption keys from parsed lua to config.vdf"""
        vdf_file = self.steam_path / "config/config.vdf"
        shutil.copyfile(vdf_file, (self.steam_path / "config/config.vdf.backup"))
        with VDFLoadAndDumper(vdf_file) as vdf_data:
            for pair in lua.depots:
                depot_id = pair.depot_id
                dec_key = pair.decryption_key
                print(f"Depot {depot_id} has decryption key {dec_key}...", end="")
                depots = enter_path(
                    vdf_data,
                    "InstallConfigStore",
                    "Software",
                    "Valve",
                    "Steam",
                    "depots",
                    mutate=True,
                    ignore_case=True
                )
                if depot_id not in depots:
                    depots[depot_id] = {"DecryptionKey": dec_key}
                    print("Added to config.vdf succesfully.")
                else:
                    print("Already in config.vdf.")
