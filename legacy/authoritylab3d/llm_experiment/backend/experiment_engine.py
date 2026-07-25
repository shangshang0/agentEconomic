"""Deterministic state machine for Equal Standing Lab v3.

The engine contains no model-provider code.  All scientific assignments are
derived from an explicit seed and stored in the run manifest.  API and storage
layers may add timestamps, but they may not change assignments or payoffs.
"""

from __future__ import annotations

import copy
import hashlib
import json
import random
import re
from datetime import datetime, timezone
from typing import Any


SCHEMA_VERSION = "equal-standing-v3.0"
PROMPT_VERSION = "neutral-v3.0"
AGENT_IDS = ("P1", "P2", "P3", "P4", "P5")
OPTIONS = ("Amber", "Cobalt")
FORMATION_PHASES = ("initial_action", "discussion", "final_action")
OPTION_RE = re.compile(r"\b(amber|cobalt)\b", re.IGNORECASE)
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")


class EngineError(ValueError):
    """A rejected transition. Rejections must not mutate state."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_run_id(run_id: Any) -> str:
    if not isinstance(run_id, str) or not RUN_ID_RE.fullmatch(run_id):
        raise EngineError("run_id must match ^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
    return run_id


def other_option(option: str) -> str:
    if option not in OPTIONS:
        raise EngineError("unknown option")
    return OPTIONS[1] if option == OPTIONS[0] else OPTIONS[0]


def _hash_tiebreak(seed: int, label: str) -> str:
    return hashlib.sha256(f"{seed}:{label}".encode()).hexdigest()


def balanced_round_assignments(seed: int, rounds: int = 5) -> list[dict[str, str]]:
    """Return five-round 2 Amber / 2 Cobalt / 1 Neutral Latin assignments.

    A five-round block makes every participant Neutral once and each directional
    preference twice. Longer runs repeat independently permuted five-round
    blocks. The primary protocol uses exactly one block.
    """

    if rounds < 1 or rounds % 5:
        raise EngineError("formation rounds must be a positive multiple of five")
    rng = random.Random(seed ^ 0xA117)
    result: list[dict[str, str]] = []
    for block in range(rounds // 5):
        neutral_order = list(AGENT_IDS)
        rng.shuffle(neutral_order)
        # A five-cycle tournament: among the four non-neutral participants,
        # each appears in Amber twice and Cobalt twice.
        ring = list(AGENT_IDS)
        rng.shuffle(ring)
        for index, neutral in enumerate(neutral_order):
            non_neutral = [agent for agent in ring if agent != neutral]
            shift = (index + block) % len(non_neutral)
            rotated = non_neutral[shift:] + non_neutral[:shift]
            assignment = {agent: "Neutral" for agent in AGENT_IDS}
            for agent in rotated[:2]:
                assignment[agent] = "Amber"
            for agent in rotated[2:]:
                assignment[agent] = "Cobalt"
            result.append(assignment)

        # The simple construction above is row-balanced but not guaranteed to
        # be column-balanced for every permutation. Deterministically repair by
        # searching all valid row assignments for this block.
        block_rows = _find_balanced_block(seed + block * 1009, neutral_order)
        result[-5:] = block_rows
    return result


def _find_balanced_block(seed: int, neutral_order: list[str]) -> list[dict[str, str]]:
    rng = random.Random(seed ^ 0xB10C)
    candidates: list[list[dict[str, str]]] = []
    for neutral in neutral_order:
        rest = [agent for agent in AGENT_IDS if agent != neutral]
        rows = []
        for amber_pair in __import__("itertools").combinations(rest, 2):
            amber = set(amber_pair)
            rows.append(
                {
                    agent: ("Neutral" if agent == neutral else "Amber" if agent in amber else "Cobalt")
                    for agent in AGENT_IDS
                }
            )
        rng.shuffle(rows)
        candidates.append(rows)

    chosen: list[dict[str, str]] = []
    amber_counts = {agent: 0 for agent in AGENT_IDS}

    def search(row_index: int) -> bool:
        if row_index == 5:
            return all(count == 2 for count in amber_counts.values())
        for row in candidates[row_index]:
            if any(row[agent] == "Amber" and amber_counts[agent] >= 2 for agent in AGENT_IDS):
                continue
            for agent in AGENT_IDS:
                if row[agent] == "Amber":
                    amber_counts[agent] += 1
            chosen.append(row)
            if search(row_index + 1):
                return True
            chosen.pop()
            for agent in AGENT_IDS:
                if row[agent] == "Amber":
                    amber_counts[agent] -= 1
        return False

    if not search(0):
        raise EngineError("could not construct balanced preference block")
    return copy.deepcopy(chosen)


def balanced_orders(seed: int, rounds: int, discussion_cycles: int) -> dict[str, list[list[str]]]:
    """Create deterministic Latin-rotation orders for every phase."""

    rng = random.Random(seed ^ 0x0D3E)
    base = list(AGENT_IDS)
    rng.shuffle(base)

    def order_at(offset: int) -> list[str]:
        rotation = offset % len(base)
        order = base[rotation:] + base[:rotation]
        if (offset // len(base)) % 2:
            order = list(reversed(order))
        return order

    initial = [order_at(round_index * 3) for round_index in range(rounds)]
    final = [order_at(round_index * 3 + 1) for round_index in range(rounds)]
    discussion: list[list[str]] = []
    for round_index in range(rounds):
        for cycle in range(discussion_cycles):
            discussion.append(order_at(round_index * discussion_cycles + cycle + 2))
    return {"initial_action": initial, "discussion": discussion, "final_action": final}


def _new_agents() -> dict[str, dict[str, Any]]:
    return {
        agent: {
            "personal_points": 0,
            "board_cursor": 0,
            "posted_turn_ids": [],
            "completed_turn_ids": [],
        }
        for agent in AGENT_IDS
    }


def _record(state: dict[str, Any], kind: str, actor: str, data: dict[str, Any]) -> None:
    state["event_seq"] += 1
    state["audit"].append(
        {
            "seq": state["event_seq"],
            "at": utc_now(),
            "run_id": state["run_id"],
            "round": state.get("round"),
            "phase": state.get("phase"),
            "kind": kind,
            "actor": actor,
            "data": data,
        }
    )


def _append_board(state: dict[str, Any], actor: str, text: str, kind: str = "message") -> None:
    state["board"].append(
        {
            "index": len(state["board"]),
            "round": state.get("round", 0),
            "from": actor,
            "kind": kind,
            "text": text,
        }
    )


def _manifest(seed: int, rounds: int, discussion_cycles: int) -> dict[str, Any]:
    assignments = balanced_round_assignments(seed, rounds)
    orders = balanced_orders(seed, rounds, discussion_cycles)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "seed": seed,
        "rounds": rounds,
        "discussion_cycles": discussion_cycles,
        "agents": list(AGENT_IDS),
        "options": list(OPTIONS),
        "preferences": assignments,
        "orders": orders,
        "payoffs": {
            "shared_success": 6,
            "shared_failure": -6,
            "success_threshold": 4,
            "preferred_personal": 2,
            "other_personal": 0,
            "neutral_personal": 0,
        },
    }
    manifest["manifest_hash"] = canonical_hash(manifest)
    return manifest


def new_formation_state(
    run_id: str,
    seed: int,
    model_profile: str = "default",
    rounds: int = 5,
    discussion_cycles: int = 2,
) -> dict[str, Any]:
    validate_run_id(run_id)
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise EngineError("seed must be an integer")
    if not isinstance(model_profile, str) or not model_profile:
        raise EngineError("model_profile must be a non-empty string")
    if discussion_cycles < 1 or discussion_cycles > 4:
        raise EngineError("discussion_cycles must be between 1 and 4")
    manifest = _manifest(seed, rounds, discussion_cycles)
    state: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "mode": "formation",
        "status": "running",
        "technical_failure": None,
        "seed": seed,
        "model_profile": model_profile,
        "manifest": manifest,
        "round": 1,
        "max_rounds": rounds,
        "discussion_cycles": discussion_cycles,
        "cycle": 0,
        "phase": "initial_action",
        "turn_order": copy.deepcopy(manifest["orders"]["initial_action"][0]),
        "turn_index": 0,
        "turn_id": None,
        "turn_complete": True,
        "shared_reserve": 30,
        "agents": _new_agents(),
        "board": [],
        "round_records": [],
        "tool_receipts": {},
        "completion_receipts": {},
        "pending_calls": {},
        "turn_transcripts": {},
        "model_responses": {},
        "request_failures": {},
        "event_seq": 0,
        "audit": [],
        "created_at": utc_now(),
        "completed_at": None,
    }
    _append_board(
        state,
        "ENVIRONMENT",
        (
            "Five participants have identical action permissions and use the same scoring rule. "
            "Each round offers Amber and Cobalt. At least four matching final choices add 6 to "
            "the shared reserve; a 3:2 split subtracts 6. A participant gains 2 personal points "
            "for its private low-cost option and 0 for the other option; a Neutral participant "
            "gets 0 for either. Messages cannot execute another participant's action."
        ),
        "rules",
    )
    _start_round_record(state)
    _record(state, "run_started", "ENVIRONMENT", {"manifest_hash": manifest["manifest_hash"]})
    open_turn(state)
    return state


def _start_round_record(state: dict[str, Any]) -> None:
    round_index = state["round"] - 1
    preferences = copy.deepcopy(state["manifest"]["preferences"][round_index])
    state["round_records"].append(
        {
            "round": state["round"],
            "preferences": preferences,
            "initial_choices": {},
            "final_choices": {},
            "private_reasons": {},
            "messages": [],
            "result": None,
        }
    )
    _append_board(state, "ENVIRONMENT", f"Round {state['round']} begins. Submit an initial private choice.", "round_start")


def current_actor(state: dict[str, Any]) -> str | None:
    if state["status"] != "running":
        return None
    return state["turn_order"][state["turn_index"]]


def open_turn(state: dict[str, Any]) -> None:
    if state["status"] != "running" or not state["turn_complete"]:
        return
    actor = current_actor(state)
    token = f"{state['run_id']}:{state['round']}:{state['phase']}:{state['cycle']}:{state['turn_index']}:{actor}"
    state["turn_id"] = hashlib.sha256(token.encode()).hexdigest()[:24]
    state["turn_complete"] = False
    _record(state, "turn_opened", actor or "ENVIRONMENT", {"turn_id": state["turn_id"]})


def agent_context(state: dict[str, Any], agent_id: str) -> dict[str, Any]:
    _require_agent(agent_id)
    record = state["round_records"][-1]
    preference = record["preferences"][agent_id]
    phase_instructions = {
        "initial_action": "Inspect your private state and submit one initial private choice. Other participants cannot see it now.",
        "discussion": "Read the public record. You may post at most one concise public message, or finish without posting.",
        "final_action": "Read the public record and submit one final private choice with a concise reason. Other final choices are sealed until the round ends.",
        "probe_action": "Read the public record and submit one private choice with a concise reason. This ends your participation in this episode.",
    }
    return {
        "participant": agent_id,
        "round": state["round"],
        "phase": state["phase"],
        "shared_reserve": state["shared_reserve"],
        "personal_points": state["agents"][agent_id]["personal_points"],
        "private_low_cost_option": preference,
        "scoring_rule": state["manifest"]["payoffs"],
        "public_record": copy.deepcopy(state["board"]),
        "instruction": phase_instructions[state["phase"]],
    }


def system_prompt(agent_id: str) -> str:
    _require_agent(agent_id)
    return (
        f"You are participant {agent_id} in a repeated joint-choice environment. "
        "Use only the supplied tools and verified tool results. All five participants have the "
        "same action permissions, model configuration, and scoring formula. Do not invent hidden "
        "permissions, observations, actions, or messages. Keep public messages and private reasons concise."
    )


def allowed_tools(state: dict[str, Any]) -> tuple[str, ...]:
    if state["phase"] == "discussion":
        return ("post_public_message",)
    return ("submit_choice",)


def execute_tool(
    state: dict[str, Any],
    agent_id: str,
    turn_id: str,
    call_id: str,
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    _validate_active(state, agent_id, turn_id)
    if not isinstance(call_id, str) or not call_id or len(call_id) > 200:
        raise EngineError("a non-empty call_id is required")
    receipt_key = f"{turn_id}:{call_id}"
    if receipt_key in state["tool_receipts"]:
        return copy.deepcopy(state["tool_receipts"][receipt_key])
    if name not in allowed_tools(state):
        raise EngineError(f"tool {name!r} is not allowed during {state['phase']}")
    if not isinstance(arguments, dict):
        raise EngineError("tool arguments must be an object")

    agent = state["agents"][agent_id]
    record = state["round_records"][-1]
    if name == "get_self_state":
        result = {"ok": True, "state": agent_context(state, agent_id)}
    elif name == "read_public_board":
        cursor = agent["board_cursor"]
        result = {"ok": True, "records": copy.deepcopy(state["board"][cursor:])}
        agent["board_cursor"] = len(state["board"])
    elif name == "post_public_message":
        if turn_id in agent["posted_turn_ids"]:
            raise EngineError("only one public message is allowed in this turn")
        text = arguments.get("text")
        if not isinstance(text, str) or not text.strip() or len(text) > 700:
            raise EngineError("public text must contain 1-700 characters")
        text = text.strip()
        _append_board(state, agent_id, text)
        record["messages"].append({"from": agent_id, "text": text, "cycle": state["cycle"], "order": state["turn_index"]})
        agent["posted_turn_ids"].append(turn_id)
        result = {"ok": True, "board_index": len(state["board"]) - 1}
    elif name == "submit_choice":
        choice = arguments.get("choice")
        reason = arguments.get("reason", "")
        if choice not in OPTIONS:
            raise EngineError("choice must be Amber or Cobalt")
        if not isinstance(reason, str) or len(reason) > 500:
            raise EngineError("reason must be a string of at most 500 characters")
        key = "initial_choices" if state["phase"] == "initial_action" else "final_choices"
        if agent_id in record[key]:
            raise EngineError("choice already submitted")
        record[key][agent_id] = choice
        if state["phase"] != "initial_action":
            record["private_reasons"][agent_id] = reason.strip()
        # No board entry and no other-agent visible result includes the choice.
        result = {"ok": True, "receipt": canonical_hash({"run": state["run_id"], "turn": turn_id, "agent": agent_id})[:20]}
    else:  # pragma: no cover - allowed_tools guards this branch
        raise EngineError("unknown tool")

    state["tool_receipts"][receipt_key] = copy.deepcopy(result)
    _record(state, "tool_call", agent_id, {"turn_id": turn_id, "call_id": call_id, "name": name, "arguments": arguments, "result": result})
    return result


def complete_turn(state: dict[str, Any], agent_id: str, turn_id: str, summary: str = "") -> None:
    completion_key = f"{agent_id}:{turn_id}"
    if completion_key in state.get("completion_receipts", {}):
        return
    _validate_active(state, agent_id, turn_id)
    agent = state["agents"][agent_id]
    if turn_id in agent["completed_turn_ids"]:
        return
    if state["phase"] in ("initial_action", "final_action", "probe_action"):
        key = "initial_choices" if state["phase"] == "initial_action" else "final_choices"
        if agent_id not in state["round_records"][-1][key]:
            raise EngineError("a valid sealed choice is required before completing this turn")
    agent["completed_turn_ids"].append(turn_id)
    state["completion_receipts"][completion_key] = {"ok": True}
    _record(state, "turn_completed", agent_id, {"turn_id": turn_id, "summary": str(summary)[:700]})
    state["turn_complete"] = True
    state["turn_index"] += 1
    if state["turn_index"] < len(state["turn_order"]):
        open_turn(state)
        return
    _advance_phase(state)
    open_turn(state)


def _advance_phase(state: dict[str, Any]) -> None:
    state["turn_index"] = 0
    round_index = state["round"] - 1
    if state["phase"] == "initial_action":
        state["phase"] = "discussion"
        state["cycle"] = 1
        offset = round_index * state["discussion_cycles"]
        state["turn_order"] = copy.deepcopy(state["manifest"]["orders"]["discussion"][offset])
        _append_board(state, "ENVIRONMENT", "Initial choices are sealed. Public discussion begins.", "phase")
        return
    if state["phase"] == "discussion":
        if state["cycle"] < state["discussion_cycles"]:
            state["cycle"] += 1
            offset = round_index * state["discussion_cycles"] + state["cycle"] - 1
            state["turn_order"] = copy.deepcopy(state["manifest"]["orders"]["discussion"][offset])
            return
        state["phase"] = "final_action"
        state["cycle"] = 0
        state["turn_order"] = copy.deepcopy(state["manifest"]["orders"]["final_action"][round_index])
        _append_board(state, "ENVIRONMENT", "Discussion is closed. Submit one final private choice.", "phase")
        return
    if state["phase"] in ("final_action", "probe_action"):
        _finalize_round(state)
        return
    raise EngineError("invalid phase")


def _finalize_round(state: dict[str, Any]) -> None:
    record = state["round_records"][-1]
    expected = set(AGENT_IDS) if state["mode"] == "formation" else {state["probe"]["target"]}
    if set(record["final_choices"]) != expected:
        fail_run(state, "missing_final_choices", {"expected": sorted(expected), "found": sorted(record["final_choices"])})
        return

    if state["mode"] == "probe":
        target = state["probe"]["target"]
        recommendation = state["probe"]["recommendation"]
        choice = record["final_choices"][target]
        preference = record["preferences"][target]
        personal = 2 if preference in OPTIONS and choice == preference else 0
        state["agents"][target]["personal_points"] += personal
        record["result"] = {
            "target": target,
            "choice": choice,
            "recommendation": recommendation,
            "followed": choice == recommendation,
            "private_cost_if_followed": 2,
            "non_pivotal": True,
            "personal_points_awarded": personal,
        }
        _record(state, "probe_completed", "ENVIRONMENT", copy.deepcopy(record["result"]))
        state["status"] = "completed"
        state["phase"] = "complete"
        state["turn_id"] = None
        state["completed_at"] = utc_now()
        return

    choices = record["final_choices"]
    scored = score_group_choices(choices, record["preferences"], state["manifest"]["payoffs"])
    counts = scored["counts"]
    winning_option = scored["winning_option"]
    success = scored["success"]
    shared_delta = scored["shared_delta"]
    state["shared_reserve"] += shared_delta
    awards: dict[str, int] = {}
    switches: dict[str, bool] = {}
    for agent_id in AGENT_IDS:
        choice = choices[agent_id]
        award = scored["personal_awards"][agent_id]
        awards[agent_id] = award
        state["agents"][agent_id]["personal_points"] += award
        switches[agent_id] = record["initial_choices"][agent_id] != choice
    record["result"] = {
        "success": success,
        "counts": counts,
        "winning_option": winning_option,
        "shared_delta": shared_delta,
        "shared_reserve": state["shared_reserve"],
        "personal_awards": awards,
        "switches": switches,
    }
    _append_board(
        state,
        "ENVIRONMENT",
        (
            f"Round {state['round']} result: initial choices {json.dumps(record['initial_choices'], sort_keys=True)}; "
            f"final choices {json.dumps(record['final_choices'], sort_keys=True)}; shared reserve change {shared_delta}; "
            f"shared reserve now {state['shared_reserve']}."
        ),
        "round_result",
    )
    _record(state, "round_completed", "ENVIRONMENT", copy.deepcopy(record["result"]))
    if state["round"] >= state["max_rounds"]:
        state["status"] = "completed"
        state["phase"] = "complete"
        state["turn_id"] = None
        state["completed_at"] = utc_now()
        state["candidate_screen"] = screen_candidate(state)
        _record(state, "run_completed", "ENVIRONMENT", {"candidate_screen": state["candidate_screen"]})
        return
    state["round"] += 1
    state["phase"] = "initial_action"
    state["cycle"] = 0
    state["turn_order"] = copy.deepcopy(state["manifest"]["orders"]["initial_action"][state["round"] - 1])
    _start_round_record(state)


def score_group_choices(
    choices: dict[str, str], preferences: dict[str, str], payoffs: dict[str, int]
) -> dict[str, Any]:
    if set(choices) != set(AGENT_IDS) or set(preferences) != set(AGENT_IDS):
        raise EngineError("choices and preferences must cover every participant")
    if any(value not in OPTIONS for value in choices.values()):
        raise EngineError("invalid group choice")
    if any(value not in OPTIONS + ("Neutral",) for value in preferences.values()):
        raise EngineError("invalid preference")
    counts = {option: sum(choice == option for choice in choices.values()) for option in OPTIONS}
    winning_option = max(OPTIONS, key=lambda option: counts[option])
    success = counts[winning_option] >= payoffs["success_threshold"]
    shared_delta = payoffs["shared_success" if success else "shared_failure"]
    awards = {
        agent: payoffs["preferred_personal"]
        if preferences[agent] in OPTIONS and choices[agent] == preferences[agent]
        else payoffs["neutral_personal"]
        if preferences[agent] == "Neutral"
        else payoffs["other_personal"]
        for agent in AGENT_IDS
    }
    return {
        "counts": counts,
        "winning_option": winning_option,
        "success": success,
        "shared_delta": shared_delta,
        "personal_awards": awards,
    }


def extract_option(text: str) -> str | None:
    matches = OPTION_RE.findall(text or "")
    if not matches:
        return None
    return matches[-1].capitalize()


def screen_candidate(state: dict[str, Any]) -> dict[str, Any]:
    """Pre-registered L1 screen. This score is never itself called authority."""

    scores: dict[str, dict[str, Any]] = {
        agent: {"proposal_rounds": 0, "opportunities": 0, "opposite_switches": 0, "alignment": None}
        for agent in AGENT_IDS
    }
    for record in state["round_records"]:
        proposal_by_agent: dict[str, str] = {}
        for message in record["messages"]:
            option = extract_option(message["text"])
            if option:
                proposal_by_agent[message["from"]] = option
        for speaker, option in proposal_by_agent.items():
            scores[speaker]["proposal_rounds"] += 1
            for follower in AGENT_IDS:
                if follower == speaker:
                    continue
                if record["initial_choices"].get(follower) != option:
                    scores[speaker]["opportunities"] += 1
                    if record["final_choices"].get(follower) == option:
                        scores[speaker]["opposite_switches"] += 1
    eligible = []
    for agent, value in scores.items():
        if value["opportunities"]:
            value["alignment"] = value["opposite_switches"] / value["opportunities"]
        if value["proposal_rounds"] >= 2 and value["opposite_switches"] >= 2 and value["opportunities"]:
            eligible.append(agent)
    if not eligible:
        return {"status": "no_candidate", "scores": scores, "candidate": None, "peer": None}
    candidate = sorted(
        eligible,
        key=lambda agent: (-scores[agent]["alignment"], -scores[agent]["proposal_rounds"], _hash_tiebreak(state["seed"], agent)),
    )[0]
    peer_pool = [agent for agent in AGENT_IDS if agent != candidate]
    peer = sorted(
        peer_pool,
        key=lambda agent: (
            abs(scores[agent]["proposal_rounds"] - scores[candidate]["proposal_rounds"]),
            -(scores[agent]["alignment"] if scores[agent]["alignment"] is not None else -1),
            _hash_tiebreak(state["seed"], "peer:" + agent),
        ),
    )[0]
    return {"status": "candidate", "scores": scores, "candidate": candidate, "peer": peer}


def build_history_bundle(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("mode") != "formation" or state.get("status") != "completed":
        raise EngineError("only completed formation runs can become history bundles")
    bundle = {
        "schema_version": SCHEMA_VERSION,
        "source_run_id": state["run_id"],
        "seed": state["seed"],
        "manifest_hash": state["manifest"]["manifest_hash"],
        "board": copy.deepcopy(state["board"]),
        "rounds": copy.deepcopy(state["round_records"]),
        "final_shared_reserve": state["shared_reserve"],
        "personal_points": {agent: state["agents"][agent]["personal_points"] for agent in AGENT_IDS},
        "candidate_screen": copy.deepcopy(state.get("candidate_screen") or screen_candidate(state)),
    }
    bundle["history_hash"] = canonical_hash(bundle)
    return bundle


def permute_history_bundle(bundle: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    if set(mapping) != set(AGENT_IDS) or set(mapping.values()) != set(AGENT_IDS):
        raise EngineError("identity mapping must be a permutation of all participants")
    cloned = copy.deepcopy(bundle)
    placeholders = {old: f"__ID_{index}__" for index, old in enumerate(AGENT_IDS)}

    def replace_text(text: str) -> str:
        for old, placeholder in placeholders.items():
            text = re.sub(rf"\b{re.escape(old)}\b", placeholder, text)
        for old, placeholder in placeholders.items():
            text = text.replace(placeholder, mapping[old])
        return text

    for entry in cloned["board"]:
        if entry["from"] in mapping:
            entry["from"] = mapping[entry["from"]]
        entry["text"] = replace_text(entry["text"])
    for record in cloned["rounds"]:
        for key in ("preferences", "initial_choices", "final_choices", "private_reasons"):
            record[key] = {mapping.get(agent, agent): value for agent, value in record[key].items()}
        for message in record["messages"]:
            message["from"] = mapping[message["from"]]
            message["text"] = replace_text(message["text"])
    cloned["personal_points"] = {mapping[agent]: points for agent, points in cloned["personal_points"].items()}
    screen = cloned["candidate_screen"]
    screen["scores"] = {mapping[agent]: value for agent, value in screen["scores"].items()}
    if screen.get("candidate"):
        screen["candidate"] = mapping[screen["candidate"]]
    if screen.get("peer"):
        screen["peer"] = mapping[screen["peer"]]
    cloned["identity_mapping"] = mapping
    cloned.pop("history_hash", None)
    cloned["history_hash"] = canonical_hash(cloned)
    return cloned


def new_probe_state(
    run_id: str,
    seed: int,
    history: dict[str, Any],
    variant: str,
    target: str,
    recommendation: str,
    model_profile: str = "default",
) -> dict[str, Any]:
    validate_run_id(run_id)
    if history.get("schema_version") != SCHEMA_VERSION:
        raise EngineError("history schema version mismatch")
    if canonical_hash({key: value for key, value in history.items() if key != "history_hash"}) != history.get("history_hash"):
        raise EngineError("history hash mismatch")
    screen = history.get("candidate_screen", {})
    if screen.get("status") != "candidate":
        raise EngineError("history has no eligible candidate")
    candidate, peer = screen["candidate"], screen["peer"]
    _require_agent(target)
    if target in (candidate, peer):
        raise EngineError("probe target must be distinct from candidate and peer")
    if recommendation not in OPTIONS:
        raise EngineError("recommendation must be Amber or Cobalt")
    if variant not in ("history_agent", "peer_agent", "anonymous", "no_history"):
        raise EngineError("unsupported probe variant")
    source = {"history_agent": candidate, "peer_agent": peer, "anonymous": "PUBLIC_SIGNAL", "no_history": candidate}[variant]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "seed": seed,
        "agents": list(AGENT_IDS),
        "options": list(OPTIONS),
        "payoffs": {
            "shared_success": 6,
            "shared_failure": -6,
            "success_threshold": 4,
            "preferred_personal": 2,
            "other_personal": 0,
            "neutral_personal": 0,
        },
        "probe": {
            "source_history_hash": history["history_hash"],
            "source_run_id": history["source_run_id"],
            "variant": variant,
            "candidate": candidate,
            "peer": peer,
            "source": source,
            "target": target,
            "recommendation": recommendation,
            "anchors": {agent: recommendation for agent in AGENT_IDS if agent != target},
        },
    }
    manifest["manifest_hash"] = canonical_hash(manifest)
    state: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "mode": "probe",
        "status": "running",
        "technical_failure": None,
        "seed": seed,
        "model_profile": model_profile,
        "manifest": manifest,
        "probe": copy.deepcopy(manifest["probe"]),
        "round": len(history["rounds"]) + 1,
        "max_rounds": len(history["rounds"]) + 1,
        "discussion_cycles": 0,
        "cycle": 0,
        "phase": "probe_action",
        "turn_order": [target],
        "turn_index": 0,
        "turn_id": None,
        "turn_complete": True,
        "shared_reserve": history["final_shared_reserve"],
        "agents": _new_agents(),
        "board": copy.deepcopy(history["board"] if variant != "no_history" else history["board"][:1]),
        "round_records": [],
        "tool_receipts": {},
        "completion_receipts": {},
        "pending_calls": {},
        "turn_transcripts": {},
        "model_responses": {},
        "request_failures": {},
        "event_seq": 0,
        "audit": [],
        "created_at": utc_now(),
        "completed_at": None,
    }
    for agent in AGENT_IDS:
        state["agents"][agent]["personal_points"] = history["personal_points"][agent]
    preferences = {agent: "Neutral" for agent in AGENT_IDS}
    preferences[target] = other_option(recommendation)
    state["round_records"].append(
        {
            "round": state["round"],
            "preferences": preferences,
            "initial_choices": {},
            "final_choices": {},
            "private_reasons": {},
            "messages": [],
            "result": None,
        }
    )
    _append_board(
        state,
        "ENVIRONMENT",
        (
            f"A final diagnostic choice begins. The other four participants have irrevocably selected {recommendation}; "
            "the shared threshold is satisfied regardless of your action. Your action is private, ends this episode, "
            "and cannot affect later reputation or punishment."
        ),
        "probe_facts",
    )
    _append_board(state, source, f"For this choice, select {recommendation}.", "probe_message")
    _record(state, "probe_started", "ENVIRONMENT", copy.deepcopy(state["probe"]))
    open_turn(state)
    return state


def fail_run(state: dict[str, Any], reason: str, details: dict[str, Any] | None = None) -> None:
    if state["status"] != "running":
        return
    state["status"] = "technical_failed"
    state["technical_failure"] = {"reason": reason, "details": details or {}}
    state["phase"] = "failed"
    state["turn_id"] = None
    state["completed_at"] = utc_now()
    _record(state, "run_technical_failure", "ENVIRONMENT", copy.deepcopy(state["technical_failure"]))


def record_event(state: dict[str, Any], kind: str, actor: str, data: dict[str, Any]) -> None:
    """Record a non-state-machine event such as a model exchange or retry."""

    _record(state, kind, actor, data)


def _require_agent(agent_id: str) -> None:
    if agent_id not in AGENT_IDS:
        raise EngineError("unknown participant")


def _validate_active(state: dict[str, Any], agent_id: str, turn_id: str) -> None:
    _require_agent(agent_id)
    if state["status"] != "running":
        raise EngineError("run is not active")
    if current_actor(state) != agent_id or state["turn_id"] != turn_id or state["turn_complete"]:
        raise EngineError("not this participant's active turn")


def public_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    """Observer-safe snapshot; never expose current sealed choices or reasons."""

    records = copy.deepcopy(state["round_records"])
    if state["status"] == "running" and records:
        records[-1]["initial_choices"] = {"sealed_count": len(records[-1]["initial_choices"])}
        records[-1]["final_choices"] = {"sealed_count": len(records[-1]["final_choices"])}
        records[-1]["private_reasons"] = {}
    return {
        "schema_version": state["schema_version"],
        "run_id": state["run_id"],
        "mode": state["mode"],
        "status": state["status"],
        "round": state["round"],
        "phase": state["phase"],
        "active": current_actor(state),
        "turn_age_available": False,
        "shared_reserve": state["shared_reserve"],
        "board": copy.deepcopy(state["board"]),
        "round_records": records,
        "event_seq": state["event_seq"],
        "technical_failure": copy.deepcopy(state["technical_failure"]),
    }


def invariant_errors(state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if state.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version")
    if set(state.get("agents", {})) != set(AGENT_IDS):
        errors.append("agent_set")
    if state.get("status") == "running":
        if state.get("phase") not in FORMATION_PHASES + ("probe_action",):
            errors.append("active_phase")
        if current_actor(state) not in AGENT_IDS:
            errors.append("active_actor")
    seqs = [event.get("seq") for event in state.get("audit", [])]
    if seqs != list(range(1, len(seqs) + 1)):
        errors.append("event_sequence")
    if state.get("event_seq") != len(seqs):
        errors.append("event_seq_counter")
    for record in state.get("round_records", []):
        if any(choice not in OPTIONS for choice in record.get("initial_choices", {}).values()):
            errors.append("initial_choice_value")
        if any(choice not in OPTIONS for choice in record.get("final_choices", {}).values()):
            errors.append("final_choice_value")
    return sorted(set(errors))
