#!/usr/bin/env python3
"""Audit every catalogued original CTF challenge against available runtimes."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlparse


FLAG_PATTERN = re.compile(r"(?:CTF|SECCON|RWCTF|rwctf|flag|FLAG|OOO|ooo|hitcon|HITCON|ticket)\{[^\r\n{}]{3,300}\}")
PLACEHOLDER = re.compile(r"(?:example|fake|dummy|placeholder|place[_ -]?holder|test|your[_ -]?flag|redacted|censored|xxx|flag goes here|super secret thing|real flag)", re.I)
TEXT_SUFFIXES = {"", ".md", ".txt", ".yaml", ".yml", ".json", ".toml", ".py", ".js", ".ts", ".go", ".rs", ".c", ".cc", ".cpp", ".h", ".hpp", ".sh", ".rb", ".php", ".java", ".kt", ".conf", ".cfg", ".ini", ".env"}
ARCHIVE_SUFFIXES = {".zip", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".tar", ".zst"}
HANDOUT_SUFFIXES = ARCHIVE_SUFFIXES | {".exe", ".bin", ".dso", ".so", ".elf", ".wasm", ".apk", ".jar", ".pcap", ".pcapng", ".img", ".iso", ".pdf"}
PLAYER_DIRS = {"attachments", "attachment", "files", "dist", "public", "download", "handout", "handouts"}
NON_PLAYER_DIRS = {"solver", "solution", "solutions", "healthcheck", "build", "challenge", "server", "deploy", "deployment", "infra", "kctf", "third_party"}


def record_name(item: dict[str, object]) -> str:
    return str(item.get("challenge_directory") or item.get("challenge") or "")


def source_relative(item: dict[str, object]) -> Path:
    source = str(item["source"])
    marker = "/tree/" + str(item["commit"]) + "/"
    if marker not in source:
        raise ValueError(f"source URL lacks pinned tree path: {source}")
    return Path(unquote(source.split(marker, 1)[1]))


def trusted_flag_candidates(directory: Path) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for path in directory.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.stat().st_size > 2_000_000:
            continue
        relative = path.relative_to(directory)
        lowered = {part.lower() for part in relative.parts}
        if lowered & {"node_modules", "vendor", "third_party"} or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in FLAG_PATTERN.finditer(text):
            value = match.group(0)
            if value.lower().startswith("ticket{") or PLACEHOLDER.search(value) or re.search(r"\{[^{}]*(?:[\"']|\bif\b|\belse\b|\[[^]]+\]|\([^)]*\)|\.upper\(|\.split\(|rand_|next\(|label_counter)[^{}]*\}", value):
                continue
            source_class = "official_solution" if lowered & {"solver", "solution", "solutions", "healthcheck"} else "deployment_or_metadata"
            candidates.append({"value": value, "path": str(relative), "source_class": source_class})
    unique: dict[str, dict[str, str]] = {}
    for candidate in candidates:
        unique.setdefault(candidate["value"], candidate)
    return list(unique.values())


def handout_paths(directory: Path, catalog_paths: list[str] | None = None) -> list[str]:
    selected: list[str] = []
    relative_paths = {path.relative_to(directory) for path in directory.rglob("*") if path.is_file() and ".git" not in path.parts}
    relative_paths.update(Path(path) for path in catalog_paths or [])
    for relative in sorted(relative_paths):
        parts = [part.lower() for part in relative.parts]
        if parts[0] in PLAYER_DIRS:
            selected.append(str(relative))
        elif len(parts) == 1 and relative.suffix.lower() in HANDOUT_SUFFIXES:
            selected.append(str(relative))
    return sorted(selected)


def topology(directory: Path, catalog_paths: list[str] | None = None) -> dict[str, object]:
    paths = [str(path.relative_to(directory)).lower() for path in directory.rglob("*") if path.is_file()]
    paths.extend(path.lower() for path in catalog_paths or [])
    paths = sorted(set(paths))
    joined = "\n".join(paths)
    browser = any(token in joined for token in ("playwright", "puppeteer", "selenium", "chromedriver", "xss-bot", "/bot/", "bot.js", "bot.py"))
    vm_kernel = any(token in joined for token in ("vmlinuz", "bzimage", "initramfs", "initrd", "qemu", "kernel", ".ko"))
    compose_paths = [path for path in paths if Path(path).name in {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}]
    dockerfiles = [path for path in paths if Path(path).name.lower() == "dockerfile" or path.endswith(".dockerfile")]
    server_entry = any(Path(path).name in {"server.py", "server.js", "server.ts", "server.go", "server.rb", "server.php", "app.py"} for path in paths)
    service_config = any(token in joined for token in ("nsjail", "xinetd", "gunicorn"))
    declared_port = False
    remote_service = False
    for relative in paths:
        if Path(relative).name not in {"challenge.yaml", "challenge.yml", "metadata.yaml", "metadata.yml"}:
            continue
        try:
            text = (directory / relative).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if re.search(r"(?m)^\s*(?:ports?|targetPort|containerPort):(?:\s*(?:\[|\{|[1-9]))?\s*$", text):
            declared_port = True
    for path in directory.iterdir() if directory.is_dir() else []:
        if not path.is_file() or not path.name.lower().startswith(("readme", "description")):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"(?im)(?:^|[` ])(?:nc|ncat|socat)\s+\S+\s+\d{2,5}(?:[` ]|$)", text):
            remote_service = True
    service = bool(compose_paths or server_entry or service_config or declared_port or remote_service)
    multi_container = False
    for relative in compose_paths:
        try:
            text = (directory / relative).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        service_names = re.findall(r"(?m)^  ([A-Za-z0-9_.-]+):\s*(?:$|#)", text.split("services:", 1)[-1])
        if len(set(service_names)) > 1:
            multi_container = True
    return {"service": service, "browser_bot": browser, "vm_or_kernel": vm_kernel, "multi_container": multi_container, "dockerfiles": dockerfiles, "compose_files": compose_paths, "remote_service_description": remote_service}


def audit(catalog_name: str, catalog: dict[str, object], repo: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in catalog["challenges"]:
        relative_directory = source_relative(item)
        directory = repo / relative_directory
        try:
            tree_paths = subprocess.check_output(["git", "-c", "core.quotePath=false", "-C", str(repo), "ls-tree", "-r", "--name-only", "HEAD", "--", str(relative_directory)], text=True).splitlines()
        except (OSError, subprocess.SubprocessError):
            tree_paths = []
        tree_relative = [str(Path(path).relative_to(relative_directory)) for path in tree_paths]
        source_exists = directory.is_dir() or bool(tree_paths)
        flags = trusted_flag_candidates(directory) if directory.is_dir() else []
        catalog_flag = item.get("official_flag")
        if isinstance(catalog_flag, str) and catalog_flag:
            flags.insert(0, {"value": catalog_flag, "path": "catalog", "source_class": "catalog_metadata"})
        unique_flags = {candidate["value"] for candidate in flags}
        resolved_flag = catalog_flag if isinstance(catalog_flag, str) and catalog_flag else (next(iter(unique_flags)) if len(unique_flags) == 1 else None)
        catalog_paths = [str(record["path"]) for record in item.get("files", []) if isinstance(record, dict) and isinstance(record.get("path"), str)]
        all_paths = sorted(set(catalog_paths + tree_relative))
        handouts = handout_paths(directory, all_paths) if source_exists else []
        runtime = topology(directory, all_paths) if source_exists else {"service": False, "browser_bot": False, "vm_or_kernel": False, "multi_container": False, "dockerfiles": [], "compose_files": []}
        review_flags = set(item.get("review_flags") or [])
        name = record_name(item)
        shared = "probable_shared_component_not_standalone_challenge" in review_flags or name.lower() in {"kctf", "third_party", "common", "shared", "support"}
        reasons: list[str] = []
        handout_leaks_flag = False
        if resolved_flag and directory.is_dir():
            flag_bytes = resolved_flag.encode()
            for relative in handouts:
                path = directory / relative
                if path.is_file() and path.stat().st_size <= 2_000_000 and flag_bytes in path.read_bytes():
                    handout_leaks_flag = True
                    break
        if not source_exists:
            status, mode = "blocked", None; reasons.append("pinned_source_directory_missing")
        elif shared:
            status, mode = "excluded", None; reasons.append("not_a_standalone_challenge")
        elif runtime["vm_or_kernel"]:
            status, mode = "blocked", "vm_or_kernel"; reasons.append("requires_disposable_vm_or_nested_virtualization")
        elif runtime["browser_bot"]:
            status, mode = "blocked", "browser_bot"; reasons.append("browser_bot_runtime_not_implemented")
        elif runtime["multi_container"]:
            status, mode = "blocked", "multi_container_service"; reasons.append("multi_container_runtime_not_implemented")
        elif handout_leaks_flag:
            status, mode = "blocked", "original_attachment"; reasons.append("official_handout_contains_plaintext_flag")
        elif resolved_flag is None:
            status, mode = "blocked", "original_service" if runtime["service"] else "original_attachment"; reasons.append("official_flag_unresolved" if not unique_flags else "multiple_distinct_flag_candidates")
        elif not catalog_flag and len(unique_flags) > 1:
            status, mode = "blocked", "original_service" if runtime["service"] else "original_attachment"; reasons.append("multi_flag_semantics_requires_review")
        elif runtime["service"]:
            status, mode = "build_candidate", "original_service"; reasons.append("service_image_not_built_and_digest_pinned")
        elif handouts:
            status, mode = "ready", "original_attachment"; reasons.append("official_handout_and_flag_resolved")
        else:
            status, mode = "blocked", "original_attachment"; reasons.append("player_handout_not_identified")
        rows.append({
            "catalog": catalog_name,
            "event": item.get("event") or catalog.get("event"),
            "challenge": name,
            "source": item.get("source"),
            "commit": item.get("commit") or catalog.get("commit"),
            "status": status,
            "mode": mode,
            "reasons": reasons,
            "official_flag_resolved": resolved_flag is not None,
            "resolved_official_flag": resolved_flag,
            "flag_evidence_conflict": len(unique_flags) > 1,
            "flag_evidence": flags,
            "handout_paths": handouts,
            "handout_leaks_flag": handout_leaks_flag,
            "topology": runtime,
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog-dir", type=Path, required=True)
    parser.add_argument("--repo-map", type=Path, required=True, help="JSON object mapping catalog filename to checked-out repo")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo_map = json.loads(args.repo_map.read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    for catalog_name, repo_text in sorted(repo_map.items()):
        catalog = json.loads((args.catalog_dir / catalog_name).read_text(encoding="utf-8"))
        rows.extend(audit(catalog_name, catalog, Path(repo_text)))
    status_counts = Counter(row["status"] for row in rows)
    mode_counts = Counter(str(row["mode"]) for row in rows)
    reason_counts = Counter(reason for row in rows for reason in row["reasons"])
    result = {
        "schema": "authority-world-original-ctf-full-audit-v1",
        "policy": "Ready means an official player handout and one official flag are resolved and the current runtime preserves the original challenge mode. Service build candidates are not counted as ready until their official image builds, is digest-pinned, and passes isolation smoke tests.",
        "record_count": len(rows),
        "status_counts": dict(sorted(status_counts.items())),
        "mode_counts": dict(sorted(mode_counts.items())),
        "reason_counts": dict(sorted(reason_counts.items())),
        "records": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"record_count": len(rows), "status_counts": result["status_counts"], "reason_counts": result["reason_counts"]}, sort_keys=True))


if __name__ == "__main__":
    main()
