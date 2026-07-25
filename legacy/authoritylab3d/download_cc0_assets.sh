#!/bin/zsh
# Downloads a small, pinned CC0 asset pack from Poly Haven. These are real PBR
# assets, not generated placeholders. The sources and their CC0 status are
# recorded in assets/polyhaven/ATTRIBUTION.md.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
python3 "$ROOT/scripts/fetch_polyhaven_assets.py" "$ROOT/assets/polyhaven"
