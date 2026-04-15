import asyncio
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Optional
import zipfile
from colorama import Fore, Style
import httpx
import json

from smd.http_utils import get_request
from smd.strings import GITHUB_USERNAME, REPO_NAME, VERSION
from smd.utils import root_folder


class Updater:
    @staticmethod
    def get_latest_stable() -> dict[str, Any]:
        resp = None
        while resp is None:
            resp = asyncio.run(
                get_request(
                    "https://api.github.com/repos/"
                    f"{GITHUB_USERNAME}/{REPO_NAME}/releases/latest",
                    "json",
                )
            )
        return resp

    @staticmethod
    def get_latest_prerelease() -> Optional[dict[str, Any]]:
        """Returns none of prerelease newer than current version can't be found"""
        url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/releases"
        while True:
            resp = httpx.get(url)
            releases = json.loads(resp.text)
            for release in releases:
                tag = release.get("tag_name")
                if tag == VERSION:
                    return
                if release.get("prerelease") is True:
                    return release
            if "next" in resp.links:
                url = resp.links["next"]["url"]
            else:
                break

    @staticmethod
    def download_for_windows(download_url: str):
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

    @staticmethod
    def download_for_linux(download_url: str):
        axel = shutil.which("axel")
        if not axel:
            print("axel is not installed. Can't download update.")
            return
        cwd = root_folder(True)
        subprocess.run([axel, "-n", "64", download_url], cwd=cwd)
        zip_name = Path(download_url).name
        tmp_dir = cwd / "tmp"
        tmp_dir.mkdir(exist_ok=True)
        zip_path = cwd / zip_name
        tar = shutil.which("tar")
        if not tar:
            print("tar is not installed. Can't extract this archive.")
            return
        subprocess.run([tar, "-xJf", zip_path, "-C", tmp_dir])
        zip_path.unlink(missing_ok=True)
        shutil.rmtree(cwd / "_internal")
        (cwd / "SMD").unlink()
        for file in tmp_dir.iterdir():
            shutil.move(file, cwd / file.name)
        print("Update success! You may restart SMD now.")
