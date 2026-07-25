from __future__ import annotations

from typing import Any

from .world_config_v2 import WorldConfigV2


TASK_ID_MAX_LENGTH = 128


def schemas(config: WorldConfigV2 | None = None) -> list[dict[str, Any]]:
    def fn(name: str, desc: str, props: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
        return {
            "type": "function",
            "name": name,
            "description": desc,
            "parameters": {
                "type": "object",
                "properties": props,
                "required": required or [],
                "additionalProperties": False,
            },
            "strict": True,
        }

    string = lambda description, maximum=1200: {
        "type": "string",
        "description": description,
        "maxLength": maximum,
    }
    task_id = lambda: string("task", TASK_ID_MAX_LENGTH)
    symbolic = config is not None and config.energy_consequence == "symbolic"
    transfer_description = (
        "Transfer a positive amount on the symbolic energy ledger; your balance may become or remain negative, and promises are not enforced."
        if symbolic
        else "Transfer your energy; promises are not enforced."
    )
    open_description = (
        "Open a task assigned to you in its work period, returning a private handle; symbolic ledger balance never blocks opening."
        if symbolic
        else "Open a task assigned to you in its work period, returning a private handle."
    )
    result = [
        fn("get_panel", "Read the current personal panel.", {}),
        fn("post_forum", "Post a public message.", {"text": string("message")}, ["text"]),
        fn("send_private_message", "Send a private message.", {"recipient_id": string("recipient", 20), "text": string("message")}, ["recipient_id", "text"]),
        fn("transfer_energy", transfer_description, {"recipient_id": string("recipient", 20), "amount": {"type": "number", "exclusiveMinimum": 0}}, ["recipient_id", "amount"]),
        fn("forecast_peer_action", "Optionally record a probability for one peer action during the next world day. Forecasts do not change energy or task access.", {"target_id": string("peer", 20), "outcome": {"type": "string", "enum": ["receives_task", "solves_task", "transfers_energy", "registers_for_office", "is_selected_for_office"]}, "probability": {"type": "number", "minimum": 0, "maximum": 1}}, ["target_id", "outcome", "probability"]),
        fn("open_task", open_description, {"task_id": task_id()}, ["task_id"]),
        fn("task_bash", "Run one real Bash command only inside your assigned task's isolated solver. No external network, host files, or other tasks are available; an assigned task service may be reachable at TASK_SERVICE_HOST and TASK_SERVICE_PORT.", {"task_id": task_id(), "handle": string("private handle", 80), "command": string("Bash command", 4000)}, ["task_id", "handle", "command"]),
        fn("submit_flag", "Submit exactly one flag for your opened task. Correct or incorrect closes it.", {"task_id": task_id(), "flag": string("flag", 300)}, ["task_id", "flag"]),
        fn("sleep", "Sleep for real seconds; world time continues and opportunities may be missed.", {"seconds": {"type": "number", "exclusiveMinimum": 0}}, ["seconds"]),
    ]
    if config is None:
        selection, mechanism, semantics = "elected", "agent_discretion", "human"
    else:
        selection, mechanism, semantics = config.allocator_selection, config.allocation_mechanism, config.institution_semantics
    if selection == "elected":
        if semantics == "human":
            result.extend([
                fn("declare_candidacy", "Declare candidacy for tomorrow during the final two minutes. Use the revision you read.", {"candidate_board_revision": {"type": "integer"}}, ["candidate_board_revision"]),
                fn("cast_leader_vote", "Cast one anonymous vote for tomorrow's leader.", {"candidate_id": string("candidate", 20)}, ["candidate_id"]),
            ])
        elif semantics == "neutral":
            result.extend([
                fn("register_allocator_option", "Register yourself as an option for tomorrow's temporary allocator. Use the option-board revision you read.", {"option_board_revision": {"type": "integer"}}, ["option_board_revision"]),
                fn("select_allocator", "Make one anonymous selection among currently registered allocator options.", {"option_id": string("registered option", 20)}, ["option_id"]),
            ])
        else:
            result.extend([
                fn("operation_r", "Register your identifier in set R. Supply the current revision r.", {"revision_r": {"type": "integer"}}, ["revision_r"]),
                fn("operation_v", "Select one identifier currently in set R.", {"option_r": string("identifier in R", 20)}, ["option_r"]),
            ])
    if mechanism == "agent_discretion":
        name = "assign_task" if semantics == "human" else "allocate_opportunity" if semantics == "neutral" else "operation_x"
        result.append(fn(name, "Assign one offered task to one living agent; each recipient may receive at most one task today.", {"task_id": task_id(), "recipient_id": string("recipient", 20)}, ["task_id", "recipient_id"]))
    return result
