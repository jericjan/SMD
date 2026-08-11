import re
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path
from typing import cast
from zipfile import ZipFile

from InquirerPy.base.control import Choice

from smd.prompts import prompt_dir, prompt_file, prompt_select
from smd.storage.settings import get_or_compute_setting
from smd.ui.settings.types import Settings


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
        subprocess.run(cmd, check=True)


def is_not_file(path: str):
    return not Path(path).is_file()


def process_zip(zip_path: Path | BytesIO, exe_path: Path, base_id: str) -> None:
    lua_pattern = (
        r"^\s*addappid\s*\(\s*(\d+)\s*,\s*\d\s*,\s*(?:\"|')\s*(\S+)\s*(?:\"|')"
    )
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
        manifest_files = prompt_select(
            "Pick manifests to download from (Space = Select, Enter = Confirm)",
            [Choice(x, x.name, enabled=True) for x in manifest_files],
            multiselect=True,
        )
        out_dir = get_or_compute_setting(
            Settings.DDM_OUTPUT_DIR,
            lambda: prompt_dir(
                "Enter master path to download the game to. This will be used for future downloads for various games."
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
        for manifest, depot_id, app_id in execution_queue:
            downloader.run(manifest, depot_id, app_id, out_dir / base_id)


def run_ddm_helper(zip_path: Path | BytesIO, app_id: str) -> None:

    exe_path = get_or_compute_setting(
        Settings.DDM_PATH,
        lambda: prompt_file("Enter absolute path to DepotDownloaderMod.exe: "),
    )
    exe_path = Path(cast(str, exe_path))
    if not exe_path.exists():
        print("Error: DDM executable not found.")
        return

    try:
        process_zip(zip_path, exe_path, app_id)
        print("\nProcessing completed successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")
