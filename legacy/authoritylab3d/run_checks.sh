#!/bin/zsh
set -euo pipefail

GODOT="/Applications/Godot.app/Contents/MacOS/Godot"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

"$GODOT" --headless --path "$PROJECT_DIR" --script res://scripts/smoke_test.gd
