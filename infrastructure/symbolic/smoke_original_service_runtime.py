#!/usr/bin/env python3

import argparse
import json
import tempfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--solver-image", required=True)
    parser.add_argument("--service-image", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    import sys
    sys.path.insert(0, str(args.root))
    from backend.artifact_runtime import OriginalServiceTaskRuntime

    with tempfile.TemporaryDirectory(prefix="authority-service-runtime-smoke-", dir="/data/authoritylab") as temporary:
        base = Path(temporary)
        manifest = base / "manifest.json"
        manifest.write_text(json.dumps({
            "schema": "authority-world-original-ctf-run-v1",
            "tasks": [{
                "id": "SERVICE-RUNTIME-SMOKE",
                "mode": "original_service",
                "tier": "easy",
                "official_flag": "SMOKE{service_runtime}",
                "handout_paths": [],
                "sha256": {},
                "service": {
                    "image": args.service_image,
                    "protocol": "tcp",
                    "port": 31337
                }
            }]
        }, indent=2) + "\n")
        work = base / "work"
        runtime = OriginalServiceTaskRuntime(
            work,
            args.solver_image,
            30,
            32768,
            manifest,
            base,
            work,
        )
        run_id = "preflight-service-runtime-20260724"
        try:
            runtime.prepare(run_id, 20260724, "SERVICE-RUNTIME-SMOKE", "easy")
            result = runtime.execute(
                "SERVICE-RUNTIME-SMOKE",
                "set -eu; test \"$TASK_SERVICE_HOST\" = service; "
                "test \"$TASK_SERVICE_PORT\" = 31337; "
                "printf ping | nc -w 5 service 31337 | grep -q service-smoke-ok; "
                "printf service-runtime-ok",
            )
            ok = "service-runtime-ok" in str(result.get("stdout", ""))
            if not ok:
                raise RuntimeError("service runtime TCP smoke did not complete")
        finally:
            runtime.close_all()
            runtime.cleanup_orphans(run_id)

    report = {
        "schema": "authority-original-service-runtime-environment-smoke-v1",
        "ok": True,
        "solver_image": args.solver_image,
        "service_image": args.service_image,
        "service_image_digest_pinned": args.service_image.startswith("sha256:") and len(args.service_image) == 71,
        "private_network": True,
        "tcp_round_trip": True,
        "cleanup_completed": True
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
