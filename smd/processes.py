import subprocess
import time
from pathlib import Path

import psutil

from smd.prompts import prompt_confirm


def is_proc_running(process_name: str):
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if process_name.lower() == proc.info["name"].lower():
                return True
        except psutil.Error:
            pass
    return False


class SteamProcess:
    def __init__(self, steam_path: Path, applist_folder: Path):
        self.steam_path = steam_path
        self.injector_dir = applist_folder.parent
        self.exe_name = "steam.exe"
        self.wait_time = 3

    def kill(self):
        exe = self.steam_path / self.exe_name
        print("Killing Steam...", flush=True, end="")
        subprocess.run([str(exe), "-shutdown"])
        print(" Done!")

    def resolve_injector_path(self):
        candidates = ["DLLInjector.exe", "steam.exe"]
        matches = [
            x for x in map(lambda x: (self.injector_dir / x), candidates) if x.exists()
        ]
        if len(matches) == 1:
            return str(matches[0].resolve())
        if len(matches) == 0:
            return None
        print(f"The following were found: {', '.join(x.name for x in matches)}")
        if prompt_confirm("Is your GreenLuma installation in Normal Mode right now?"):
            return str(matches[0].resolve())
        renamed_path = matches[0].parent / (matches[0].name + ".backup")
        matches[0].rename(renamed_path)
        print(
            "You must be in stealth mode then. "
            f"You shouldn't leave {candidates[0]} in that folder! I've renamed it "
            f"to {renamed_path.name} for you."
        )
        return str(matches[1].resolve())

    def prompt_launch_or_restart(self):
        if not prompt_confirm("Would like me to restart/start Steam for you?"):
            return False
        while is_proc_running(self.exe_name):
            self.kill()  # TODO: run kill command once and just continuosly wait
            time.sleep(self.wait_time)
        injector = self.resolve_injector_path()
        if injector is None:
            print("Could not find any matching executables. Launch it yourself.")
            return
        print("Launching Steam...")
        subprocess.Popen(
            injector, creationflags=subprocess.DETACHED_PROCESS, shell=False,
            cwd=self.steam_path
        )
        return True
