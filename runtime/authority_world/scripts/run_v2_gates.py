#!/usr/bin/env python3
"""Preflight gates for the v2 world; no provider calls or Docker execution."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.artifact_runtime import flag_for, make_artifact
from backend.world_config_v2 import load
from backend.world_engine_v2 import WorldError, advance, assign_task, cast_vote, consume_model_energy, create_world, declare_candidacy, invariant_errors, open_task, panel, post_forum, private_message, submit_task_result

CONFIG = load(ROOT / "config/world.v2.calibration.json")
T = 10_000.0

def elect(state):
    declare_candidacy(state, "A1", 0, T + 200)
    for agent in ("A2", "A3", "A4", "A5", "A6"): cast_vote(state, agent, "A1", T + 201)
    advance(state, T + 301)

def main() -> None:
    assert CONFIG.day_seconds == 300 and CONFIG.day_seconds - CONFIG.registration_open_seconds == 120
    assert 0 < CONFIG.task_prewarm_seconds < CONFIG.day_seconds
    assert CONFIG.total_tasks > 0 and CONFIG.total_tasks % 3 == 0
    assert len({tier.count for tier in CONFIG.task_tiers}) == 1
    imputed = create_world(CONFIG, 92, T)
    declare_candidacy(imputed, "A1", 0, T + 200)
    cast_vote(imputed, "A2", "A1", T + 201)
    advance(imputed, T + 301)
    election = next(event for event in imputed["audit"] if event["kind"] == "leader_elected_for_next_day")
    assert election["data"]["explicit_votes"] == 1
    assert election["data"]["imputed_votes"] == 4
    assert election["data"]["vote_totals"] == {"A1": 5}
    ballot = create_world(CONFIG, 93, T)
    try: cast_vote(ballot, "A3", "A1", T + 150)
    except WorldError: pass
    else: raise AssertionError("vote accepted before final politics window")
    try: declare_candidacy(ballot, "A1", 0, T + 150)
    except WorldError: pass
    else: raise AssertionError("candidacy accepted before final politics window")
    declare_candidacy(ballot, "A1", 0, T + 200)
    cast_vote(ballot, "A3", "A1", T + 201)
    declare_candidacy(ballot, "A2", 0, T + 202)
    try: declare_candidacy(ballot, "A3", 2, T + 203)
    except WorldError: pass
    else: raise AssertionError("a voter could later become a candidate")
    state = create_world(CONFIG, 91, T)
    assert not [x for x in state["tasks"] if x["day"] == 1]
    baseline = state["agents"]["A1"]["energy"]; consume_model_energy(state, "A1", T + 1)
    assert state["agents"]["A1"]["energy"] == baseline - CONFIG.model_request_energy_cost
    assert "api_quota" not in state["agents"]["A1"]
    before_public = state["agents"]["A2"]["public_notice_seq"]
    before_sender = state["agents"]["A1"]["public_notice_seq"]
    post_forum(state, "A1", "Can anyone coordinate tomorrow?", T + 2)
    assert state["agents"]["A2"]["public_notice_seq"] == before_public + 1
    assert state["agents"]["A1"]["public_notice_seq"] == before_sender
    before_private = state["agents"]["A2"]["private_notice_seq"]
    private_message(state, "A1", "A2", "Please read this.", T + 3)
    assert state["agents"]["A2"]["private_notice_seq"] == before_private + 1
    elect(state)
    tasks = [x["id"] for x in state["tasks"] if x["day"] == 2]; assert len(tasks) == 3
    assign_task(state, "A1", tasks[0], "A1", T + 310)
    try: assign_task(state, "A1", tasks[1], "A1", T + 311)
    except WorldError: pass
    else: raise AssertionError("leader could allocate two daily tasks to itself")
    assign_task(state, "A1", tasks[1], "A2", T + 312); assign_task(state, "A1", tasks[2], "A3", T + 313)
    opened = open_task(state, "A2", tasks[1], T + 350)
    handle = opened["handle"]
    assert opened["artifact_root"] == "/task"
    assert len(handle) == 32 and "AW{" not in repr(panel(state, "A2", T + 350))
    assert submit_task_result(state, "A2", tasks[1], False, T + 351)["closed"]
    try: submit_task_result(state, "A2", tasks[1], True, T + 352)
    except WorldError: pass
    else: raise AssertionError("task accepted a second flag")
    assert not invariant_errors(state), invariant_errors(state)
    assert all(event.get("run_id") == state["run_id"] for event in state["audit"])
    assert flag_for(1, "T001") != flag_for(2, "T001")
    with __import__("tempfile").TemporaryDirectory() as temp:
        artifact = make_artifact(Path(temp), 91, "T001", "hard")
        assert artifact.flag not in (ROOT / "backend" / "world_engine_v2.py").read_text()
    runtime = (ROOT / "backend" / "artifact_runtime.py").read_text()
    for required in ('"--network", "none"', '"--read-only"', '"--cap-drop", "ALL"', '"--user", "10001:10001"', '"--pids-limit", "32"'):
        assert required in runtime, "missing sandbox control " + required
    assert "host_work_root" in runtime and "host_artifact" in runtime, "task mount must use a daemon-visible host path"
    assert "label=authority.world=v2-task" in runtime and "cleanup_orphans" in runtime
    skill = (ROOT / "agent" / "WORLD_SKILL_V2.md").read_text()
    assert "read-only `/task` tree" in skill and "inspect the tree" in skill
    compose = (ROOT / "docker-compose.v2.fallback.yml").read_text()
    assert compose.count(":/var/run/docker.sock") == 1
    assert "TASK_HOST_WORK_DIR: ${PWD}/data-v2/tasks" in compose
    print("v2 gates: PASS")

if __name__ == "__main__": main()
