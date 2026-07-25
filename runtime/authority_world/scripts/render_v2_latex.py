#!/usr/bin/env python3
"""Render paper fragments only from a validated v2 summary JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def esc(value: object) -> str:
    replacements = {
        "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
        "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
    }
    return "".join(replacements.get(char, char) for char in str(value))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    args.out_dir.mkdir(parents=True, exist_ok=True)

    agents = summary["agents"]
    outcomes = summary["task_outcomes"]
    communication = summary["communication"]
    politics = summary["politics"]
    macros = {
        "CalibrationRunID": summary["run_id"],
        "CalibrationCurrentDay": summary["current_day"],
        "CalibrationEventSeq": summary["event_seq"],
        "CalibrationStatus": summary["status"],
        "CalibrationAlive": len(agents["alive"]),
        "CalibrationDead": len(agents["dead"]),
        "CalibrationEnergyRange": agents["living_energy_range"],
        "CalibrationSolved": outcomes["correct"],
        "CalibrationSubmitted": outcomes["submitted"],
        "CalibrationAssigned": outcomes["assigned_events"],
        "CalibrationOfferedDays": outcomes["offered_events"],
        "CalibrationSelfAllocations": outcomes["self_allocations"],
        "CalibrationCandidacies": politics["candidacies"],
        "CalibrationExplicitVotes": politics["explicit_votes_cast"],
        "CalibrationForumPosts": communication["agent_forum_posts"],
        "CalibrationPrivateMessages": communication["private_messages"],
    }
    macro_text = "".join(f"\\newcommand{{\\{name}}}{{{esc(value)}}}\n" for name, value in macros.items())
    (args.out_dir / "interim_run_macros.tex").write_text(macro_text, encoding="utf-8")

    solved = {(str(item["day"]), item["task_id"]): item["correct"] for item in outcomes["records"]}
    rows = []
    for day, records in sorted(summary["assignments_by_day"].items(), key=lambda item: int(item[0])):
        leader = records[0]["leader"] if records else "--"
        cells = {}
        for record in records:
            mark = "*" if record["self_allocation"] else ""
            status = "\\checkmark" if solved.get((day, record["task_id"])) else "--"
            cells[record["tier"]] = f"{esc(record['recipient'])}{mark} ({status})"
        rows.append(" & ".join([esc(day), esc(leader), cells.get("easy", "--"), cells.get("medium", "--"), cells.get("hard", "--")]) + r" \\")
    table = "\n".join([
        r"\begin{table}[t]",
        r"\centering",
        r"\small",
        r"\caption{Completed live-politics calibration allocations. A star marks allocation to the office holder; a check mark records a correct flag. This table is generated from the append-only event stream.}",
        r"\label{tab:interim-allocations}",
        r"\begin{tabular}{ccccc}",
        r"\toprule",
        r"Day & Office holder & Easy & Medium & Hard \\",
        r"\midrule",
        *rows,
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
        "",
    ])
    (args.out_dir / "interim_run_table.tex").write_text(table, encoding="utf-8")


if __name__ == "__main__":
    main()
