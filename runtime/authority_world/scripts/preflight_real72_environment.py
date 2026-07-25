#!/usr/bin/env python3

import argparse
import collections
import json
import re
import sys
import time
import traceback
from pathlib import Path

# Allow the documented invocation ``python3 scripts/preflight_real72_environment.py``
# to import the repository packages without requiring an external PYTHONPATH.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.artifact_runtime import OriginalCTFTaskRuntime


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", type=Path, default=ROOT)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--image", default="authority-world-task:real72-v4")
    parser.add_argument("--output", type=Path, default=ROOT / "output/real72-environment-preflight.json")
    args = parser.parse_args()
    manifest_path = args.base_dir / "task-catalog/original-ctf-real72-ranked.json"
    source = args.source_root or (args.base_dir / "ctf-originals/real72")
    if not source.is_dir():
        raise SystemExit(f"CTF source root does not exist: {source}")
    work = args.base_dir / "preflight-work"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    runtime = OriginalCTFTaskRuntime(work, args.image, 300, 32768, manifest_path, source, work)
    mode_counts = collections.Counter(task.get("mode") for task in manifest["tasks"])
    service_images = [
        task.get("service", {}).get("image")
        for task in manifest["tasks"]
        if task.get("mode") == "original_service"
    ]
    digest_pattern = re.compile(r"(?:^sha256:|@sha256:)[0-9a-f]{64}$")
    digest_pinned_services = all(
        isinstance(image, str) and digest_pattern.search(image)
        for image in service_images
    )
    results = []
    for index, task in enumerate(manifest["tasks"], 1):
        started = time.time()
        result = {"id": task["id"], "tier": task["tier"], "mode": task.get("mode"), "ok": False}
        try:
            runtime.prepare("preflight-v4", 2026071805, task["id"], task["tier"])
            output = runtime.execute(task["id"], "set -eu; test -r /task; test -w /work; test -w /tmp; find /task -type f -readable | grep -q .; command -v python3 >/dev/null; command -v sage >/dev/null; command -v clamscan >/dev/null; printf preflight-ok")
            if "preflight-ok" not in output.get("stdout", ""):
                raise RuntimeError("smoke command did not complete")
            result.update(ok=True, files=len(task["handout_paths"]), seconds=round(time.time() - started, 3))
        except Exception as error:
            result.update(error=str(error), traceback=traceback.format_exc(), seconds=round(time.time() - started, 3))
        finally:
            runtime.close(task["id"])
        results.append(result)
        print(f"{index:02d}/72 {task['id']} {'PASS' if result['ok'] else 'FAIL'}", flush=True)

    special = {}
    devil = next(task for task in manifest["tasks"] if task["id"] == "SECCON22-devil-hunter")
    runtime.prepare("preflight-v4-special", 2026071805, devil["id"], devil["tier"])
    try:
        flag_literal = json.dumps(devil["official_flag"])
        command = (
            "cd /task/SECCON22-devil-hunter/files/devil_hunter; "
            f"python3 -c 'open(\"/work/correct\",\"wb\").write({flag_literal}.encode())'; "
            "printf %s 'SECCON{wrong}' >/work/wrong; "
            "set +e; clamscan --bytecode-unsigned=yes --quiet -dflag.cbc /work/correct >/dev/null; correct=$?; "
            "clamscan --bytecode-unsigned=yes --quiet -dflag.cbc /work/wrong >/dev/null; wrong=$?; set -e; "
            "test $correct -eq 1; test $wrong -eq 0; echo clamav-check-ok"
        )
        output = runtime.execute(devil["id"], command)
        special["devil_hunter_clamav"] = "clamav-check-ok" in output.get("stdout", "")
    finally:
        runtime.close(devil["id"])

    sage_results = []
    sage_files = sorted(source.rglob("*.sage"))
    for path in sage_files:
        task_id = path.relative_to(source).parts[0]
        task = next(task for task in manifest["tasks"] if task["id"] == task_id)
        runtime.prepare("preflight-v4-sage", 2026071805, task_id, task["tier"])
        try:
            relative = "/task/" + str(path.relative_to(source))
            output = runtime.execute(task_id, f"cp {json.dumps(relative)} /work/input.sage; sage --preparse /work/input.sage; test -s /work/input.sage.py; echo sage-ok")
            sage_results.append({"path": str(path.relative_to(source)), "ok": "sage-ok" in output.get("stdout", "")})
        except Exception as error:
            sage_results.append({"path": str(path.relative_to(source)), "ok": False, "error": str(error)})
        finally:
            runtime.close(task_id)
    special["sage_files_total"] = len(sage_files)
    special["sage_results"] = sage_results
    report = {
        "schema": "authority-world-real72-environment-preflight-v2",
        "image": args.image,
        "mode_counts": dict(mode_counts),
        "service_images": service_images,
        "service_images_digest_pinned": digest_pinned_services,
        "passed": sum(result["ok"] for result in results),
        "failed": sum(not result["ok"] for result in results),
        "special": special,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    summary = {
        "passed": report["passed"],
        "failed": report["failed"],
        "clamav": special["devil_hunter_clamav"],
        "sage_passed": sum(result["ok"] for result in sage_results),
        "sage_total": len(sage_results),
        "mode_counts": dict(mode_counts),
        "service_images_digest_pinned": digest_pinned_services,
    }
    print(json.dumps(summary), flush=True)
    if report["failed"] or not digest_pinned_services or not special["devil_hunter_clamav"] or any(not result["ok"] for result in sage_results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
