import re
import subprocess
import tempfile
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from typing import cast
from zipfile import ZipFile

from colorama import Fore, Style
from InquirerPy.base.control import Choice
from pathvalidate import sanitize_filename

from smd.http_utils import get_game_name
from smd.prompts import prompt_dir, prompt_file, prompt_select
from smd.storage.settings import get_or_compute_setting
from smd.structs import LuaParsedInfo
from smd.ui.settings.types import Settings
from smd.zip import BytesIOZip


class KeyExtractor:
    """handles parsing of decryptions keys from lua files"""

    def __init__(self, pattern: str):
        self.pattern = re.compile(pattern, re.MULTILINE)

    def extract_keys(self, content: str) -> list[tuple[str, str]]:
        return self.pattern.findall(content)

    def write_keys_file(self, keys: list[tuple[str, str]], output_path: Path) -> None:
        lines = [f"{depot};{key}\n" for depot, key in keys]
        output_path.write_text("".join(lines), encoding="utf-8")


class DepotDownloaderMod:
    def __init__(self, exe_path: Path, keys_path: Path):
        self.exe_path = exe_path
        self.keys_path = keys_path

    def run(
        self, manifest_path: Path, depot_id: str, app_id: str, target_dir: Path
    ) -> None:
        match = re.search(r"_(\d+)$", manifest_path.stem)
        if not match:
            print(
                f"ERROR: Could not get manifest ID from filename {manifest_path.stem}"
            )
            return
        manifest_id = match.group(1)
        cmd: list[str] = [
            str(self.exe_path),
            "-app",
            app_id,
            "-depot",
            depot_id,
            "-depotkeys",
            str(self.keys_path),
            "-manifest",
            manifest_id,
            "-manifestfile",
            str(manifest_path),
            "-dir",
            str(target_dir),
        ]
        print(Fore.CYAN)
        subprocess.run(cmd, check=True)
        print(Style.RESET_ALL)


def is_not_file(path: str):
    return not Path(path).is_file()


def process_zip(
    zip_path: Path | BytesIO,
    exe_path: Path,
    base_id: str,
    lib_path: Path | None = None,
    target_dir_transformer: Callable[[Path], Path] | None = None,
) -> None:
    lua_pattern = (
        r"^\s*addappid\s*\(\s*(\d+)\s*,\s*\d\s*,\s*(?:\"|')\s*(\S+)\s*(?:\"|')"
    )
    game_name = sanitize_filename(get_game_name(base_id)).replace("'", "")
    extractor = KeyExtractor(lua_pattern)

    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        manifest_files: list[Path] = []
        lua_file = None

        with ZipFile(zip_path, "r") as archive:
            for file_info in archive.infolist():
                suffix = Path(file_info.filename).suffix.lower()
                if suffix in (".manifest", ".lua"):
                    extracted_path = Path(archive.extract(file_info, temp_dir))
                    if suffix == ".manifest":
                        manifest_files.append(extracted_path)
                    elif suffix == ".lua":
                        # TODO: handle >1 lua file
                        lua_file = extracted_path

        if not lua_file:
            raise FileNotFoundError("no .lua file found inside the zip archive")

        keys_path = temp_dir / "depot.keys"
        keys = extractor.extract_keys(lua_file.read_text(encoding="utf-8"))
        extractor.write_keys_file(keys, keys_path)

        execution_queue: list[tuple[Path, str, str]] = []
        # TODO: manifest selection should have been before the user started to download manifests, not here

        manifest_files = (
            prompt_select(
                "Pick manifests to download from (Space = Select, Enter = Confirm)",
                [Choice(x, x.name, enabled=True) for x in manifest_files],
                multiselect=True,
            )
            if len(manifest_files) > 1
            else manifest_files
        )
        if lib_path:
            out_dir = lib_path / "steamapps/common"
        else:
            out_dir = get_or_compute_setting(
                Settings.DDM_OUTPUT_DIR,
                lambda: prompt_dir(
                    "Enter master path to download the game (or workshop item) to. This will be used for future downloads for various games."
                ),
            )
            out_dir = Path(cast(str, out_dir))
        for manifest in manifest_files:
            match = re.search(r"\d+", manifest.name)
            if not match:
                raise ValueError(f"invalid manifest filename: {manifest.name}")

            depot_id = match.group(0)
            guessed_id = f"{depot_id[:-1]}0"

            print(f"\n[Manifest File]: {manifest.name}")
            print(f"Predicted App ID: {guessed_id}")
            user_val = input(
                "Press ENTER to confirm, or type the correct App ID: "
            ).strip()
            app_id = user_val if user_val else guessed_id

            execution_queue.append((manifest, depot_id, app_id))

        downloader = DepotDownloaderMod(exe_path, keys_path)
        folder_name = game_name if lib_path else f"{base_id} - {game_name}"
        target_dir = out_dir / folder_name
        if target_dir_transformer:
            target_dir = target_dir_transformer(target_dir)
        for manifest, depot_id, app_id in execution_queue:
            downloader.run(manifest, depot_id, app_id, target_dir)
        print(Fore.GREEN + f"Game downloaded to {target_dir} !" + Style.RESET_ALL)


def run_ddm(
    parsed_lua: LuaParsedInfo,
    manifests: list[Path],
    lib_path: Path | None = None,
    target_dir_transformer: Callable[[Path], Path] | None = None,
):
    print(Fore.YELLOW + "\nDownloading game via DDM:" + Style.RESET_ALL)
    b_zip = BytesIOZip()
    b_zip.prepare_local_file(manifests)
    b_zip.prepare_str_file(f"{parsed_lua.app_id}.lua", parsed_lua.contents)
    b_zip.write()

    exe_path = get_or_compute_setting(
        Settings.DDM_PATH,
        lambda: prompt_file("Enter absolute path to DepotDownloaderMod.exe: "),
    )
    exe_path = Path(cast(str, exe_path))
    if not exe_path.exists():
        print("Error: DDM executable not found.")
        return

    try:
        process_zip(
            b_zip.file, exe_path, parsed_lua.app_id, lib_path, target_dir_transformer
        )
    except Exception as e:
        print(f"An error occurred: {e}")
