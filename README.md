# Steam Manifest Decryptor (SMD)
<img alt="" src="https://img.shields.io/github/repo-size/jericjan/SMD" />

Download and decrypt Steam manifest files. Basically imitates what steamtools does and greenluma couldn't.

## **Educational use only.** This project is provided for educational purposes only. Use at your own risk.

Need help? Reach out to me on the discord server and we'll sort it out: https://discord.gg/bK667akcjn

# Building
It's best if you have `uv` installed. Download from Releases if you don't want to build it yourself.

1. Clone the repo
2. Run `uv sync` to install dependencies  
3. Download [gbe_fork_tools](https://github.com/Detanup01/gbe_fork_tools/releases) (compiled) and paste the `generate_emu_config` folder inside `\third_party\gbe_fork_tools`. It should look something like this now:  
```
├───gbe_fork
├───gbe_fork_tools
│   └───generate_emu_config
│       └───_internal
│       └───generate_emu_config.exe
└───steamless
```
4. Download my version of [aria2](https://github.com/jericjan/aria2) (has increased limits) and place it in `third_party\aria2c\aria2c.exe`.
5. Either run `uv run main.py` to directly run it or `uv run pyinstaller main.spec` to build it. You can also build it with `build.bat` for convenience.

Optional (Requires GCC Compiler):
1. CD into the `c` folder and build the MIDI Player with:  
```gcc midi_player_lib.c -shared -fPIC -o midi_player_lib.dll```
2. Download this [soundfont](https://musical-artifacts.com/artifacts/7352) (WTFPL 2 License) and place it in the `c` folder. Any soundfont works but just note that bigger files will use more memory.
3. Download this [MIDI](https://files.gamebanana.com/bitpit/th105_broken_moon_redpaper_.mid) and place it in the `c` folder.

# Pre-requisites
This program requires that **GreenLuma** is installed, preferably in normal mode. Other modes work too but you'll have to specify the AppList folder location manually.

# Features
- Downloads and decrypt latest manifest
- Downloading lua files from either Manilua (API key required) or oureveryday
- Stores imported lua files for later use (e.g. updating the game)
- Cracks games with [gbe_fork](https://github.com/Detanup01/gbe_fork/)
- Removes SteamStub DRM with [Steamless](https://github.com/atom0s/Steamless/)
- Via [gbe_fork_tools](https://github.com/Detanup01/gbe_fork_tools) :
  - `steam_settings` folder generation 
   - `Steam\appcache\stats` .bin file generation (for Steam achievements directly in the Steam overlay/library)
- Basic AppList folder management (You can add and delete IDs for now)

# Contributing

Whenever you update the dependencies, run this as well to update the requirements.txt file for non-uv users.
```
uv pip compile pyproject.toml -o requirements.txt
```

# FAQ
(Moved to the [wiki](/../../wiki/FAQ))



# To-Do
- [ ] keep track on if game was cracked / steamless'd before
  - [ ] prompt to automatically crack and steamless if so
- [ ] Use gbe_fork_tools source code instead of using a compiled version

# Licenses
This project includes the following third-party components:
- [gbe_fork](https://github.com/Detanup01/gbe_fork/) (LGPL-3.0)
- [gbe_fork_tools](https://github.com/Detanup01/gbe_fork_tools) (LGPL-3.0)
- [Steamless](https://github.com/atom0s/Steamless/) (CC BY-NC-ND 4.0)
- [TinyMidiLoader](https://github.com/schellingb/TinySoundFont) (ZLIB)
- [TinySoundFont](https://github.com/schellingb/TinySoundFont) (MIT)
- [miniaudio](https://github.com/mackron/miniaudio) (MIT)
- [fzf](https://github.com/junegunn/fzf) (MIT)
- [aria2](https://github.com/aria2/aria2) (GPL-3.0)

Full license texts are available in the `third_party_licenses` directory or as comments in the respective module file.

# Credit
Credit to RedPaper for the Broken Moon MIDI cover, originally arranged by U2 Akiyama and used in Touhou 7.5: Immaterial and Missing Power.
Touhou 7.5 and its related assets are owned by Team Shanghai Alice and Twilight Frontier. SMD is not affiliated with, endorsed by, or sponsored by either party. All trademarks belong to their respective owners.



