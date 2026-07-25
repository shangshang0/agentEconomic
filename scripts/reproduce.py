#!/usr/bin/env python3
"""Recompute frozen world metrics from public extracted evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--world-root", type=Path, default=ROOT / "data/releases/extracted/worlds")
    args = parser.parse_args()
    selected = []
    for line in args.catalog.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if row.get("analysis_eligible"):
                selected.append(row["run_id"])
    missing = [run_id for run_id in selected if not (args.world_root / run_id / "run_metadata.json").is_file()]
    if missing:
        raise SystemExit(f"downloaded evidence missing for {len(missing)} eligible world(s)")
    args.output.mkdir(parents=True, exist_ok=True)
    analyzer = ROOT / "runtime/authority_world/scripts/analyze_agent_economics.py"
    subprocess.run([
        sys.executable, str(analyzer), "--results", str(args.world_root),
        "--output", str(args.output), "--latex", str(args.output / "results.generated.tex")
    ], check=True)
    provenance = {
        "catalog": str(args.catalog), "selected_run_ids": selected,
        "analysis_unit": "world", "analyzer": str(analyzer.relative_to(ROOT)),
    }
    (args.output / "PROVENANCE.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
