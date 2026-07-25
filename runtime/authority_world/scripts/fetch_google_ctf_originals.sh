#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
DEST=${CTF_GOOGLE_DEST:-"$ROOT/ctf-originals/google-ctf"}
COMMIT=${CTF_GOOGLE_COMMIT:-067421eb7e918c29e39f187fac5a0f0d72a6ab83}
PROXY=${CTF_GIT_PROXY:-}

if [[ -e "$DEST" ]]; then
  echo "destination already exists: $DEST" >&2
  exit 2
fi

mkdir -p "$(dirname "$DEST")"
args=(clone --filter=blob:none --no-checkout https://github.com/google/google-ctf.git "$DEST")
if [[ -n "$PROXY" ]]; then
  git -c "http.proxy=$PROXY" "${args[@]}"
else
  git "${args[@]}"
fi
git -C "$DEST" sparse-checkout init --cone
git -C "$DEST" sparse-checkout set 2020 2021 2022 2023 2024 2025
git -C "$DEST" checkout --detach "$COMMIT"
actual=$(git -C "$DEST" rev-parse HEAD)
[[ "$actual" == "$COMMIT" ]] || { echo "commit mismatch: $actual" >&2; exit 3; }
echo "Google CTF originals ready at $DEST ($actual)"
