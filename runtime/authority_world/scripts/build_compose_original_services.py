#!/usr/bin/env python3
"""Build official Compose service candidates and record immutable image IDs."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    candidates = json.loads(args.candidates.read_text(encoding="utf-8"))
    results = []
    for candidate in candidates:
        project = "authority-audit-" + re.sub(r"[^a-z0-9]", "-", candidate["id"].lower())[-48:]
        started = time.time()
        command = ["docker", "compose", "-p", project, "-f", candidate["compose"], "build"]
        try:
            built = subprocess.run(command, cwd=candidate["root"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=args.timeout, check=False)
            ok, log = built.returncode == 0, built.stdout[-12000:]
        except (OSError, subprocess.TimeoutExpired) as error:
            ok, log = False, str(error)
        images = []
        if ok:
            config = subprocess.run(["docker", "compose", "-p", project, "-f", candidate["compose"], "config", "--images"], cwd=candidate["root"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            for image in config.stdout.splitlines():
                inspected = subprocess.run(["docker", "image", "inspect", image, "--format", "{{.Id}}"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                if inspected.returncode == 0:
                    images.append({"name": image, "digest": inspected.stdout.strip()})
            ok = bool(images)
        results.append({**candidate, "project": project, "build_ok": ok, "images": images, "elapsed_seconds": round(time.time() - started, 3), "log_tail": log})
        args.output.write_text(json.dumps({"schema": "authority-world-original-compose-build-audit-v1", "results": results}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"id": candidate["id"], "build_ok": ok, "images": images, "elapsed_seconds": results[-1]["elapsed_seconds"]}))


if __name__ == "__main__":
    main()
