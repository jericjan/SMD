import subprocess
import time
from pathlib import Path

import psutil

from smd.prompts import prompt_confirm, prompt_file
from smd.storage.settings import get_setting, set_setting
from smd.structs import Settings


def is_proc_running(process_name: str):
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if process_name.lower() == proc.info["name"].lower():
                return True
        except psutil.Error:
            pass
    return False


class SteamProcess:
    def __init__(self, steam_path: Path):
        self.steam_path = steam_path
        self.exe_name = "steam.exe"
        self.wait_time = 3

    def kill(self):
        exe = self.steam_path / self.exe_name
        print("Killing Steam...", flush=True, end="")
        subprocess.run([str(exe), "-shutdown"])
        print(" Done!")

    def resolve_injector_path(self):
        if (injector_path_str := get_setting(Settings.INJECTOR_EXE)) is None:
            injector_path = prompt_file(
                "Paste the path of DLLInjector.exe "
                "(or steam.exe if you're on Stealth Mode)"
            )
            injector_path_str = str(injector_path.resolve())
            set_setting(Settings.INJECTOR_EXE, injector_path_str)
        return injector_path_str

    def prompt_launch_or_restart(self):
        if not prompt_confirm("Would like me to restart/start Steam for you?"):
            return False
        while is_proc_running(self.exe_name):
            self.kill()
            time.sleep(self.wait_time)
        injector = self.resolve_injector_path()
        print("Launching Steam...")
        subprocess.Popen(
            injector, creationflags=subprocess.DETACHED_PROCESS, shell=False,
            cwd=self.steam_path
        )
        return True
