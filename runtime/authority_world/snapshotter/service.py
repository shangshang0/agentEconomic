"""Barriered full-run checkpoint service.

The backend creates a checkpoint request at each world-day boundary.  While a
request is pending, agents cannot begin another world action.  This service
copies the world checkpoint, every isolated agent state directory, the
gateway audit, and the active config into one immutable bundle, hashes it,
then acknowledges the barrier.  It is a host-side research service and is
never reachable by Agents.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import urllib.request
from pathlib import Path

WORLD = Path(os.environ.get("WORLD_DATA_DIR", "/world-data"))
AGENTS = Path(os.environ.get("AGENT_STATE_DIR", "/agent-state"))
GATEWAY = Path(os.environ.get("GATEWAY_DATA_DIR", "/gateway-data"))
CONFIG = Path(os.environ.get("WORLD_CONFIG_DIR", "/world-config"))
OUT = Path(os.environ.get("SNAPSHOT_DIR", "/snapshots"))
BACKEND = os.environ["BACKEND_URL"].rstrip("/")
TOKEN = os.environ["WORLD_CONTROL_TOKEN"]
STATE = WORLD / "authority-world-v1.state.json"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def copy_tree(source: Path, target: Path) -> None:
    if source.exists():
        shutil.copytree(source, target, dirs_exist_ok=False)
    else:
        target.mkdir(parents=True)


def acknowledge(snapshot_id: str) -> None:
    request = urllib.request.Request(
        BACKEND + "/v1/control/checkpoints/complete",
        data=json.dumps({"snapshot_id": snapshot_id}).encode(), method="POST",
        headers={"Content-Type": "application/json", "X-World-Control-Token": TOKEN},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        json.load(response)


def take(request: dict) -> None:
    snapshot_id = request["snapshot_id"]
    target = OUT / snapshot_id
    if target.exists():
        acknowledge(snapshot_id)
        return
    staging = OUT / ("." + snapshot_id + ".partial")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    shutil.copy2(STATE, staging / STATE.name)
    events = WORLD / "authority-world-v1.events.jsonl"
    if events.exists():
        shutil.copy2(events, staging / events.name)
    copy_tree(AGENTS, staging / "agent-state")
    copy_tree(GATEWAY, staging / "gateway-data")
    copy_tree(CONFIG, staging / "config")
    files = sorted(path for path in staging.rglob("*") if path.is_file())
    manifest = {
        "snapshot_id": snapshot_id, "day": request["day"], "event_seq": request["event_seq"],
        "run_id": json.loads((staging / STATE.name).read_text(encoding="utf-8")).get("run_id"),
        "created_at": time.time(), "files": {str(path.relative_to(staging)): digest(path) for path in files},
    }
    (staging / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(staging, target)
    acknowledge(snapshot_id)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    while True:
        try:
            if STATE.exists():
                state = json.loads(STATE.read_text(encoding="utf-8"))
                request = state.get("checkpoint_pending")
                if isinstance(request, dict) and {"snapshot_id", "day", "event_seq"} <= set(request):
                    take(request)
        except Exception as error:
            # A pending checkpoint deliberately remains pending on failure;
            # the backend will not let agents race past an incomplete bundle.
            print(f"snapshotter error: {type(error).__name__}: {error}", flush=True)
        time.sleep(0.25)


if __name__ == "__main__":
    main()
