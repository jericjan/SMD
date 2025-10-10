If you ever update `content_manifest.proto`, run this to build the stuff that python can understand:
```
uv run python -m grpc_tools.protoc --proto_path=. --python_out=. --pyi_out=. content_manifest.proto
```
