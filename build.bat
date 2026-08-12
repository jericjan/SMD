uv sync --no-dev
uv run --no-dev pyinstaller --clean --noconfirm main.spec
uv sync