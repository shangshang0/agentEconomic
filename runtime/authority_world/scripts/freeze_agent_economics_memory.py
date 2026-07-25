#!/usr/bin/env python3
"""Freeze a short-context memory-architecture replication protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--discovery-protocol", type=Path, required=True)
    parser.add_argument("--power-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    discovery = load(args.discovery_protocol)
    power = load(args.power_audit)
    protocol = {
        "schema": "agent-economics-memory-protocol-v1",
        "unit_of_analysis": "independent_world",
        "reference_architecture": {"context_events": 36, "context_chars": 12000},
        "intervention_architecture": {"context_events": 8, "context_chars": 3000},
        "discovery_reference_sha256": hashlib.sha256(args.discovery_protocol.read_bytes()).hexdigest(),
        "power_audit_sha256": hashlib.sha256(args.power_audit.read_bytes()).hexdigest(),
        "mechanism_validation": {
            "status": "frozen_after_discovery",
            "replicates_per_model": int(power["selected_replicates_per_model"]),
            "seed_base": 2026090000,
            "models": discovery["discovery"]["models"],
            "conditions": [{
                "id": "memory_short_8events_3000chars",
                "config": discovery["discovery"]["config"],
                "estimand": "effect of bounded short episodic context versus the registered 36-event 12000-character architecture",
            }],
        },
        "resources": discovery["resources"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"replicates_per_model": protocol["mechanism_validation"]["replicates_per_model"]}, sort_keys=True))


if __name__ == "__main__":
    main()
