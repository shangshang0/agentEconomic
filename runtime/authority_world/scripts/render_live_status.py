#!/usr/bin/env python3
"""Render a compact LaTeX live-run status table from a v2 summary JSON."""
from __future__ import annotations
import argparse, json
from pathlib import Path


def esc(value: object) -> str:
    repl={"\\":r"\textbackslash{}","&":r"\&","%":r"\%","$":r"\$","#":r"\#","_":r"\_","{":r"\{","}":r"\}"}
    return "".join(repl.get(ch,ch) for ch in str(value))


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--summary", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args=ap.parse_args()
    s=json.loads(args.summary.read_text(encoding="utf-8"))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    agents=s.get("agents",{})
    task=s.get("task_outcomes",{})
    comm=s.get("communication",{})
    pol=s.get("politics",{})
    rows=[
        ("Run", s.get("run_id")),
        ("Status / day", f"{s.get('status')} / {s.get('current_day')}"),
        ("Event sequence", s.get("event_seq")),
        ("Alive / dead", f"{len(agents.get('alive', []))} / {len(agents.get('dead', []))}"),
        ("Energy range", agents.get("living_energy_range")),
        ("Candidacies / votes", f"{pol.get('candidacies', 0)} / {pol.get('explicit_votes_cast', 0)}"),
        ("Forum / private", f"{comm.get('agent_forum_posts', 0)} / {comm.get('private_messages', 0)}"),
        ("Tasks solved / submitted", f"{task.get('correct', 0)} / {task.get('submitted', 0)}"),
    ]
    body="\n".join(f"{esc(k)} & {esc(v)} \\\\" for k,v in rows)
    (args.out_dir/"live_run_status.tex").write_text("\n".join([
        r"\begin{table}[t]", r"\centering", r"\small",
        r"\caption{Live corrected-run supervision snapshot. This table is generated from the remote append-only event stream via \texttt{scripts/render\_live\_status.py}; it is operational monitoring, not a final result.}",
        r"\label{tab:live-run-status}", r"\begin{tabular}{ll}", r"\toprule", r"Field & Value \\", r"\midrule",
        body, r"\bottomrule", r"\end{tabular}", r"\end{table}", "",
    ]), encoding="utf-8")

if __name__ == "__main__": main()
