from enum import IntFlag
from pathlib import Path
from typing import Optional

from smd.storage.vdf import vdf_load
from smd.utils import enter_path


class AppState(IntFlag):
    StateInvalid = 0
    StateUninstalled = 1
    StateUpdateRequired = 2
    StateFullyInstalled = 4
    StateEncrypted = 8
    StateLocked = 16
    StateFilesMissing = 32
    StateAppRunning = 64
    StateFilesCorrupt = 128
    StateUpdateRunning = 256
    StateUpdatePaused = 512
    StateUpdateStarted = 1024
    StateUninstalling = 2048
    StateBackupRunning = 4096
    StateReconfiguring = 65536
    StateValidating = 131072
    StateAddingFiles = 262144
    StatePreallocating = 524288
    StateDownloading = 1048576
    StateStaging = 2097152
    StateCommitting = 4194304
    StateUpdateStopping = 8388608


class ACFParser:
    def __init__(self, acf: Path):
        self.data = vdf_load(acf)
        self._name: Optional[str] = None
        self._id: Optional[int] = None
        self._state: Optional[AppState] = None

    @property
    def name(self):
        if self._name is None:
            raw_name: Optional[str] = enter_path(
                self.data, "AppState", "name", default=None
            )
            self._name = raw_name
        return self._name

    @property
    def id(self):
        if self._id is None:
            raw_id: Optional[str] = enter_path(
                self.data, "AppState", "appid", default=None
            )
            if raw_id and raw_id.isdigit():
                self._id = int(raw_id)
        return self._id

    @property
    def state(self):
        if self._state is None:
            raw_state: Optional[str] = enter_path(
                self.data, "AppState", "StateFlags", default=None
            )
            if raw_state and raw_state.isdigit():
                self._state = AppState(int(raw_state))
        return self._state

    def needs_update(self):
        state = self.state
        if state and AppState.StateUpdateRequired in state:
            return True
        return False
