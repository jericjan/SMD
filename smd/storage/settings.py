from pathlib import Path
from typing import Any, Union, cast

import msgpack  # type: ignore

from smd.secret_store import keyring_decrypt, keyring_encrypt
from smd.structs import Settings

SETTINGS_FILE = Path.cwd() / "settings.bin"


def load_all_settings() -> dict[Any, Any]:
    """Returns all saved settings as a dict"""
    SETTINGS_FILE.touch(exist_ok=True)
    with SETTINGS_FILE.open("rb") as f:
        try:
            settings = cast("dict[Any, Any]", msgpack.unpackb(f.read()))  # type: ignore
        except ValueError:
            settings: dict[Any, Any] = {}
    return settings


def get_setting(key: Settings):
    value = load_all_settings().get(key.key_name)
    return keyring_decrypt(value) if (value and key.hidden) else value


def set_setting(key: Settings, value: Union[str, bool]):
    settings = load_all_settings()
    settings[key.key_name] = (
        keyring_encrypt(value) if key.hidden and isinstance(value, str) else value
    )
    with SETTINGS_FILE.open("wb") as f:
        f.write(msgpack.packb(settings))  # type: ignore
