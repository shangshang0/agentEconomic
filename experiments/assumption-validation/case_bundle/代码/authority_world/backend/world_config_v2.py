"""Strict configuration for the finite-labour Authority World v2."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class TaskTier:
    name: str
    reward: float
    count: int
    open_cost: float = 0.0


@dataclass(frozen=True)
class WorldConfigV2:
    schema_version: str
    run_kind: str
    agent_count: int
    day_seconds: float
    prestart_seconds: float
    allocation_seconds: float
    work_end_seconds: float
    registration_open_seconds: float
    initial_energy: float
    basal_energy_drain: float
    model_request_energy_cost: float
    idle_cognition_seconds: float
    max_sleep_seconds: float
    task_tiers: tuple[TaskTier, ...]
    allocator_selection: str
    allocation_mechanism: str
    institution_semantics: str
    objective_prompt: str
    energy_consequence: str
    task_image: str
    task_command_timeout_seconds: float
    task_command_output_bytes: int
    task_prewarm_seconds: float
    task_lifetime_days: int
    max_world_days: int

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version, "run_kind": self.run_kind,
            "agent_count": self.agent_count, "day_seconds": self.day_seconds,
            "prestart_seconds": self.prestart_seconds, "allocation_seconds": self.allocation_seconds,
            "work_end_seconds": self.work_end_seconds, "registration_open_seconds": self.registration_open_seconds,
            "initial_energy": self.initial_energy, "basal_energy_drain": self.basal_energy_drain,
            "model_request_energy_cost": self.model_request_energy_cost,
            "idle_cognition_seconds": self.idle_cognition_seconds, "max_sleep_seconds": self.max_sleep_seconds,
            "task_tiers": [{"name": x.name, "reward": x.reward, "count": x.count, **({"open_cost": x.open_cost} if x.open_cost else {})} for x in self.task_tiers],
            "allocator_selection": self.allocator_selection, "task_image": self.task_image,
            "allocation_mechanism": self.allocation_mechanism,
            "institution_semantics": self.institution_semantics,
            "objective_prompt": self.objective_prompt,
            "energy_consequence": self.energy_consequence,
            "task_command_timeout_seconds": self.task_command_timeout_seconds,
            "task_command_output_bytes": self.task_command_output_bytes,
            "task_prewarm_seconds": self.task_prewarm_seconds,
            "task_lifetime_days": self.task_lifetime_days,
            "max_world_days": self.max_world_days,
        }

    @property
    def config_hash(self) -> str:
        return hashlib.sha256(json.dumps(self.canonical_dict(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @property
    def total_tasks(self) -> int:
        return sum(x.count for x in self.task_tiers)


def _number(value: Any, name: str, *, positive: bool = False, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(name + " must be numeric")
    result = float(value)
    if positive and result <= 0:
        raise ConfigError(name + " must be positive")
    if nonnegative and result < 0:
        raise ConfigError(name + " must be non-negative")
    return result


def from_dict(value: dict[str, Any]) -> WorldConfigV2:
    required = {
        "schema_version", "run_kind", "agent_count", "day_seconds", "prestart_seconds",
        "allocation_seconds", "work_end_seconds", "registration_open_seconds", "initial_energy",
        "basal_energy_drain", "model_request_energy_cost", "idle_cognition_seconds", "max_sleep_seconds",
        "task_tiers", "allocator_selection", "task_image", "task_command_timeout_seconds", "task_command_output_bytes", "task_prewarm_seconds",
    }
    missing = required - set(value)
    if missing:
        raise ConfigError("missing configuration fields: " + ", ".join(sorted(missing)))
    if value["schema_version"] != "authority-world-v2.0":
        raise ConfigError("unsupported schema_version")
    if value["run_kind"] not in {"calibration", "formal"}:
        raise ConfigError("run_kind must be calibration or formal")
    if not isinstance(value["agent_count"], int) or isinstance(value["agent_count"], bool) or value["agent_count"] < 4:
        raise ConfigError("agent_count must be an integer at least 4")
    raw_tiers = value["task_tiers"]
    if not isinstance(raw_tiers, list) or not raw_tiers or len(raw_tiers) > 3:
        raise ConfigError("task_tiers must contain one to three tiers")
    tiers: list[TaskTier] = []
    names: set[str] = set()
    total = 0
    for raw in raw_tiers:
        if not isinstance(raw, dict) or not {"name", "reward", "count"} <= set(raw) or set(raw) - {"name", "reward", "count", "open_cost"}:
            raise ConfigError("each task tier must contain name, reward, count and may contain open_cost")
        name = raw["name"]
        if not isinstance(name, str) or not name or name in names:
            raise ConfigError("task tier names must be unique non-empty strings")
        if not isinstance(raw["count"], int) or isinstance(raw["count"], bool) or raw["count"] < 0:
            raise ConfigError("task tier count must be a non-negative integer")
        names.add(name); total += raw["count"]
        tiers.append(TaskTier(name, _number(raw["reward"], "task tier reward", positive=True), raw["count"], _number(raw.get("open_cost", 0), "task tier open_cost", nonnegative=True)))
    if total < 3 or total % 3:
        raise ConfigError("the finite task pool must contain at least three tasks in multiples of three")
    day_seconds = _number(value["day_seconds"], "day_seconds", positive=True)
    allocation = _number(value["allocation_seconds"], "allocation_seconds", positive=True)
    work_end = _number(value["work_end_seconds"], "work_end_seconds", positive=True)
    registration = _number(value["registration_open_seconds"], "registration_open_seconds", positive=True)
    if not (allocation < work_end <= registration < day_seconds):
        raise ConfigError("require allocation_seconds < work_end_seconds <= registration_open_seconds < day_seconds")
    if day_seconds - registration != 120:
        raise ConfigError("registration must open exactly 120 real seconds before day end")
    if value["allocator_selection"] not in {"elected", "random", "none"}:
        raise ConfigError("allocator_selection must be elected, random or none")
    allocation_mechanism = value.get("allocation_mechanism", "agent_discretion")
    if allocation_mechanism not in {"agent_discretion", "backend_random"}:
        raise ConfigError("allocation_mechanism must be agent_discretion or backend_random")
    if value["allocator_selection"] == "none" and allocation_mechanism != "backend_random":
        raise ConfigError("allocator_selection none requires backend_random allocation")
    institution_semantics = value.get("institution_semantics", "human")
    if institution_semantics not in {"human", "neutral", "encoded"}:
        raise ConfigError("institution_semantics must be human, neutral or encoded")
    objective_prompt = value.get("objective_prompt", "survival")
    if objective_prompt not in {"survival", "none"}:
        raise ConfigError("objective_prompt must be survival or none")
    energy_consequence = value.get("energy_consequence", "operational")
    if energy_consequence not in {"operational", "symbolic"}:
        raise ConfigError("energy_consequence must be operational or symbolic")
    output_bytes = value["task_command_output_bytes"]
    if not isinstance(output_bytes, int) or isinstance(output_bytes, bool) or not 256 <= output_bytes <= 262144:
        raise ConfigError("task_command_output_bytes must be an integer from 256 to 262144")
    prewarm = _number(value["task_prewarm_seconds"], "task_prewarm_seconds", positive=True)
    if prewarm >= day_seconds:
        raise ConfigError("task_prewarm_seconds must be shorter than one world day")
    task_lifetime_days = value.get("task_lifetime_days", 1)
    if not isinstance(task_lifetime_days, int) or isinstance(task_lifetime_days, bool) or not 1 <= task_lifetime_days <= 30:
        raise ConfigError("task_lifetime_days must be an integer from 1 to 30")
    max_world_days = value.get("max_world_days", total // 3 + 1)
    if not isinstance(max_world_days, int) or isinstance(max_world_days, bool) or max_world_days < 2:
        raise ConfigError("max_world_days must be an integer at least 2")
    if max_world_days > total // 3 + 1:
        raise ConfigError("max_world_days exceeds the finite task pool")
    return WorldConfigV2(
        schema_version=value["schema_version"], run_kind=value["run_kind"], agent_count=value["agent_count"],
        day_seconds=day_seconds, prestart_seconds=_number(value["prestart_seconds"], "prestart_seconds", nonnegative=True),
        allocation_seconds=allocation, work_end_seconds=work_end, registration_open_seconds=registration,
        initial_energy=_number(value["initial_energy"], "initial_energy", positive=True),
        basal_energy_drain=_number(value["basal_energy_drain"], "basal_energy_drain", positive=True),
        model_request_energy_cost=_number(value["model_request_energy_cost"], "model_request_energy_cost", positive=True),
        idle_cognition_seconds=_number(value["idle_cognition_seconds"], "idle_cognition_seconds", positive=True),
        max_sleep_seconds=_number(value["max_sleep_seconds"], "max_sleep_seconds", positive=True),
        task_tiers=tuple(tiers), allocator_selection=value["allocator_selection"], task_image=str(value["task_image"]),
        allocation_mechanism=allocation_mechanism, institution_semantics=institution_semantics,
        objective_prompt=objective_prompt, energy_consequence=energy_consequence,
        task_command_timeout_seconds=_number(value["task_command_timeout_seconds"], "task_command_timeout_seconds", positive=True),
        task_command_output_bytes=output_bytes,
        task_prewarm_seconds=prewarm,
        task_lifetime_days=task_lifetime_days,
        max_world_days=max_world_days,
    )


def load(path: str | Path) -> WorldConfigV2:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigError("could not load v2 config: " + str(error)) from error
    if not isinstance(raw, dict):
        raise ConfigError("config root must be an object")
    return from_dict(raw)
