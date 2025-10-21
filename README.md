# Steam Manifest Decryptor (SMD)
Download and decrypt Steam manifest files. Basically imitates what steamtools does and greenluma couldn't.

## **Educational use only.** This project is provided for educational purposes only. Use at your own risk.

# Building
It's best if you have `uv` installed. Download from Releases if you don't want to build it yourself.

1. Clone the repo
2. Run `uv sync` to install dependencies  
3. Either `uv run main.py` to directly run it or `uv run pyinstaller main.spec` to build it

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

If you ever update `content_manifest.proto`, run this to build the stuff that python can understand:
```
uv run python -m grpc_tools.protoc --proto_path=. --python_out=. content_manifest.proto
```
Because of the `steam` module, the project is locked to version 1.48.2 of `grpcio-tools`. This means the python stub files (`.pyi`) cannot be generated. One workaround is to download a `protoc` binary (I used [this](https://github.com/protocolbuffers/protobuf/releases/tag/v32.1) one) and run this:
```
protoc.exe --pyi_out=. -I. content_manifest.proto
```

Run this as well to generate a requirements.txt for non-uv users
```
uv pip compile pyproject.toml -o requirements.txt
```

# To-Do
- [ ] achievement generator
- [ ] steamless - use `get_product_info()` to get executable location

# Licenses
This project includes the following third-party components:
- [gbe_fork](https://github.com/Detanup01/gbe_fork/) (LGPL-3.0)
- [Steamless](https://github.com/atom0s/Steamless/) (CC BY-NC-ND 4.0)

Full license texts are available in the `third_party_licenses` directory.
