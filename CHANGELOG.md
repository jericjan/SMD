## 4.3.0 (2025-12-30)

### Fix

- remote single-quote characters in dir names
- create depotcache folder when it doesn't exist.

## 4.3.0-rc.0 (2025-12-26)

### Feat

- add workshop manifest download
- add easter egg
- remove injector exe setting and instead get the exe dynamically

### Fix

- disable vim mode when fuzzy searching via prompt_select
- safely ignore when a steam library path is not a valid file system
- update MRC endpoint
- ask to try again instead of immediately retrying in 1s when MRC endpoint fails
- run steam kill command only once

### Refactor

- separate responsibilities for download_manifests
- rename decrypt_manifest to decrypt_and_save_manifest

## 4.3.0-beta.2 (2025-12-07)

### Feat

- add auto start/restart steam after lua processing
- add more places to press "Back"
- remember GL achievement tracking instead of prompting every time
- add setting deletion

### Fix

- handle files and dirs properly when changing settings

## 4.3.0-beta.1 (2025-12-06)

### Fix

- handle dlc misclassification

## 4.3.0-beta.0 (2025-12-03)

### Feat

- add way to update either pre-release or stable
- add menu "Update manifests for all outdated games"

### Fix

- refuse update if not frozen

## 4.2.0
### Fix:

- There was a little `The system cannot find the file specified` message whenever you updated through SMD. Not sure how I missed this. It was because of a redundant delete operation. The update still worked.  

- When a ZIP was processed, it would get backed up to saved_lua as a .lua file but the contents would be the raw ZIP itself instead of just the .lua file. (Broken since 4.0.0 😭)

- If a Depot DLC was not part of an "inner depot", it would get incorrectly classified as "PRE-INSTALLED" (Not Depot). 

- When importing a .lua file via right-click, the current working directory would be incorrectly set to the .lua file's directory instead of SMD's directory



### Changes:

- Doesn't decrypt manifests by default anymore. Steam doesn't actually need them decrypted as long as you have the decyption key. If you do still need it, enable advanced mode and use the "(Manifest downloads only" menu option.

- Settings menu will display all values at a glance now



**Full Changelog**: https://github.com/jericjan/SMD/compare/4.1.0...4.2.0

## 4.1.0
**Full Changelog**: https://github.com/jericjan/SMD/compare/4.0.0...4.1.0



### Fixes:

- SMD would fail to move the manifest file if SMD was not on the same drive as the user's Steam installation. I'll take the L on that one. Fixed.

- I forgot to catch exceptions during SMD's initialization before the main loop. Fixed.



### Added/Changed:

- Updated ID limit to 134 (Steam limitation, out of my control)

- SMD will now display an error if the AppList folder has txt files that don't contain only digits.

- Steam Path has been added to settings

- Steam Web API Key has now been hardcoded, although you can still change this in settings if you'd like for whatever reason.

- There is now an option to only download manifests. You could already kind of do that previously but you'd have to go through all the redundant checks like adding to AppList, and adding decryption keys. Do note that this option is disabled by default. You will have to enable Advanced Mode in settings to view it. Once enabled, it will show up as "Process a .lua file (Manifest downloads only)"

- "Manage .lua files" has also been renamed to "Process a .lua file"

- A few small refactors/optimizations have been done

- Added argparse. This means you can run `SMD.exe -f 620.lua` and it'll immediately start processing it.

- Context menu support has been added. You can install/uninstall through the main menu. It'll show up as "Add to SMD" when you right-click a file. This utilizes the argparse functionality I added. This works both in a virtualvenv and in the compiled version.





## 4.0.0
**Full Changelog**: https://github.com/jericjan/SMD/compare/3.4.1...4.0.0



### 3.4.1 had a couple major issues that made people downgrade to 3.3.0. Oops. Those problems have been fixed now.



### Fixed:

- If you try to import a ZIP, it will now work if it contains subfolders

- Reverted timeout for get_product_info to 15s

- Caught an exception when CDNClient initialization times out

- Fixed "stuck on anonymous login" bug. It was actually stuck in an endless loop if a game had only pre-installed/non-depot DLCs.

- When backing up files to saved_lua, it will also rename the file to {app_id}.lua, just in case people import lua files that have been renamed to something else.

- In the lua file parsing, I accidentally made it only read the first ID that doesn't have a decryption key. It will read ALL IDs without keys now.

- Inner Depots from DLC are handled more properly now

- Steam removed their `ISteamApps/GetAppList` endpoint. I've replaced it with `IStoreService/GetAppList`. It does require that you provide a Steam Web API Key though.

- Commented out `addappid` commands will be ignored in the lua file now.

- There are some lua files where the first `addappid` command (usually the base app ID) comes with a decryption key. This usually doesn't have a key. Regardless, it will be properly handled. It will first try to see if that ID has a respective manifest ID (usually doesn't), and when it fails, it just skips it. 



### Added/Changed:

- Session-wide app info caching. This means it won't be making a request to Steam for the same ID multiple times in the same session.

- Greenluma version is remembered via settings. If you only have one version of GL installed, this won't feel any different.

- Because of the above, it will also tell you now if GreenLuma has already been set to track your game's achievements or not. For example: `Would you like Greenluma (normal mode) to track achievements?  (Currently Disabled)`

- luas in `saved_lua` will be overwritten every time you import a lua. Before it would only save the first time and then never again. 



## 3.4.1
### Added

- You can now check for updates through SMD itself (super cursed method dw about it)

- A menu for checking game DLCs has been added. This also runs when you add a lua file. DLCs that don't have depots are called "pre-installed" while DLCs that have depots are called "download required". This should make it easier for newcomers to understand the two types.

- Added a prompt for creating the SkipStatsAndAchievements registry key for greenluma. This happens when after the lua selection process.



### Fixes

- When obtaining app info (via get_product_info) it will try again. It's also been decreased to a timeout of 5 seconds.

- handled the edge case where manilua doesn't have a lua file at all

- For the people building from scratch, you can actually run it without the midi player files now.

- SMD finally uses manifest files from manilua instead of always redownloading from scratch. it will still download new ones if manilua's is outdated.

- For selection prompts where you're able to type for an item, maximum height has been reduced to 10 lines. This way, you don't have to go out of your way to max out the commandline window each time.



### How To Update

Just copy over `settings.bin` and your `saved_lua` folder. It's still compatible. This is the last time you'll have to do this, hopefully.



**Full Changelog**: https://github.com/jericjan/SMD/compare/3.3.0...3.4.1

## 3.3.0
### Added/Changed:

- It will now also search for DLCs (that are not depots) whenever you add a .lua, and then ask to add them to the AppList

- Searching game by name has been added. Takes a good chunk of memory but works pretty quick. (God bless fzf)

- It'll skip the library selection if you only have one #3



### Fixed:

- There was a visual bug where Depot DLCs would show twice when viewing AppList IDs

- AppList IDs are also now sorted properly 

- "Inner Depots" should be properly handled by SMD now. Before, it would fail to grab manifest IDs, but it should be automatic now.

- When fetching Steam app info, it will retry if it ever times out

- When manilua doesn't have a game, it didn't have the chance to respond cuz the timeout was too low. The timeout has been disabled and it should error out properly.



### How To Update

Just copy over `settings.bin` and your `saved_lua` folder. It's still compatible.



**Full Changelog**: https://github.com/jericjan/SMD/compare/3.2.0...3.3.0

## 3.2.0
### Bug Fix:

- Variables were pointlessly reinitialized every time it loops back to the main menu. Fixed. This also means that Steam will only "anonymously login" once per session.

- The prompt module I used (InquirerPy) had a memory leak every time it finished a prompt, and I was able to minimize the leak a bit. Might replace this module in the future.

- Fixed some logic issues in AppListManager:

	- It would start with 1.txt instead of 0.txt if folder was empty

	- When adding/deleting IDs it would write the wrong filename cuz of a variable I forgot to reset



### Additions/Changes:

- Cleaned the print messages a bit with some spacing and coloring here and there.

- debug.log now shows only info from SMD itself, instead of including other external modules

- You can now use Vim keybinds when navigating lists (J and K)

- When downloading from manilua, there's now a lil progress bar if your internet is dogshit.

- AppList Manager will automatically correct filenames if it's ever malformed (e.g. gap in numbering, doesn't start at 0.txt)



### How To Update

Just copy over `settings.bin` and your `saved_lua` folder. It's still compatible.



**Full Changelog**: https://github.com/jericjan/SMD/compare/3.1.1...3.2.0

## 3.1.1
**Full Changelog**: https://github.com/jericjan/SMD/compare/3.1.0...3.1.1



### Bug Fix

- Whoops! Messed up a module import in the last one. Bug caused a crash when retrieving app information. 



### How To Update

Just copy over `settings.bin` and your `saved_lua` folder. It's still compatible.

## 3.1.0
**Full Changelog**: https://github.com/jericjan/SMD/compare/3.0.1...3.1.0



# The Barely Even Anything Update



### Added

- MIDI Music. I was initially gonna use a 25MB soundfont but found a 3MB one that sounded pretty alright. This is toggleable btw so if you don't fw it, just change it in settings. It's also disabled by default. Changes to this setting will persist so don't worry. I also had to use C libraries for this and I *think* it might have a memory leak.



### How To Update

Just copy over `settings.bin` and your `saved_lua` folder. It's still compatible.

## 3.0.1
**Full Changelog**: https://github.com/jericjan/SMD/compare/3.0.0...3.0.1



### Bug Fix:

- gbe_fork and gbe_fork_tools functionality should be back to normal now

- There was a typo where it said "steamtools" instead of steamless

- It would crash if the `GSE Saves` folder didn't alread exist in AppData



### Added:

- It writes extra info to `debug.log`, although not much gets written there right now.



### How To Update

Just copy over settings.bin and your saved_lua folder. It's still compatible.

## 3.0.0
# BUGGED

Anything involving gbe_fork or gbe_fork_tools doesn't work rn. I moved some stuff and it accidentally picks the wrong folder. 



### Added:

- AppList Management. There is now a menu where you can manually delete or add App IDs. If you select the base ID, it will ask if you also want to delete all the Depot IDs that are related to it.

- Crashes won't immediately close the app. Additionally, it will write to a `crash.log` file

- Added short instructions on what to do after SMD processes a lua file

- The AppList path will also print out on startup



### Bug Fix:

- Will warn the user when the Steam path from the registry doesn't exist and then ask for a different path (This doesn't save to settings yet)

- UserGameStatsSchema used to select the steam library folder instead of the steam root installation. Fixed.

- Some steam installations seem to have different capitalization on the key names for config.vdf. The logic is now case-insensitive and should work now.



### Refactor:

- Basically the whole thing has been refactored. Bugs *may* come from this refactor so let me know if there's any that you experience.



### How To Update

Just copy over `settings.bin` and your `saved_lua` folder. It's still compatible.



**Full Changelog**: https://github.com/jericjan/SMD/compare/2.3.1...3.0.0

## 2.3.1
**Full Changelog**: https://github.com/jericjan/SMD/compare/2.3.0...2.3.1



Small bug fix: last version wouldn't generate UserGameStatsSchema bin files because of a flag I added. It should work now. In the off chance, there are still no bin files, it will prompt the user for a Steam64 ID (from someone that owns the game), and redo the bin file downloads.

## 2.3.0
**Full Changelog**: https://github.com/jericjan/SMD/compare/2.2.0...2.3.0



- Back option has been added to most areas, so you don't have to force close the app just to go back to the main menu

- In 2.2.0, after cracking a game, it would run `generate_emu_config` then copy generated files to both `Steam\appcache\stats` (for overlay and library achievements) and the game's `steam_settings` folder (_gbe_fork_ files). This is contradictory because overlay and library achievements only work when _gbe_fork_ has not been applied to the game yet. So they have been separated. You can find `Download UserGameStatsSchema` in the Main Menu and `steam_settings` generation can be done after cracking a game.



## 2.2.0
**Full Changelog**: https://github.com/jericjan/SMD/compare/1.1.0...2.2.0



- Added Manilua endpoint (Requires your own API Key)

- Fixed major bug where steam_appid.txt was always the ID for Portal 😭

- Settings are stored in MessagePack format instead of JSON

- Important settings are encrypted with a keyring master key, so if you happen to accidentally share the whole folder to a friend, they can't read the encrypted settings data.

- Added `gbe_fork_tools` functionally. You can now generate achievement data (both for `Steam\appcache\stats` and `gbe_fork`) without an external tool like Achievement Watcher anymore

- Steam library selection menu has been relocated to a later part of the code

- Settings menu added that lets you view and change your settings

- Custom AppsList location is now supported, meaning you can probably run Greenluma in other mode (I never tested this)

- Bug fix for v2.1.0: UserGameStats will not be overwritten every time anymore

- Added Offline Fix menu for toggling Offline Mode (Greenluma breaks when launching in offline mode)





## 1.1.0
**Full Changelog**: https://github.com/jericjan/SMD/compare/1.0.0...1.1.0

## 1.0.0
First release, might have bugs, lmk

