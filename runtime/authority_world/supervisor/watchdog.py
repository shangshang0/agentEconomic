"""Host-controlled circuit breaker for technical-invalid agent runs."""
from __future__ import annotations
import json, os, socket, time, urllib.request
from pathlib import Path

BACKEND = os.getenv("BACKEND_URL", "http://backend:8100").rstrip("/")
TOKEN = os.environ["WORLD_CONTROL_TOKEN"]
AGENTS = [Path(f"/agent-state/a{index}/executor.degraded") for index in range(1, 7)]
MARKER = Path("/world-data/TECHNICAL_FAILURE.json")
CONTAINERS = [f"authority-world-v1-agent_a{index}-1" for index in range(1, 7)]

def freeze(reason: str) -> None:
    payload = json.dumps({"reason": reason}).encode()
    request = urllib.request.Request(BACKEND + "/v1/control/freeze-technical", data=payload, method="POST", headers={"Content-Type": "application/json", "X-World-Control-Token": TOKEN})
    try:
        urllib.request.urlopen(request, timeout=5).read()
    except Exception:
        pass


def stop_agents() -> None:
    """Host-supervisor authority only; never available to an Agent."""
    for container in CONTAINERS:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(3)
                client.connect("/var/run/docker.sock")
                payload = f"POST /v1.41/containers/{container}/stop?t=2 HTTP/1.1\r\nHost: docker\r\nContent-Length: 0\r\n\r\n"
                client.sendall(payload.encode())
                client.recv(1024)
        except Exception:
            continue

SUSTAINED_DEGRADED_SECONDS = float(os.getenv("SUSTAINED_DEGRADED_SECONDS", "18"))

while True:
    # A container restart can leave a stale degraded marker on its writable
    # volume for a fraction of a second.  Treat only a marker that persists
    # through a sustained window as a run failure.  This does not mask an
    # executor outage: runners continue writing the marker while their wake
    # transport is unavailable.
    now = time.time()
    failed = [path.parent.name for path in AGENTS if path.exists() and now - path.stat().st_mtime >= SUSTAINED_DEGRADED_SECONDS]
    if failed:
        reason = "runner degraded after three wake failures: " + ",".join(failed)
        MARKER.parent.mkdir(parents=True, exist_ok=True)
        MARKER.write_text(json.dumps({"reason": reason, "at": time.time()}), encoding="utf-8")
        stop_agents()
        freeze(reason)
        time.sleep(5)
    time.sleep(1)
