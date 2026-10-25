#!/usr/bin/env python3
"""Portable Lean build and dependency audit for the microfoundations."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
VERIFY_DIR = ROOT / 'verification'
VERIFY_DIR.mkdir(exist_ok=True)
subprocess.run([sys.executable, str(ROOT / 'generate_case_studies.py')], cwd=ROOT, check=True)
subprocess.run([sys.executable, str(ROOT / 'generate_ctf_archive.py')], cwd=ROOT, check=True)
subprocess.run([sys.executable, str(ROOT / 'generate_project_artifacts.py')], cwd=ROOT, check=True)
case_assumption_audit = ROOT.parent / 'analysis' / 'validate_case_assumptions.py'
subprocess.run([sys.executable, str(case_assumption_audit)], cwd=ROOT.parent.parent, check=True)
design_coverage_audit = ROOT.parent / 'analysis' / 'audit_ctf_design_coverage.py'
subprocess.run([sys.executable, str(design_coverage_audit)], cwd=ROOT.parent.parent, check=True)
authority_clock_audit = ROOT.parent / 'analysis' / 'audit_authority_v2_clock.py'
authority_election_audit = ROOT.parent / 'analysis' / 'audit_authority_v2_election.py'


def find_lake_bin() -> Path:
    configured = os.environ.get('AGENT_ECONOMICS_LEAN_BIN')
    if configured:
        candidate = Path(configured).expanduser() / 'lake'
        if candidate.is_file():
            return candidate
        raise SystemExit(f'No lake executable at AGENT_ECONOMICS_LEAN_BIN={configured}')
    on_path = shutil.which('lake')
    if on_path:
        return Path(on_path)
    # Convenience fallback for the authoring machine; reviewers should install
    # Lean 4.35.0 or set AGENT_ECONOMICS_LEAN_BIN to their Lean bin directory.
    fallback = Path.home() / '.cache/agent-economics-lean/lean-4.35.0-darwin_aarch64/bin/lake'
    if fallback.is_file():
        return fallback
    raise SystemExit('Install Lean 4.35.0 and put lake on PATH, or set AGENT_ECONOMICS_LEAN_BIN.')


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


lake = find_lake_bin()
source_path = ROOT / 'AgentMicrofoundations.lean'
source = source_path.read_text()
code = re.sub(r'/\-.*?\-/', '', source, flags=re.S)
code = re.sub(r'--[^\n]*', '', code)
if re.search(r'\b(sorry|admit|axiom)\b', code):
    raise SystemExit('Forbidden declaration/token found in Lean source')

version = subprocess.run([str(lake), 'env', 'lean', '--version'], cwd=ROOT,
                         check=True, text=True, capture_output=True).stdout.strip()
if '4.35.0' not in version:
    raise SystemExit(f'Expected Lean 4.35.0, found: {version}')
subprocess.run([str(lake), 'build'], cwd=ROOT, check=True)
subprocess.run([str(lake), 'build', 'AgentMicrofoundations.FoundationCore'], cwd=ROOT, check=True)
subprocess.run([str(lake), 'build', 'AgentMicrofoundations.ResearchTargets.ChoiceLawProblem'], cwd=ROOT, check=True)
audit = subprocess.run([str(lake), 'env', 'lean', 'Audit.lean'], cwd=ROOT,
                       check=True, text=True, capture_output=True)
print(audit.stdout, end='')
target_audit = subprocess.run([str(lake), 'env', 'lean', 'ResearchTargetsAudit.lean'], cwd=ROOT,
                              check=True, text=True, capture_output=True)
print(target_audit.stdout, end='')
subprocess.run([str(lake), 'build', 'AgentMicrofoundations.Methods'], cwd=ROOT, check=True)
methods_audit = subprocess.run([str(lake), 'env', 'lean', 'MethodsAudit.lean'], cwd=ROOT,
                               check=True, text=True, capture_output=True)
print(methods_audit.stdout, end='')
allowed = {'propext', 'Classical.choice', 'Quot.sound'}
blocks = re.findall(r'depends on axioms: \[(.*?)\]', audit.stdout + target_audit.stdout + methods_audit.stdout, flags=re.S)
for block in blocks:
    names = set(re.findall(r'\b(?:propext|Classical\.choice|Quot\.sound|[A-Za-z_][\w.]*)\b', block))
    unexpected = names - allowed
    if unexpected:
        raise SystemExit(f'Unexpected axiom dependencies: {sorted(unexpected)}')

files = [
    str(path.relative_to(ROOT))
    for path in sorted(ROOT.rglob('*.lean'))
    if 'verification' not in path.parts
] + ['generate_case_studies.py', 'generate_ctf_archive.py', 'generate_project_artifacts.py', 'THEORY_INDEX.md', 'METHODS_INDEX.md', 'lakefile.toml', 'lean-toolchain', 'lake-manifest.json']
case_data = ROOT.parent.parent / 'WWW2027_submission' / 'appendix' / 'pilot' / 'pilot_v2.jsonl'
ctf_task_data = ROOT.parent / 'analysis' / 'ctf_case' / 'results' / 'task_panel.csv'
ctf_world_data = ROOT.parent / 'analysis' / 'ctf_case' / 'results' / 'world_summary.csv'
ctf_agent_day_data = ROOT.parent / 'analysis' / 'ctf_case' / 'results' / 'agent_day_panel.csv'
ctf_case_summary = ROOT.parent / 'analysis' / 'ctf_case' / 'results' / 'case_model_summary.json'
ctf_pipeline = ROOT.parent / 'analysis' / 'ctf_case' / 'build_ctf_case.py'
theory_freeze = ROOT.parent / 'THEORY_FREEZE_0.5.md'
theory_project = ROOT.parent / 'THEORY_PROJECT.md'
case_assumption_report = VERIFY_DIR / 'assumption_validation.json'
case_assumption_report_obj = json.loads(case_assumption_report.read_text())
design_coverage_report = VERIFY_DIR / 'ctf_design_coverage.json'
design_coverage_report_obj = json.loads(design_coverage_report.read_text())
authority_clock_report = VERIFY_DIR / 'authority_v2_clock_audit.json'
authority_clock_report_obj = json.loads(authority_clock_report.read_text())
authority_election_report = VERIFY_DIR / 'authority_v2_election_audit.json'
authority_election_report_obj = json.loads(authority_election_report.read_text())
if case_assumption_report_obj.get('archive_integrity', {}).get('status') != 'PASS':
    raise SystemExit('Case assumption audit did not pass archive integrity checks')
assumption_registry = case_assumption_report_obj.get('assumption_registry', [])
required_assumption_fields = {
    'id', 'kind', 'verification_cost', 'restriction', 'check', 'reject_rule',
    'failure_action', 'status', 'evidence', 'used_for_case_prediction'
}
if not assumption_registry:
    raise SystemExit('Assumption registry is empty')
if any(not required_assumption_fields.issubset(entry) for entry in assumption_registry):
    raise SystemExit('An assumption registry entry is missing its test/rejection fields')
if len({entry['id'] for entry in assumption_registry}) != len(assumption_registry):
    raise SystemExit('Assumption registry contains duplicate IDs')
if any(entry['used_for_case_prediction'] and entry['status'] not in {
        'PASS', 'PASS_FOR_NON_SYMBOLIC_TRACE'} for entry in assumption_registry):
    raise SystemExit('A case forecast uses an unvalidated empirical restriction')
if design_coverage_report_obj.get('field_count') != 46 or len(design_coverage_report_obj.get('fields', [])) != 46:
    raise SystemExit('CTF design field coverage audit did not account for all declared controls')
if design_coverage_report_obj.get('status_counts', {}).get('REQUIRES_CASE_KERNEL_BINDING', 0) == 0:
    raise SystemExit('CTF design audit failed to disclose controls requiring case-kernel binding')
if authority_clock_report_obj.get('status') != 'PASS' or authority_clock_report_obj.get('configs_checked', 0) < 1:
    raise SystemExit('Authority World v2 clock source/config audit failed')
if authority_election_report_obj.get('status') != 'PASS' or not all(
        branch.get('pass') for branch in authority_election_report_obj.get('branches', {}).values()):
    raise SystemExit('Authority World v2 election source/branch audit failed')
eligibility = case_assumption_report_obj.get('prediction_admissibility', {})
if eligibility.get('untested_or_rejected_restrictions_used_in_case_forecast') != 0:
    raise SystemExit('An untested/rejected restriction is used in a case forecast')
if eligibility.get('positive_reserve_survival_forecast_admissible_for_current_ctf') is not False:
    raise SystemExit('CTF positive-reserve survival forecast was not explicitly gated')
if eligibility.get('point_forecast_from_behavioral_kernel_admissible') is not False:
    raise SystemExit('CTF behavioral point forecast was not explicitly gated')
manifest = {
    'verified_at_utc': datetime.now(timezone.utc).isoformat(),
    'theory_freeze': '0.5; theory/methods separation, case-level assumption audits, field-level CTF coverage, and Authority World v2 clock/election mechanics',
    'lean_version': version,
    'commands': [
        'python3 theory_v3/analysis/validate_case_assumptions.py',
        'lake build',
        'lake build AgentMicrofoundations.FoundationCore',
        'lake build AgentMicrofoundations.ResearchTargets.ChoiceLawProblem',
        'lake env lean Audit.lean',
        'lake env lean ResearchTargetsAudit.lean',
    ],
    'source_sha256': {name: sha256(ROOT / name) for name in files},
    'case_data_sha256': {
        str(case_data.relative_to(ROOT.parent.parent)): sha256(case_data),
        str(ctf_task_data.relative_to(ROOT.parent.parent)): sha256(ctf_task_data),
        str(ctf_world_data.relative_to(ROOT.parent.parent)): sha256(ctf_world_data),
        str(ctf_agent_day_data.relative_to(ROOT.parent.parent)): sha256(ctf_agent_day_data),
        str(ctf_case_summary.relative_to(ROOT.parent.parent)): sha256(ctf_case_summary),
        str(case_assumption_report.relative_to(ROOT.parent.parent)): sha256(case_assumption_report),
    },
    'case_assumption_validator_sha256': {
        str(case_assumption_audit.relative_to(ROOT.parent.parent)): sha256(case_assumption_audit),
    },
    'ctf_design_coverage_sha256': {
        str(design_coverage_audit.relative_to(ROOT.parent.parent)): sha256(design_coverage_audit),
        str(design_coverage_report.relative_to(ROOT.parent.parent)): sha256(design_coverage_report),
    },
    'ctf_design_field_status_counts': design_coverage_report_obj['status_counts'],
    'authority_v2_clock_audit_sha256': {
        str(authority_clock_audit.relative_to(ROOT.parent.parent)): sha256(authority_clock_audit),
        str(authority_clock_report.relative_to(ROOT.parent.parent)): sha256(authority_clock_report),
    },
    'authority_v2_clock_configs_checked': authority_clock_report_obj['configs_checked'],
    'authority_v2_election_audit_sha256': {
        str(authority_election_audit.relative_to(ROOT.parent.parent)): sha256(authority_election_audit),
        str(authority_election_report.relative_to(ROOT.parent.parent)): sha256(authority_election_report),
    },
    'case_pipeline_sha256': {str(ctf_pipeline.relative_to(ROOT.parent.parent)): sha256(ctf_pipeline)},
    'theory_freeze_sha256': {
        str(theory_freeze.relative_to(ROOT.parent.parent)): sha256(theory_freeze),
        str((ROOT.parent / 'FOUNDATION_CORE.md').relative_to(ROOT.parent.parent)): sha256(ROOT.parent / 'FOUNDATION_CORE.md'),
        str(theory_project.relative_to(ROOT.parent.parent)): sha256(theory_project),
        str((ROOT.parent / 'FOUNDATION_BOUNDARY.md').relative_to(ROOT.parent.parent)): sha256(ROOT.parent / 'FOUNDATION_BOUNDARY.md'),
        str((ROOT.parent / 'EXPERIMENTAL_MODEL_ADMISSION.md').relative_to(ROOT.parent.parent)): sha256(ROOT.parent / 'EXPERIMENTAL_MODEL_ADMISSION.md'),
        str((ROOT.parent / 'ASSUMPTION_VALIDATION.md').relative_to(ROOT.parent.parent)): sha256(ROOT.parent / 'ASSUMPTION_VALIDATION.md'),
    },
    'audit_output_sha256': {
        'foundation_and_case_theory': hashlib.sha256(audit.stdout.encode()).hexdigest(),
        'auxiliary_methods': hashlib.sha256(methods_audit.stdout.encode()).hexdigest(),
    },
    'has_custom_axiom_sorry_or_admit': False,
    'axiom_policy': sorted(allowed),
    'result': 'PASS',
}
remote_logs = sorted(VERIFY_DIR.glob('lake_check_miao_*.log'))
if remote_logs:
    latest_remote = remote_logs[-1]
    remote_text = latest_remote.read_text(errors='replace')
    manifest['additional_verification'] = [{
        'command': './verify_miao.sh',
        'log': str(latest_remote.relative_to(ROOT)),
        'default_kernel_accepts_solution': 'Lean default kernel accepts the solution' in remote_text,
        'log_sha256': sha256(latest_remote),
    }]
(VERIFY_DIR / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(f'PASS: {version}; no sorry/admit/custom axioms; manifest written to {VERIFY_DIR / "manifest.json"}')
