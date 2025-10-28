# Steam Manifest Decryptor (SMD)
<img alt="" src="https://img.shields.io/github/repo-size/jericjan/SMD" />

Download and decrypt Steam manifest files. Basically imitates what steamtools does and greenluma couldn't.

## **Educational use only.** This project is provided for educational purposes only. Use at your own risk.

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
4. Either `uv run main.py` to directly run it or `uv run pyinstaller main.spec` to build it

# Pre-requisites
This program requires that **GreenLuma** is installed, preferably in normal mode. Other modes work too but for now, it's most convenient in normal mode.


# Features
- Downloads and decrypt latest manifest
- Stores imported lua files for later use (e.g. updating the game)
- Cracks games with [gbe_fork](https://github.com/Detanup01/gbe_fork/)
- Removes SteamStub DRM with [Steamless](https://github.com/atom0s/Steamless/)

# Caveats
It can't generate achievements for gbe_fork automatically so you'll have to use a tool like Achievement Watcher in the meantime.

# Contributing

Whenever you update the dependencies, run this as well to update the requirements.txt file for non-uv users.
```
uv pip compile pyproject.toml -o requirements.txt
```

# To-Do
- [ ] keep track on if game was cracked / steamless'd before
  - [ ] prompt to automatically crack and steamless if so
- [ ] if given a ZIP, use existing manifest instead of redownloading
- [ ] AppList folder manager (deletion, adding dlc)

# Licenses
This project includes the following third-party components:
- [gbe_fork](https://github.com/Detanup01/gbe_fork/) (LGPL-3.0)
- [Steamless](https://github.com/atom0s/Steamless/) (CC BY-NC-ND 4.0)

Full license texts are available in the `third_party_licenses` directory.
