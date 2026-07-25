#!/usr/bin/env python3
"""One bounded Authority World supervision/CI cycle.

The persistent human goal asks for an always-on supervisor.  This script makes
one cycle auditable: inspect runtime state, collect run metrics when present,
run local gates, regenerate paper fragments, build the draft, and write a
machine-readable dashboard.  It never prints or stores secret values; it records
only whether required variables are present.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper"
DATA = PAPER / "data"
GENERATED = PAPER / "generated"
REQUIRED_ENV = [
    "OPENAI_API_KEY", "GATEWAY_TOKEN", "WORLD_CONTROL_TOKEN", "AGENT_TOKENS_JSON",
    "A1_TOKEN", "A2_TOKEN", "A3_TOKEN", "A4_TOKEN", "A5_TOKEN", "A6_TOKEN",
]


def run(cmd: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None, timeout: int = 120) -> dict[str, Any]:
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True, timeout=timeout)
        return {
            "cmd": cmd,
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "duration_seconds": round(time.time() - started, 3),
            "stdout_tail": proc.stdout[-4000:],
            "stderr_tail": proc.stderr[-4000:],
        }
    except FileNotFoundError as error:
        return {"cmd": cmd, "ok": False, "missing_executable": cmd[0], "error": str(error), "duration_seconds": round(time.time() - started, 3)}
    except subprocess.TimeoutExpired as error:
        return {"cmd": cmd, "ok": False, "timeout": timeout, "stdout_tail": (error.stdout or "")[-4000:], "stderr_tail": (error.stderr or "")[-4000:], "duration_seconds": round(time.time() - started, 3)}


def redact_env_presence(path: Path) -> dict[str, bool]:
    keys: set[str] = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            keys.add(line.split("=", 1)[0].strip())
    return {key: key in keys for key in REQUIRED_ENV}


def docker_status() -> dict[str, Any]:
    # Docker Desktop may emit NUL / replacement bytes inside {{json .}} for
    # truncated commands, so use a plain field format and tolerate malformed
    # lines.  We only need health/readiness metadata, not full container JSON.
    fmt = "{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.State}}\t{{.Label \"com.docker.compose.project\"}}"
    result = run(["docker", "ps", "-a", "--format", fmt], timeout=20)
    containers: list[dict[str, Any]] = []
    if result["ok"]:
        for line in result["stdout_tail"].splitlines():
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            row = {"Names": parts[0], "Image": parts[1], "Status": parts[2], "State": parts[3], "Project": parts[4] if len(parts) > 4 else ""}
            text = " ".join(row.values())
            if re.search(r"authority|world|v2|backend|gateway|agent", text, re.I):
                containers.append(row)
    return {"command": result, "relevant_containers": containers, "authority_world_v2_active": any("authority-world-v2" in str(c.get("Names")) or c.get("Project") == "authority-world-v2" for c in containers)}


def load_archived_runs() -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for group in (ROOT / "formal-results", ROOT / "formal-results-v2"):
        if not group.exists():
            continue
        for path in sorted(group.glob("*/audit_summary.json")):
            try:
                audit = json.loads(path.read_text(encoding="utf-8"))
                meta_path = path.parent / "run_metadata.json"
                meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
                runs.append({
                    "archive": str(path.parent.relative_to(ROOT)),
                    "condition": meta.get("condition"),
                    "run_id": audit.get("run_id"),
                    "status": audit.get("status"),
                    "final_day": audit.get("final_day"),
                    "event_count": audit.get("event_count"),
                    "technical_failures": audit.get("technical", {}).get("technical_failure_events"),
                })
            except Exception as error:  # keep dashboard fail-closed but informative
                runs.append({"archive": str(path.parent.relative_to(ROOT)), "error": str(error)})
    return runs


def active_v2_summary() -> dict[str, Any] | None:
    state = ROOT / "data-v2" / "authority-world-v2.state.json"
    events = ROOT / "data-v2" / "authority-world-v2.events.jsonl"
    if not state.exists():
        return None
    out = DATA / "active_v2_metrics.json"
    result = run([sys.executable, "scripts/summarize_v2_run.py", "--state", str(state), "--events", str(events), "--output", str(out)], timeout=30)
    if result["ok"] and out.exists():
        return json.loads(out.read_text(encoding="utf-8"))
    return {"summary_error": result}


def live_remote_summary() -> dict[str, Any] | None:
    path = DATA / "live_remote_metrics.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        return {"summary_error": str(error)}


def compose_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "OPENAI_API_KEY": env.get("OPENAI_API_KEY", "dummy"),
        "GATEWAY_TOKEN": env.get("GATEWAY_TOKEN", "gateway"),
        "WORLD_CONTROL_TOKEN": env.get("WORLD_CONTROL_TOKEN", "control"),
        "AGENT_TOKENS_JSON": env.get("AGENT_TOKENS_JSON", '{"A1":"a1","A2":"a2","A3":"a3","A4":"a4","A5":"a5","A6":"a6"}'),
        "A1_TOKEN": env.get("A1_TOKEN", "a1"), "A2_TOKEN": env.get("A2_TOKEN", "a2"),
        "A3_TOKEN": env.get("A3_TOKEN", "a3"), "A4_TOKEN": env.get("A4_TOKEN", "a4"),
        "A5_TOKEN": env.get("A5_TOKEN", "a5"), "A6_TOKEN": env.get("A6_TOKEN", "a6"),
    })
    return env


def citation_scan() -> dict[str, Any]:
    tex = (PAPER / "paper.tex").read_text(encoding="utf-8")
    bib = (PAPER / "references.bib").read_text(encoding="utf-8") if (PAPER / "references.bib").exists() else ""
    cites = sorted({key.strip() for group in re.findall(r"\\cite\{([^}]+)\}", tex) for key in group.split(",")})
    bib_keys = sorted(set(re.findall(r"@\w+\{([^,]+),", bib)))
    labels = sorted(set(re.findall(r"\\label\{([^}]+)\}", tex + "\n" + "\n".join(p.read_text(encoding="utf-8") for p in GENERATED.glob("*.tex")))))
    refs = sorted(set(re.findall(r"\\(?:ref|pageref)\{([^}]+)\}", tex)))
    return {"cites": cites, "bib_keys": bib_keys, "missing_cites": sorted(set(cites) - set(bib_keys)), "refs": refs, "labels": labels, "missing_refs": sorted(set(refs) - set(labels))}


def build_paper() -> dict[str, Any]:
    pdflatex = shutil.which("pdflatex")
    bibtex = shutil.which("bibtex")
    if pdflatex and bibtex:
        passes = [
            run([pdflatex, "-interaction=nonstopmode", "-halt-on-error", "paper.tex"], cwd=PAPER, timeout=120),
            run([bibtex, "paper"], cwd=PAPER, timeout=120),
            run([pdflatex, "-interaction=nonstopmode", "-halt-on-error", "paper.tex"], cwd=PAPER, timeout=120),
            run([pdflatex, "-interaction=nonstopmode", "-halt-on-error", "paper.tex"], cwd=PAPER, timeout=120),
        ]
        mode = "pdflatex-bibtex-pdflatex-pdflatex"
    else:
        tectonic = shutil.which("tectonic")
        passes = [run([tectonic or "tectonic", "--keep-logs", "--keep-intermediates", "paper.tex"], cwd=PAPER, timeout=180)]
        mode = "tectonic-fallback"
    log_text = (PAPER / "paper.log").read_text(encoding="utf-8", errors="replace") if (PAPER / "paper.log").exists() else ""
    warning_patterns = ["LaTeX Warning", "Package .* Warning", "Undefined", "Citation", "Overfull", "Underfull", "! "]
    warnings = [line for line in log_text.splitlines() if any(re.search(pat, line) for pat in warning_patterns)]
    render = run(["pdftoppm", "-png", "-r", "150", str(PAPER / "paper.pdf"), str(ROOT / "tmp/pdfs/authority_world_interim")], timeout=60) if (PAPER / "paper.pdf").exists() else {"ok": False, "error": "paper.pdf missing"}
    return {"mode": mode, "pdflatex_available": bool(pdflatex), "bibtex_available": bool(bibtex), "passes": passes, "ok": all(p.get("ok") for p in passes) and render.get("ok", False), "warnings": warnings, "render": render}


def write_dashboard(report: dict[str, Any]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    GENERATED.mkdir(parents=True, exist_ok=True)
    (DATA / "supervision_health.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    ci = report.get("ci", {})
    active = report.get("active_v2_summary")
    run_status = active.get("status") if isinstance(active, dict) else "none"
    remote = report.get("live_remote_summary")
    remote_status = "none"
    if isinstance(remote, dict) and remote.get("run_id"):
        remote_status = f"{remote.get('status')} day {remote.get('current_day')}"
    rows = [
        ("Local v2 stack", "active" if report["docker"]["authority_world_v2_active"] else "not active"),
        ("Local v2 state", str(run_status)),
        ("Remote live run", remote_status),
        ("Pytest", "PASS" if ci.get("pytest", {}).get("ok") else "FAIL"),
        ("v2 gates", "PASS" if ci.get("v2_gates", {}).get("ok") else "FAIL"),
        ("Compose config", "PASS" if ci.get("compose_config", {}).get("ok") else "FAIL"),
        ("Paper build", "PASS" if ci.get("paper_build", {}).get("ok") else "FAIL"),
    ]
    tex_rows = "\n".join(f"{name} & {value} \\\\" for name, value in rows)
    (GENERATED / "supervision_dashboard.tex").write_text("\n".join([
        r"\begin{table}[t]", r"\centering", r"\small",
        r"\caption{Automated supervision dashboard for the current working tree. The table is generated by \texttt{scripts/supervision\_cycle.py}; it reports engineering readiness only, not authority evidence.}",
        r"\label{tab:supervision-dashboard}", r"\begin{tabular}{ll}", r"\toprule", r"Check & Status \\", r"\midrule",
        tex_rows, r"\bottomrule", r"\end{tabular}", r"\end{table}", "",
    ]), encoding="utf-8")


def write_quality_markdown(report: dict[str, Any]) -> None:
    ci = report.get("ci", {})
    citations = report.get("citation_scan", {})
    build = ci.get("paper_build", {})
    lines = [
        f"# Paper health report — {datetime.now().strftime('%Y-%m-%d')}", "",
        f"- Build: {'PASS' if build.get('ok') else 'FAIL'} via `{build.get('mode')}`.",
        f"- Requested four-pass pdflatex: {'available' if build.get('pdflatex_available') and build.get('bibtex_available') else 'not available on this host; Tectonic fallback used as current evidence'}.",
        f"- Compiler warnings: {len(build.get('warnings', []))} actionable warning lines matched.",
        f"- Citation integrity: {len(citations.get('cites', []))} cite keys used, {len(citations.get('bib_keys', []))} BibTeX records defined, missing={citations.get('missing_cites', [])}.",
        f"- Cross-reference integrity: missing refs={citations.get('missing_refs', [])}.",
        "- Data anchoring: interim allocation table/macros and the supervision dashboard are generated from JSON data by scripts, not hand-copied.",
        f"- Engineering gates: pytest={'PASS' if ci.get('pytest', {}).get('ok') else 'FAIL'}, v2_gates={'PASS' if ci.get('v2_gates', {}).get('ok') else 'FAIL'}, compose_config={'PASS' if ci.get('compose_config', {}).get('ok') else 'FAIL'}.",
        f"- Local runtime status: authority-world-v2 stack is {'active' if report['docker']['authority_world_v2_active'] else 'not active'} on this Mac workspace.",
        f"- Remote runtime status: {('active run ' + str(report.get('live_remote_summary', {}).get('run_id')) + ' status=' + str(report.get('live_remote_summary', {}).get('status')) + ' day=' + str(report.get('live_remote_summary', {}).get('current_day'))) if isinstance(report.get('live_remote_summary'), dict) and report.get('live_remote_summary', {}).get('run_id') else 'no remote live summary captured'}.",
        "- Evidence status: calibration only. No claim of personal authority is made.",
        "- Open evidence gaps:",
        "  1. continue the fresh corrected run through multiple days and archive it immutably before any formal inference;",
        "  2. full-state v2 checkpoints under long runs; compact runner receipts now have a unit regression;",
        "  3. non-ceiling task calibration across repeated blind trials;",
        "  4. elected/random/no-office contrasts across seeds and model profiles;",
        "  5. blinded coding of costly deference, dissent, appeal, and third-party maintenance.",
    ]
    (PAPER / "quality_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-ci", action="store_true", help="run tests, gates, compose config and paper build")
    args = parser.parse_args()
    report: dict[str, Any] = {
        "schema": "authority-world-supervision-cycle-1",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "cwd": str(ROOT),
        "credentials_presence_in_dotenv": redact_env_presence(ROOT / ".env"),
        "docker": docker_status(),
        "active_v2_summary": active_v2_summary(),
        "live_remote_summary": live_remote_summary(),
        "archived_runs": load_archived_runs(),
        "citation_scan": citation_scan(),
    }
    if args.run_ci:
        render = run([sys.executable, "scripts/render_v2_latex.py", "--summary", "paper/data/interim_metrics.json", "--out-dir", "paper/generated"], timeout=30)
        report["ci"] = {
            "pytest": run([sys.executable, "-m", "pytest", "-q"], timeout=120),
            "v2_gates": run([sys.executable, "scripts/run_v2_gates.py"], timeout=60),
            "compose_config": run(["docker", "compose", "-f", "docker-compose.v2.fallback.yml", "config"], env=compose_env(), timeout=60),
            "render_v2_latex": render,
        }
        # Build after render so the dashboard and quality report reflect fresh data.
        write_dashboard(report)
        report["ci"]["paper_build"] = build_paper()
        write_quality_markdown(report)
    write_dashboard(report)
    print(json.dumps({
        "ok": not args.run_ci or all(report["ci"][key].get("ok") for key in ("pytest", "v2_gates", "compose_config", "paper_build")),
        "dashboard": str(DATA / "supervision_health.json"),
        "v2_active": report["docker"]["authority_world_v2_active"],
        "archived_runs": len(report["archived_runs"]),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
