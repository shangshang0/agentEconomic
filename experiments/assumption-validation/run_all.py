#!/usr/bin/env python3
"""Reproduce all zero-API assumption and case-mapping audits."""
from pathlib import Path
import subprocess, sys
root = Path(__file__).resolve().parent / "case_bundle"
commands = [[sys.executable, "theory_v3/analysis/audit_ctf_design_coverage.py"], [sys.executable, "theory_v3/analysis/validate_case_assumptions.py"]]
for command in commands:
    subprocess.run(command, cwd=root, check=True)
print("PASS: assumption-validation bundle; no model/API calls were made")
