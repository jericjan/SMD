#!/bin/bash

BASE_DIR=$(dirname "$(readlink -f "$0")")

APP_NAME="SMD"
DESKTOP_FILE="$HOME/.local/share/applications/io.github.jericjan.smd.desktop"
EXEC_PATH="$BASE_DIR/SMD"
ICON_PATH="$BASE_DIR/_internal/icon.ico"

mkdir -p "$HOME/.local/share/applications"

cat <<EOF > "$DESKTOP_FILE"
[Desktop Entry]
Type=Application
Name=$APP_NAME
Exec=$EXEC_PATH
Icon=$ICON_PATH
Terminal=true
Categories=Utility;
EOF

chmod a+x "$DESKTOP_FILE"

update-desktop-database ~/.local/share/applications 2>/dev/null

echo "SMD added to desktop!"