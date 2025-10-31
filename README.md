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

# Contributing

Whenever you update the dependencies, run this as well to update the requirements.txt file for non-uv users.
```
uv pip compile pyproject.toml -o requirements.txt
```

# FAQ

### Why use this?
I guess if you're paranoid about Steamtools and want an open-source equivalent. It's not exactly the same but gets the main functionality down. I heard word that Steamtools is actually safe (as long as you're getting it from the right source), so yeah, your decision. 

### How do I get achievements working?
There's basically two methods: **UserGameStatsSchema** method or **gbe_fork** method.
#### UserGameStatsSchema method
Your achievements can show up in the overlay and library, but it depends on what mode you installed Greenluma in. It seems to work best in `stealth mode` and `stealth mode (any folder)`, but I haven't tested this. In normal mode, you *can* get achievements but it doesn't notify you when you get them. Although, in other games it does... Your achievement data will be stored in `Steam\appcache\stats` like any genuine game although it won't be backed up to the cloud. There's also another **catch**: You can only view the achievement when you switch Steam to offline mode. And I should mention that Steam will fail to launch with Greenluma if you close it while it's still in offline mode. My tool has the `Offline Mode Fix` menu to deal with this.

#### gbe_fork method
You're basically applying a steam emulator and making the emulator handle the achievements. Just crack your game using the tool and confirm when it asks you to generate achievements for gbe_fork. Your achievements won't show up in the Steam overlay or in your library page though. Your achievement data will be in `AppData\Roaming\GSE Saves`. You can also use this if you want to open your game without needing to also open Steam.

### What about cloud sync?
Nope, can't help ya with this one.

### Can I play online games?
Usually no. All it does is just download Clean Steam Files, but there have been a few cases where you can. Just test it out. 

### Can I play dеոսνо/аոtі-сһеаt games?
Out of the box, no. For аոtі-сһеаt, If you're lucky, you'll only have to apply a fix someone else made. With dеոսνо, you'll have to apply an "offline activation". It's a bit of a hassle and I won't get into it. You're on your own with this one. 

### I get "Content Still Encrypted" error
Your decryption key is missing in the `config/config.vdf` folder. Try to import the lua file again.

### I get "No Internet Connection" error
Usually happens when you don't have the manifest or your manifest file is outdated. Try to import the lua file again.



# To-Do
- [ ] keep track on if game was cracked / steamless'd before
  - [ ] prompt to automatically crack and steamless if so
- [ ] if given a ZIP, use existing manifest instead of redownloading

# Licenses
This project includes the following third-party components:
- [gbe_fork](https://github.com/Detanup01/gbe_fork/) (LGPL-3.0)
- [gbe_fork_tools](https://github.com/Detanup01/gbe_fork_tools) (LGPL-3.0)
- [Steamless](https://github.com/atom0s/Steamless/) (CC BY-NC-ND 4.0)

Full license texts are available in the `third_party_licenses` directory.


