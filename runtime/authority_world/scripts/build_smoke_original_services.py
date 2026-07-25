#!/usr/bin/env python3
"""Build digest-pinned official single-container service candidates."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path


def run(command: list[str], cwd: Path, timeout: int) -> tuple[bool, str]:
    try:
        result = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
        return result.returncode == 0, result.stdout[-12000:]
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, str(error)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    candidates = json.loads(args.candidates.read_text(encoding="utf-8"))
    results = []
    for candidate in candidates:
        slug = re.sub(r"[^a-z0-9_.-]", "-", candidate["id"].lower())
        tag = "authority-original-" + slug + ":audit"
        started = time.time()
        ok, log = run(["docker", "build", "--platform", "linux/amd64", "-t", tag, "-f", candidate["dockerfile"], candidate["context"]], Path(candidate["root"]), args.timeout)
        digest = None
        if ok:
            inspected = subprocess.run(["docker", "image", "inspect", tag, "--format", "{{.Id}}"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            if inspected.returncode == 0:
                digest = inspected.stdout.strip()
        results.append({**candidate, "build_ok": ok, "image": tag if ok else None, "image_digest": digest, "elapsed_seconds": round(time.time() - started, 3), "log_tail": log})
        args.output.write_text(json.dumps({"schema": "authority-world-original-service-build-audit-v1", "results": results}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"id": candidate["id"], "build_ok": ok, "digest": digest, "elapsed_seconds": results[-1]["elapsed_seconds"]}))


if __name__ == "__main__":
    main()
