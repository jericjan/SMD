import hashlib
import re
import shutil
import subprocess
from pathlib import Path

import pyperclip

from utils import prompt_select, root_folder


class GameCracker:
    def __init__(self, library_path: Path):
        self.games_path = library_path / "steamapps/common"

    def get_game(self) -> Path:
        paths: list[Path] = []
        for path in self.games_path.iterdir():
            if path.is_dir():
                paths.append(path)
        return prompt_select("Select a game", [(x.name, x) for x in paths], fuzzy=True)

    def find_steam_dll(self, game_path: Path) -> Path:
        files = list(game_path.rglob("steam_api*.dll"))
        if len(files) > 1:
            return prompt_select(
                "More than one DLL found. Pick one:", [(x.name, x) for x in files]
            )
        return files[0]

    def crack_dll(self, dll_path: Path):
        valid_app_id = re.compile(r"(?:(?=store\.steampowered.com\/app\/)\d+)|\d+")
        while True:
            app_id = input("Enter app id or steam page link: ").strip()
            if match := valid_app_id.search(app_id):
                app_id = match.group()
                print(f"App ID is {app_id}")
                break
            else:
                print("Incorrect format. Try again.")

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
        (api_folder / "steam_appid.txt").write_text(app_id, "utf-8")

        gse_app_folder = Path.home() / f"AppData/Roaming/GSE Saves/{app_id}"

        if not gse_app_folder.exists():
            print("GSE Saves folder doesn't exist. Creating...")
            gse_app_folder.mkdir()

        backup_name = dll_path.parent / ("OG_" + dll_path.name)
        if backup_name.exists():
            backup_name.unlink()
        dll_path.rename(backup_name)

        shutil.copytree(gbe_fork_folder, api_folder, dirs_exist_ok=True)

        # TODO: this sucks btw
        if "64" in dll_path.name:
            (api_folder / "steam_api.dll").unlink()
        else:  # 32
            (api_folder / "steam_api64.dll").unlink()

        pyperclip.copy(str(api_folder.absolute()))
        print(
            "API folder has been copied to clipboard. "
            "Use a tool like Achievement Watcher to generate it."
        )

    def apply_steamless(self, game_path: Path):
        steamless_exe = root_folder() / "third_party/steamless/Steamless.CLI.exe"
        subprocess.run(["explorer", game_path])
        while True:
            game_exe = Path(
                input("Drag the game .exe here and press Enter: ").strip("\"'")
            )
            if not game_exe.exists():
                print("Doesn't exist. Try again")
            break
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
            print("Steamtools failed...")
