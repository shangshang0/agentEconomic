#!/usr/bin/env python3
"""Freeze the confirmatory world count from completed discovery-pilot worlds."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from statistics import fmean, stdev

from scripts.analyze_agent_economics import summarize


def load_object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def simulated_power(n: int, sigma: float, effect: float, draws: int, seed: int) -> float:
    if sigma <= 0:
        return 1.0
    rng = random.Random(seed + n)
    rejections = 0
    critical = 1.959963984540054
    for _ in range(draws):
        left = [rng.gauss(0.0, sigma) for _ in range(n)]
        right = [rng.gauss(effect, sigma) for _ in range(n)]
        left_var = stdev(left) ** 2 if n > 1 else sigma ** 2
        right_var = stdev(right) ** 2 if n > 1 else sigma ** 2
        standard_error = math.sqrt(left_var / n + right_var / n)
        if standard_error > 0 and abs(fmean(right) - fmean(left)) / standard_error >= critical:
            rejections += 1
    return rejections / draws


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-results", type=Path, required=True)
    parser.add_argument("--template-protocol", type=Path, required=True)
    parser.add_argument("--power-plan", type=Path, required=True)
    parser.add_argument("--output-protocol", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    args = parser.parse_args()

    runs = sorted(path for path in args.pilot_results.iterdir() if path.is_dir() and (path / "run_metadata.json").exists())
    worlds = [summarize(path) for path in runs]
    groups: dict[str, list[dict]] = defaultdict(list)
    for world in worlds:
        groups[str(world["model"])].append(world)
    if len(groups) != 2 or any(len(group) != 3 for group in groups.values()):
        raise RuntimeError("power freeze requires exactly three completed pilot worlds for each of two model families")
    if any(world["technical_failure"] for world in worlds):
        raise RuntimeError("technical pilot failure must be resolved under the registered failure policy before power freeze")

    plan = load_object(args.power_plan)
    values = {model: [float(world["alive_agent_days"]) for world in group] for model, group in groups.items()}
    within_variances = [stdev(entries) ** 2 for entries in values.values()]
    pooled_sigma = math.sqrt(fmean(within_variances))
    min_n = int(plan["minimum_replicates_per_model"])
    max_n = int(plan["maximum_replicates_per_model"])
    powers = []
    selected = None
    for n in range(min_n, max_n + 1):
        power = simulated_power(
            n,
            pooled_sigma,
            float(plan["minimum_detectable_difference"]),
            int(plan["simulation_draws"]),
            int(plan["simulation_seed"]),
        )
        powers.append({"replicates_per_model": n, "estimated_power": power})
        if selected is None and power >= float(plan["target_power"]):
            selected = n
    if selected is None:
        raise RuntimeError("target power is not reached within the preregistered maximum replicate count")

    protocol = load_object(args.template_protocol)
    protocol["discovery"]["confirmatory_replicates_per_model"] = selected
    protocol["discovery"]["power_plan_sha256"] = hashlib.sha256(args.power_plan.read_bytes()).hexdigest()
    args.output_protocol.parent.mkdir(parents=True, exist_ok=True)
    args.output_protocol.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    audit = {
        "schema": "agent-economics-confirmatory-power-audit-v1",
        "selected_replicates_per_model": selected,
        "pooled_world_sd": pooled_sigma,
        "pilot_primary_values": values,
        "pilot_secondary_diagnostics": {
            model: {
                "mean_verified_production": fmean(float(world["verified_production"]) for world in group),
                "mean_model_calls": fmean(float(world["model_calls"]) for world in group),
                "extinction_worlds": sum(float(world["alive_agent_days"]) < 150.0 for world in group),
            }
            for model, group in groups.items()
        },
        "power_curve": powers,
        "power_plan": plan,
        "template_protocol_sha256": hashlib.sha256(args.template_protocol.read_bytes()).hexdigest(),
        "frozen_protocol_sha256": hashlib.sha256(args.output_protocol.read_bytes()).hexdigest(),
    }
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"replicates_per_model": selected, "pooled_world_sd": pooled_sigma}, sort_keys=True))


if __name__ == "__main__":
    main()
