from collections.abc import Callable
from enum import Enum, auto
from typing import Any, NamedTuple


class SettingOperations(Enum):
    EDIT = "Edit"
    DELETE = "Delete"


class SettingCustomTypes(Enum):
    DIR = auto()
    FILE = auto()


SettingType = type | list[Enum] | SettingCustomTypes


class SettingItem(NamedTuple):
    key_name: str
    "The key name of the setting (used in the savefile)"
    clean_name: str
    "The name of the setting as displayed in the Settings menu"
    hidden: bool
    "Whether the item is hidden (e.g. sensitive info)"
    type: SettingType
    "Type of the setting"
    description: str | list[tuple[str, str]]
    "Description of the setting"


class AchievementGenMode(Enum):
    STABLE = "Stable"
    EXPERIMENTAL = "Experimental"


class GreenLumaVersions(Enum):
    """These are the keynames in HKCU\\SOFTWARE\\"""

    GLR = "GLR"
    GL2020 = "GL2020"
    GL2024 = "GL2024"
    GL2025 = "GL2025"

    def __str__(self):
        return self.value


# Note: values are only obtained through get_setting() in utils.py
class Settings(Enum):
    ADVANCED_MODE = SettingItem(
        "advanced_mode",
        "Advanced Mode",
        False,
        bool,
        "Adds extra options to the main menu.",
    )
    MORRENUS_KEY = SettingItem(
        "morrenus_key",
        "Morrenus API Key",
        True,
        str,
        "Also known as Hubcap. This is required if you want to use their endpoint.",
    )
    STEAM_PATH = SettingItem(
        "steam_path",
        "Steam Installation Path",
        False,
        SettingCustomTypes.DIR,
        "Where your Steam is installed. This usually has a steamapps folder in it.",
    )
    STEAM_USER = SettingItem(
        "steam_user",
        "Steam Username",
        False,
        str,
        "Used for generating steam achievement data for gbe_fork",
    )
    STEAM_PASS = SettingItem(
        "steam_pass",
        "Steam Password",
        True,
        str,
        "Also used for generating steam achievement data for gbe_fork",
    )
    STEAM32_ID = SettingItem(
        "steam32_id",
        "Steam32 ID",
        False,
        str,
        "Also also used for generating steam achievement data for gbe_fork",
    )
    GL_VERSION = SettingItem(
        "greenluma_version",
        "GreenLuma Version",
        False,
        list(GreenLumaVersions),
        "Only used if you want GL to store achievements on the Registry",
    )
    APPLIST_FOLDER = SettingItem(
        "applist_folder",
        "GreenLuma AppList Folder",
        False,
        SettingCustomTypes.DIR,
        "Self-explanatory",
    )
    SLS_CONFIG_LOCATION = SettingItem(
        "sls_config_loc",
        "SLSSteam Config File Location",
        False,
        SettingCustomTypes.FILE,
        "Path to your SLSSteam config. Usually in '.config/SLSsteam/config.yaml'",
    )
    TRACK_GREENLUMA_ACH = SettingItem(
        "gl_track_ach",
        "Track Achievements via Greenluma",
        False,
        bool,
        "Enable if you want GL to store achievement to Registry. You can't really easily view them unless you use darktakayanagi's fork of Achievement-Watcher",
    )
    STEAM_WEB_API_KEY = SettingItem(
        "steam_web_api_key",
        "Steam Web API Key",
        True,
        str,
        "Used for searching games and for the experimental mode of generating achievement data for gbe_fork",
    )
    PLAY_MUSIC = SettingItem(
        "play_music",
        "Play Music",
        False,
        bool,
        "Whether to play awesome MIDI music or not",
    )
    ACHIEVE_GEN_MODE = SettingItem(
        "achieve_gen_mode",
        "(gbe_fork) Achievement Generation Mode",
        False,
        list(AchievementGenMode),
        [
            ("fg:ansigreen", "Stable"),
            ("", " uses gbe_fork's generate_emu_config, and "),
            ("fg:ansigreen", "Experimental"),
            ("", " uses my custom version"),
        ],
    )
    SEND_TO_DDM = SettingItem(
        "send_to_ddm",
        "Send To DDM",
        False,
        bool,
        "Whether or not qto automatically send obtained lua+manifest files to DDM"
    )
    DDM_PATH = SettingItem(
        "ddm_path",
        "DDM Path",
        False,
        SettingCustomTypes.FILE,
        "The file path of your DepotDownloaderMod.exe"
    )
    DDM_OUTPUT_DIR = SettingItem(
        "ddm_output_dir",
        "DDM Output Directory",
        False,
        SettingCustomTypes.FILE,
        "The directory where DDM downloads the games"
    )

    @property
    def key_name(self) -> str:
        "The key name of the setting (used in the savefile)"
        return self.value.key_name

    @property
    def clean_name(self) -> str:
        "The name of the setting as displayed in the Settings menu"
        return self.value.clean_name

    @property
    def hidden(self) -> bool:
        "Whether the item is hidden (e.g. sensitive info)"
        return self.value.hidden

    @property
    def type(self) -> SettingType:
        return self.value.type

    @property
    def description(self) -> str | list[tuple[str, str]]:
        return self.value.description

type SettingChangeCallback = Callable[[Settings, Any, Any], None]
"""(Settings, old_val, new_val) -> None."""