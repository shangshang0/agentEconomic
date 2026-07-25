#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
docker build -f Dockerfile.task -t authority-world-task:v2 .
