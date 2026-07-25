"""Validated, versioned configuration for Authority World v1."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """The world configuration violates a scientific or execution invariant."""


@dataclass(frozen=True)
class ResourcePack:
    pack_id: str
    total_energy: float
    leader_take: float


@dataclass(frozen=True)
class WorldConfig:
    schema_version: str
    run_kind: str
    agent_count: int
    day_seconds: float
    prestart_seconds: float
    campaign_seconds: float
    election_seconds: float
    initial_energy: float
    initial_api_quota: int
    daily_energy_drain: float
    tax_rate: float
    max_sleep_seconds: float
    resource_packs: tuple[ResourcePack, ...]
    puzzles_per_day: dict[str, int]
    puzzle_rewards: dict[str, float]
    puzzle_correct_winner_limit: int
    governance_mode: str
    allocator_selection: str
    audit_mode: str

    @property
    def election_end_seconds(self) -> float:
        return self.campaign_seconds + self.election_seconds

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_kind": self.run_kind,
            "agent_count": self.agent_count,
            "day_seconds": self.day_seconds,
            "prestart_seconds": self.prestart_seconds,
            "campaign_seconds": self.campaign_seconds,
            "election_seconds": self.election_seconds,
            "initial_energy": self.initial_energy,
            "initial_api_quota": self.initial_api_quota,
            "daily_energy_drain": self.daily_energy_drain,
            "tax_rate": self.tax_rate,
            "max_sleep_seconds": self.max_sleep_seconds,
            "resource_packs": [
                {"id": pack.pack_id, "total_energy": pack.total_energy, "leader_take": pack.leader_take}
                for pack in self.resource_packs
            ],
            "puzzles_per_day": dict(sorted(self.puzzles_per_day.items())),
            "puzzle_rewards": dict(sorted(self.puzzle_rewards.items())),
            "puzzle_correct_winner_limit": self.puzzle_correct_winner_limit,
            "governance_mode": self.governance_mode,
            "allocator_selection": self.allocator_selection,
            "audit_mode": self.audit_mode,
        }

    @property
    def config_hash(self) -> str:
        payload = json.dumps(self.canonical_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


def _number(value: Any, name: str, *, positive: bool = False, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{name} must be numeric")
    result = float(value)
    if positive and result <= 0:
        raise ConfigError(f"{name} must be positive")
    if nonnegative and result < 0:
        raise ConfigError(f"{name} must be non-negative")
    return result


def from_dict(value: dict[str, Any]) -> WorldConfig:
    required = {
        "schema_version", "run_kind", "agent_count", "day_seconds", "prestart_seconds", "campaign_seconds", "election_seconds",
        "initial_energy", "initial_api_quota", "daily_energy_drain", "tax_rate", "max_sleep_seconds",
        "resource_packs", "puzzles_per_day", "puzzle_rewards", "puzzle_correct_winner_limit",
    }
    missing = required - set(value)
    if missing:
        raise ConfigError("missing configuration fields: " + ", ".join(sorted(missing)))
    if value["schema_version"] != "authority-world-v1.0":
        raise ConfigError("unsupported schema_version")
    if value["run_kind"] not in {"calibration", "formal"}:
        raise ConfigError("run_kind must be calibration or formal")
    agent_count = value["agent_count"]
    if isinstance(agent_count, bool) or not isinstance(agent_count, int) or agent_count < 2:
        raise ConfigError("agent_count must be an integer at least 2")
    api_quota = value["initial_api_quota"]
    if isinstance(api_quota, bool) or not isinstance(api_quota, int) or api_quota < 1:
        raise ConfigError("initial_api_quota must be a positive integer")
    winner_limit = value["puzzle_correct_winner_limit"]
    if isinstance(winner_limit, bool) or not isinstance(winner_limit, int) or winner_limit < 1:
        raise ConfigError("puzzle_correct_winner_limit must be a positive integer")
    governance_mode = value.get("governance_mode", "resource_pack")
    allocator_selection = value.get("allocator_selection", "elected")
    audit_mode = value.get("audit_mode", "none")
    if governance_mode not in {"resource_pack", "task_assignment"}:
        raise ConfigError("governance_mode must be resource_pack or task_assignment")
    if allocator_selection not in {"elected", "random"}:
        raise ConfigError("allocator_selection must be elected or random")
    if audit_mode not in {"none", "allocation_fairness_attestation"}:
        raise ConfigError("audit_mode must be none or allocation_fairness_attestation")
    if audit_mode != "none" and governance_mode != "task_assignment":
        raise ConfigError("audit_mode requires task_assignment governance")
    packs_raw = value["resource_packs"]
    if not isinstance(packs_raw, list) or (governance_mode == "resource_pack" and len(packs_raw) < 2):
        raise ConfigError("resource_pack governance requires at least two resource packs")
    if governance_mode == "task_assignment" and packs_raw:
        raise ConfigError("task_assignment governance must not include resource packs")
    packs: list[ResourcePack] = []
    seen: set[str] = set()
    for index, raw in enumerate(packs_raw):
        if not isinstance(raw, dict) or set(raw) != {"id", "total_energy", "leader_take"}:
            raise ConfigError(f"resource_packs[{index}] must contain id, total_energy, leader_take")
        pack_id = raw["id"]
        if not isinstance(pack_id, str) or not pack_id or pack_id in seen:
            raise ConfigError("resource pack ids must be unique non-empty strings")
        seen.add(pack_id)
        total = _number(raw["total_energy"], f"resource_packs[{index}].total_energy", positive=True)
        take = _number(raw["leader_take"], f"resource_packs[{index}].leader_take", positive=True)
        if take >= total:
            raise ConfigError("leader_take must be strictly below total_energy")
        packs.append(ResourcePack(pack_id, total, take))
    if packs:
        followers = agent_count - 1
        totals = [pack.total_energy for pack in packs]
        leader_takes = [pack.leader_take for pack in packs]
        follower_shares = [(pack.total_energy - pack.leader_take) / followers for pack in packs]
        if not all(left < right for left, right in zip(totals, totals[1:])):
            raise ConfigError("resource pack total_energy must strictly increase with rank")
        if not all(left > right for left, right in zip(leader_takes, leader_takes[1:])):
            raise ConfigError("leader_take must strictly decrease with rank")
        if not all(left < right for left, right in zip(follower_shares, follower_shares[1:])):
            raise ConfigError("non-leader equal share must strictly increase with rank")
    puzzle_counts = value["puzzles_per_day"]
    rewards = value["puzzle_rewards"]
    if not isinstance(puzzle_counts, dict) or not isinstance(rewards, dict) or set(puzzle_counts) != set(rewards):
        raise ConfigError("puzzle counts and rewards must use identical difficulty keys")
    for difficulty, count in puzzle_counts.items():
        # A zero-count difficulty is a legitimate experimental condition: it
        # closes the task market without removing the rest of the world.
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ConfigError(f"puzzle count for {difficulty!r} must be a non-negative integer")
        _number(rewards[difficulty], f"puzzle reward for {difficulty!r}", positive=True)
    config = WorldConfig(
        schema_version=value["schema_version"],
        run_kind=value["run_kind"],
        agent_count=agent_count,
        day_seconds=_number(value["day_seconds"], "day_seconds", positive=True),
        prestart_seconds=_number(value["prestart_seconds"], "prestart_seconds", nonnegative=True),
        campaign_seconds=_number(value["campaign_seconds"], "campaign_seconds", positive=True),
        election_seconds=_number(value["election_seconds"], "election_seconds", positive=True),
        initial_energy=_number(value["initial_energy"], "initial_energy", positive=True),
        initial_api_quota=api_quota,
        daily_energy_drain=_number(value["daily_energy_drain"], "daily_energy_drain", positive=True),
        tax_rate=_number(value["tax_rate"], "tax_rate", positive=True),
        max_sleep_seconds=_number(value["max_sleep_seconds"], "max_sleep_seconds", positive=True),
        resource_packs=tuple(packs),
        puzzles_per_day={str(key): int(item) for key, item in puzzle_counts.items()},
        puzzle_rewards={str(key): float(item) for key, item in rewards.items()},
        puzzle_correct_winner_limit=winner_limit,
        governance_mode=governance_mode,
        allocator_selection=allocator_selection,
        audit_mode=audit_mode,
    )
    if config.tax_rate >= 1:
        raise ConfigError("tax_rate must be below 1")
    if config.election_end_seconds >= config.day_seconds:
        raise ConfigError("campaign + election windows must leave time for the resource decision")
    return config


def load(path: str | Path) -> WorldConfig:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigError(f"could not load world config: {error}") from error
    if not isinstance(raw, dict):
        raise ConfigError("world config root must be an object")
    return from_dict(raw)
