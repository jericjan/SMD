# Steam Manifest Decryptor (SMD)
Download and decrypt Steam manifest files. Basically imitates what steamtools does and greenluma couldn't.

# Building
It's best if you have `uv` installed.

1. Clone the repo
2. Run `uv sync` to install dependencies
3. Run `uv run main.py` to run the program

# Contributing

If you ever update `content_manifest.proto`, run this to build the stuff that python can understand:
```
uv run python -m grpc_tools.protoc --proto_path=. --python_out=. --pyi_out=. content_manifest.proto
```

Run this as well to generate a requirements.txt for non-uv users
```
uv pip compile pyproject.toml -o requirements.txt
```

# To-Do
- [ ] database for quick app updates