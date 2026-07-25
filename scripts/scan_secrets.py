#!/usr/bin/env python3
"""Fail-closed, repository-wide high-confidence credential scanner.

Only paths, line numbers, and rule names are reported. Suspected values are
never printed, which makes this command safe to use in CI logs.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules"}
MAX_TEXT_BYTES = 512 * 1024 * 1024
PLACEHOLDERS = re.compile(
    r"(?i)^(?:your[-_ ]?(?:key|token|secret)|example|changeme|dummy|test|none|null|"
    r"\$\{?[A-Z][A-Z0-9_]*\}?|<[^>]+>|\[REDACTED(?::[^]]+)?\])$"
)


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: re.Pattern[str]
    group: int = 0


RULES = (
    Rule("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),  # secret-scan: allow-rule-definition
    Rule("openai-key", re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}\b")),
    Rule("github-token", re.compile(r"\b(?:gh[opusr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b")),
    Rule("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    Rule("bearer-token", re.compile(r"(?i)\bAuthorization\s*:\s*Bearer\s+([A-Za-z0-9._~+/=-]{16,})"), 1),
    Rule("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{8,}\b")),
    Rule(
        "credential-assignment",
        re.compile(
            r"(?i)(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|"
            r"world[_-]?control[_-]?token|gateway[_-]?token|password)"
            r"\s*[=:]\s*[\"']?([A-Za-z0-9._~+/=-]{16,})",
        ),
        1,
    ),
)


def iter_files(root: Path):
    if root.is_file():
        yield root
        return
    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def scan_file(path: Path, display_root: Path) -> list[dict[str, object]]:
    if path.stat().st_size > MAX_TEXT_BYTES:
        return [{"path": str(path.relative_to(display_root)), "line": 0, "rule": "oversize-unscanned"}]
    raw = path.read_bytes()
    if b"\x00" in raw[:8192]:
        for needle, name in ((b"-----BEGIN PRIVATE KEY-----", "private-key-binary"), (b"sk-", "key-prefix-binary")):  # secret-scan: allow-rule-definition
            if needle in raw:
                return [{"path": str(path.relative_to(display_root)), "line": 0, "rule": name}]
        return []
    text = raw.decode("utf-8", errors="replace")
    findings: list[dict[str, object]] = []
    relative = str(path.relative_to(display_root))
    for number, line in enumerate(text.splitlines(), 1):
        if "# secret-scan: allow-rule-definition" in line and path.name == "scan_secrets.py":
            continue
        for rule in RULES:
            for match in rule.pattern.finditer(line):
                candidate = match.group(rule.group)
                if PLACEHOLDERS.fullmatch(candidate.strip("\"'")):
                    continue
                findings.append({"path": relative, "line": number, "rule": rule.name})
    return findings


def scan(root: Path) -> list[dict[str, object]]:
    root = root.resolve()
    display_root = root if root.is_dir() else root.parent
    findings: list[dict[str, object]] = []
    for path in iter_files(root):
        findings.extend(scan_file(path, display_root))
    return findings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    findings = scan(Path(args.root))
    if args.json:
        print(json.dumps(findings, ensure_ascii=False, sort_keys=True))
    else:
        for item in findings:
            print(f"{item['path']}:{item['line']}: {item['rule']}")
        print(f"secret scan: {len(findings)} finding(s)")
    raise SystemExit(1 if findings else 0)


if __name__ == "__main__":
    main()
