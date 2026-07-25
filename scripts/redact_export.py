#!/usr/bin/env python3
"""Deterministically redact an experiment tree into a public staging tree.

The source tree is never modified. Source secret values are taken from named
environment variables without being printed. A second scanner gates output.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import stat
import sys
from collections import Counter
from pathlib import Path

from scan_secrets import scan

RULESET = "agent-economic-redaction-v1"
SKIP_NAMES = {".git", ".env", ".venv", "__pycache__", ".pytest_cache"}
PATTERNS = (
    ("provider_key", re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}\b")),
    ("github_token", re.compile(r"\b(?:gh[opusr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b")),
    ("authorization", re.compile(r"(?i)(Authorization\s*:\s*Bearer\s+)[A-Za-z0-9._~+/=-]{16,}")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{8,}\b")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    (
        "credential_assignment",
        re.compile(
            r"(?i)((?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|"
            r"world[_-]?control[_-]?token|gateway[_-]?token|password)"
            r"\s*[=:]\s*[\"']?)([A-Za-z0-9._~+/=-]{16,})"
        ),
    ),
    (
        "private_ipv4",
        re.compile(
            r"(?<![0-9.])(?:10(?:\.[0-9]{1,3}){3}|192\.168(?:\.[0-9]{1,3}){2}|"
            r"172\.(?:1[6-9]|2[0-9]|3[01])(?:\.[0-9]{1,3}){2})(?![0-9.])"
        ),
    ),
    ("local_user_path", re.compile(r"/Users/([^/\s\"']+)")),
)
PRIVATE_KEY_BEGIN = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")
PRIVATE_KEY_END = re.compile(r"-----END (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")
PRIVATE_KEY_INLINE = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----.*?"
    r"-----END (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def placeholder(kind: str, value: str) -> str:
    fingerprint = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"[REDACTED:{kind.upper()}:{fingerprint}]"


def redact_line(text: str, known: dict[str, str], counts: Counter[str]) -> str:
    for kind, value in known.items():
        hits = text.count(value)
        if hits:
            text = text.replace(value, placeholder(kind, value))
            counts[kind] += hits
    for kind, pattern in PATTERNS:
        def replacement(match: re.Match[str]) -> str:
            counts[kind] += 1
            value = match.group(0)
            if kind == "authorization":
                prefix = match.group(1)
                secret = value[len(prefix):]
                return prefix + placeholder(kind, secret)
            if kind == "credential_assignment":
                return match.group(1) + placeholder(kind, match.group(2))
            if kind == "local_user_path":
                return "/Users/" + placeholder(kind, match.group(1))
            return placeholder(kind, value)
        text = pattern.sub(replacement, text)
    return text


def redact_stream(inp, out, known: dict[str, str], counts: Counter[str]) -> None:
    in_private_key = False
    for line in inp:
        if in_private_key:
            if PRIVATE_KEY_END.search(line):
                in_private_key = False
            continue
        inline_hits = list(PRIVATE_KEY_INLINE.finditer(line))
        if inline_hits:
            counts["private_key"] += len(inline_hits)
            line = PRIVATE_KEY_INLINE.sub(
                lambda match: placeholder("private_key", match.group(0)), line
            )
        begin = PRIVATE_KEY_BEGIN.search(line)
        if begin and not PRIVATE_KEY_END.search(line, begin.end()):
            counts["private_key"] += 1
            out.write(redact_line(line[: begin.start()], known, counts))
            out.write(placeholder("private_key", begin.group(0)) + "\n")
            in_private_key = True
            continue
        out.write(redact_line(line, known, counts))


def omitted(path: Path, relative: str, globs: list[str]) -> str | None:
    if any(part in SKIP_NAMES or part.startswith(".env") for part in path.parts):
        return "credential-or-build-state"
    if any(fnmatch.fnmatch(relative, pattern) for pattern in globs):
        return "operator-omission-glob"
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--secret-env", action="append", default=[])
    parser.add_argument("--omit-glob", action="append", default=[])
    args = parser.parse_args()
    source = args.source.resolve()
    destination = args.destination.resolve()
    if not source.is_dir():
        raise SystemExit("source must be a directory")
    if destination.exists() and any(destination.iterdir()):
        raise SystemExit("destination must not exist or must be empty")
    if destination == source or source in destination.parents:
        raise SystemExit("destination cannot be inside source")
    destination.mkdir(parents=True, exist_ok=True)
    known = {}
    for name in args.secret_env:
        value = os.environ.get(name)
        if not value:
            raise SystemExit(f"named secret environment variable is unset: {name}")
        if len(value) < 8:
            raise SystemExit(f"refusing dangerously short secret value: {name}")
        known[name.lower()] = value
    ledger: list[dict[str, object]] = []
    omissions: list[dict[str, str]] = []
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source).as_posix()
        reason = omitted(path.relative_to(source), relative, args.omit_glob)
        if reason:
            if path.is_file():
                omissions.append({"path": relative, "reason": reason, "source_sha256": digest(path)})
            continue
        if path.is_symlink():
            omissions.append({"path": relative, "reason": "symlink-not-exported"})
            continue
        target = destination / relative
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if not path.is_file():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        counts: Counter[str] = Counter()
        with path.open("rb") as probe:
            binary = b"\x00" in probe.read(8192)
        if binary:
            data = path.read_bytes()
            for kind, value in known.items():
                needle = value.encode("utf-8")
                hits = data.count(needle)
                if hits:
                    data = data.replace(needle, placeholder(kind, value).encode("utf-8"))
                    counts[kind] += hits
            target.write_bytes(data)
        else:
            with path.open(encoding="utf-8", errors="strict") as inp, target.open("w", encoding="utf-8", newline="") as out:
                redact_stream(inp, out, known, counts)
        target.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
        ledger.append({
            "path": relative,
            "source_sha256": digest(path),
            "public_sha256": digest(target),
            "bytes": target.stat().st_size,
            "redactions": dict(sorted(counts.items())),
            "ruleset": RULESET,
        })
    (destination / "REDACTION_LEDGER.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in ledger), encoding="utf-8"
    )
    (destination / "OMISSION_LEDGER.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in omissions), encoding="utf-8"
    )
    manifest_files = [
        {"path": p.relative_to(destination).as_posix(), "bytes": p.stat().st_size, "sha256": digest(p)}
        for p in sorted(destination.rglob("*")) if p.is_file() and p.name != "PUBLIC_MANIFEST.json"
    ]
    (destination / "PUBLIC_MANIFEST.json").write_text(
        json.dumps({"schema_version": 1, "redaction_ruleset": RULESET, "files": manifest_files}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    findings = scan(destination)
    if findings:
        for item in findings:
            print(f"{item['path']}:{item['line']}: {item['rule']}")
        raise SystemExit(f"public export blocked by {len(findings)} secret finding(s)")
    print(json.dumps({"files": len(ledger), "omissions": len(omissions), "redactions": sum(sum(x["redactions"].values()) for x in ledger)}, sort_keys=True))


if __name__ == "__main__":
    main()
