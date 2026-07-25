"""Host-side controller for the pre-registered five-condition series.

It is intentionally outside the Agent world.  It never injects messages,
resources, or actions.  A technical failure stops the series rather than
silently progressing to the next condition.

Run on the experiment host:
  nohup python3 scripts/run_formal_series.py --start-index 1 > series.log 2>&1 &
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STATE = DATA / "authority-world-v1.state.json"
EVENTS = DATA / "authority-world-v1.events.jsonl"
SNAPSHOTS = ROOT / "snapshots"
DEFAULT_RESULTS = ROOT / "formal-results"
CONDITIONS = [
    "r1_pure_resource_formal.json",
    "r2_competitive_tasks_formal.json",
    "r3_elected_allocator_formal.json",
    "r4_random_allocator_formal.json",
    "r5_norm_sensitive_allocator_formal.json",
]


def env_for(condition: str) -> dict[str, str]:
    value = os.environ.copy()
    control = next((line.split("=", 1)[1].strip() for line in (ROOT / ".env").read_text().splitlines() if line.startswith("WORLD_CONTROL_TOKEN=")), None)
    if not control:
        raise RuntimeError("WORLD_CONTROL_TOKEN is missing from .env")
    value["WORLD_CONFIG_FILE"] = condition
    value["OBSERVER_TOKEN"] = control
    return value


def compose(condition: str, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.fallback.yml", *arguments], cwd=ROOT, env=env_for(condition), text=True, check=check, capture_output=True)


def log(text: str) -> None:
    print(f"[{time.strftime('%Y-%m-%dT%H:%M:%S%z')}] {text}", flush=True)


def read_state() -> dict | None:
    return json.loads(STATE.read_text()) if STATE.exists() else None


def event_kinds() -> set[str]:
    if not EVENTS.exists():
        return set()
    return {json.loads(line)["kind"] for line in EVENTS.read_text().splitlines() if line.strip()}


def wait_backend(condition: str, timeout: float = 150.0) -> None:
    deadline = time.time() + timeout
    code = "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8100/health', timeout=3).read().decode())"
    while time.time() < deadline:
        result = compose(condition, "exec", "-T", "backend", "python", "-c", code, check=False)
        if result.returncode == 0:
            return
        time.sleep(2)
    raise RuntimeError("backend did not become healthy within timeout")


def start_condition(index: int, seed_base: int) -> None:
    condition = CONDITIONS[index - 1]
    log(f"starting R{index}: {condition}")
    compose(condition, "up", "-d", "--build")
    wait_backend(condition)
    seed = seed_base + index
    code = (
        "import os,urllib.request; "
        f"r=urllib.request.Request('http://127.0.0.1:8100/v1/control/start',data=b'{{\"seed\":{seed},\"start_delay_seconds\":30}}',method='POST',"
        "headers={'Content-Type':'application/json','X-World-Control-Token':os.environ['WORLD_CONTROL_TOKEN']}); "
        "print(urllib.request.urlopen(r).read().decode())"
    )
    result = compose(condition, "exec", "-T", "backend", "python", "-c", code)
    log("start accepted " + result.stdout.strip())


def archive_completed(index: int, state: dict, results: Path) -> None:
    run_id = str(state["run_id"])
    target = results / f"R{index}-{run_id}"
    if target.exists():
        raise RuntimeError(f"result target already exists: {target}")
    target.mkdir(parents=True)
    # Produce a descriptive summary before moving the raw, append-only data.
    audit = subprocess.run([sys.executable, "scripts/audit_run.py", "data"], cwd=ROOT, text=True, check=True, capture_output=True)
    (target / "audit_summary.json").write_text(audit.stdout)
    (target / "run_metadata.json").write_text(json.dumps({"condition": CONDITIONS[index - 1], "run_id": run_id, "config_hash": state.get("config_hash"), "archived_at": time.time()}, indent=2))
    for name in ("data", "agent-state", "gateway-data"):
        source = ROOT / name
        if source.exists():
            shutil.move(str(source), target / name)
    snapshot_target = target / "snapshots"
    snapshot_target.mkdir()
    for source in SNAPSHOTS.glob(run_id + "*"):
        shutil.move(str(source), snapshot_target / source.name)
    for name in ("data", "agent-state", "gateway-data", "snapshots"):
        (ROOT / name).mkdir(exist_ok=True)
    for number in range(1, 7):
        (ROOT / "agent-state" / f"a{number}").mkdir(parents=True, exist_ok=True)
    log(f"R{index} archived at {target}")


def stop_stack(condition: str) -> None:
    # Stop supervisor first so a normal host shutdown cannot be written as an
    # in-world technical failure marker.
    compose(condition, "stop", "supervisor", check=False)
    compose(condition, "down")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-index", type=int, default=1, choices=range(1, len(CONDITIONS) + 1))
    parser.add_argument("--poll-seconds", type=float, default=10.0)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS,
                        help="Archive root. Use a new directory for a new registered batch.")
    parser.add_argument("--seed-base", type=int, default=2026071800,
                        help="Base seed; condition i receives seed_base + i.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        for number, condition in enumerate(CONDITIONS, 1):
            print(f"R{number}: {condition}")
        return
    index = args.start_index
    while index <= len(CONDITIONS):
        condition = CONDITIONS[index - 1]
        state = read_state()
        if state is None:
            start_condition(index, args.seed_base)
            time.sleep(args.poll_seconds)
            continue
        if state.get("status") in {"scheduled", "running"}:
            time.sleep(args.poll_seconds)
            continue
        if state.get("status") == "technical_failed" or "technical_failure" in event_kinds():
            raise SystemExit(f"R{index} stopped: technical failure; raw data left in place for diagnosis")
        if state.get("status") != "complete":
            raise SystemExit(f"R{index} stopped: unexpected state {state.get('status')!r}")
        archive_completed(index, state, args.results_dir)
        stop_stack(condition)
        index += 1
    log("all five conditions completed and archived")


if __name__ == "__main__":
    main()
