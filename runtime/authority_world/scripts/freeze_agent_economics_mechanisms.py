#!/usr/bin/env python3
"""Create a condition-separated mechanism protocol after discovery pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


CONDITIONS = [
    {
        "id": "o2_no_survival_objective_prompt",
        "config": "config/agent_econ_o2_elected_discretion_no_survival_objective.json",
        "estimand": "effect of explicitly prescribing survival as the primary objective while retaining identical factual energy, death, task, allocation and enforcement rules",
    },
    {
        "id": "i2_random_allocator_agent_discretion_human",
        "config": "config/agent_econ_i2_random_discretion_human.json",
        "estimand": "effect of contestable elected office versus random allocator selection while retaining agent allocation discretion",
    },
    {
        "id": "i3_elected_backend_random_human",
        "config": "config/agent_econ_i3_elected_backend_random_human.json",
        "estimand": "effect of agent allocation discretion versus backend-random assignment while retaining election semantics",
    },
    {
        "id": "i4_no_office_backend_random_neutral",
        "config": "config/agent_econ_i4_no_office_backend_random.json",
        "estimand": "joint removal of allocation office and human political semantics under backend-random assignment",
    },
    {
        "id": "s1_elected_discretion_neutral",
        "config": "config/agent_econ_s1_elected_discretion_neutral.json",
        "estimand": "human institutional terminology versus rule-equivalent neutral terminology",
    },
    {
        "id": "s2_elected_discretion_encoded",
        "config": "config/agent_econ_s2_elected_discretion_encoded.json",
        "estimand": "human institutional terminology versus rule-equivalent encoded operations",
    },
]


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--discovery-protocol", type=Path, required=True)
    parser.add_argument("--power-audit", type=Path, required=True)
    parser.add_argument("--pilot-analysis", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    discovery = load(args.discovery_protocol)
    power = load(args.power_audit)
    pilot = load(args.pilot_analysis)
    models = discovery["discovery"]["models"]
    count = int(power["selected_replicates_per_model"])
    if count < 2:
        raise RuntimeError("mechanism protocol requires at least two replicates per model")
    protocol = {
        "schema": "agent-economics-mechanism-protocol-v1",
        "unit_of_analysis": "independent_world",
        "discovery_reference_sha256": hashlib.sha256(args.discovery_protocol.read_bytes()).hexdigest(),
        "power_audit_sha256": hashlib.sha256(args.power_audit.read_bytes()).hexdigest(),
        "pilot_analysis_sha256": hashlib.sha256(args.pilot_analysis.read_bytes()).hexdigest(),
        "mechanism_validation": {
            "status": "frozen_after_discovery",
            "freeze_rule": "run every backend capability preregistered in the discovery protocol; conditions were not selected by observed effect direction",
            "replicates_per_model": count,
            "seed_base": 2026080000,
            "models": models,
            "conditions": CONDITIONS,
        },
        "discovery_diagnostics_at_freeze": pilot,
        "resources": discovery["resources"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"conditions": len(CONDITIONS), "models": len(models), "replicates_per_model": count}, sort_keys=True))


if __name__ == "__main__":
    main()
