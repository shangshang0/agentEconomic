#!/usr/bin/env python3
"""Fail closed if the deployed container/security topology drifts."""

from __future__ import annotations

import json
import subprocess
import sys


AGENTS = [f"authoritylab-agent-p{number}" for number in range(1, 6)]
BACKEND = "authoritylab-backend"
GATEWAY = "authoritylab-gateway"
PROXY = "authoritylab-observer-proxy"


def inspect(name):
    return json.loads(subprocess.check_output(["docker", "inspect", name], text=True))[0]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def env_keys(info):
    return {item.split("=", 1)[0] for item in info["Config"].get("Env", [])}


def exec_python(container, source):
    return subprocess.run(["docker", "exec", container, "python", "-c", source], text=True, capture_output=True, timeout=15)


def main():
    backend = inspect(BACKEND)
    gateway = inspect(GATEWAY)
    proxy = inspect(PROXY)
    backend_networks = set(backend["NetworkSettings"]["Networks"])
    gateway_networks = set(gateway["NetworkSettings"]["Networks"])
    require(len(backend_networks) == 6, "backend must have control plus five participant networks")
    require(len(gateway_networks) == 2, "gateway must have control and provider egress only")
    require(len(backend_networks & gateway_networks) == 1, "backend and gateway must share exactly the control network")
    require("OPENAI_API_KEY" not in env_keys(backend), "backend must not hold provider credentials")
    gateway_keys = env_keys(gateway)
    require("OPENAI_API_KEY" in gateway_keys, "gateway must be the provider credential holder")
    require("CONTROL_TOKEN" not in gateway_keys and "AGENT_TOKENS_JSON" not in gateway_keys, "gateway has excess authority secrets")
    proxy_keys = env_keys(proxy)
    require(not ({"OPENAI_API_KEY", "CONTROL_TOKEN", "AGENT_TOKENS_JSON", "GATEWAY_TOKEN", "DASHBOARD_TOKEN"} & proxy_keys), "observer proxy has secrets")
    require(not proxy["Mounts"], "observer proxy must have no mounts")
    require(len(proxy["NetworkSettings"]["Networks"]) == 2, "observer proxy must bridge control to host publication only")

    for index, name in enumerate(AGENTS, 1):
        info = inspect(name)
        networks = set(info["NetworkSettings"]["Networks"])
        require(len(networks) == 1, f"{name} must have exactly one private network")
        require(networks <= backend_networks, f"{name} network must connect only through backend")
        require(not info["Mounts"], f"{name} must have no host or volume mounts")
        require(info["HostConfig"].get("ReadonlyRootfs") is True, f"{name} root filesystem is writable")
        require("ALL" in info["HostConfig"].get("CapDrop", []), f"{name} did not drop all capabilities")
        keys = env_keys(info)
        forbidden = {key for key in keys if any(word in key for word in ("OPENAI", "GATEWAY", "CONTROL", "DASHBOARD"))}
        require(not forbidden, f"{name} contains forbidden secret classes")
        # It can resolve backend, but neither gateway, peers, nor public DNS.
        allowed = exec_python(name, "import socket; socket.gethostbyname('backend')")
        require(allowed.returncode == 0, f"{name} cannot resolve backend")
        peer = "authoritylab-agent-p2" if index == 1 else "authoritylab-agent-p1"
        denied = exec_python(
            name,
            f"import socket,sys\nfor host in ['gateway','{peer}','example.com']:\n try: socket.gethostbyname(host); sys.exit(1)\n except OSError: pass",
        )
        require(denied.returncode == 0, f"{name} can resolve a forbidden host")
        observer = exec_python(
            name,
            "import urllib.request,urllib.error,sys\ntry: urllib.request.urlopen('http://backend:8000/v1/observer/snapshot',timeout=3); sys.exit(1)\nexcept urllib.error.HTTPError as e: sys.exit(0 if e.code==403 else 2)",
        )
        require(observer.returncode == 0, f"{name} can read observer data without authentication")
    print("Isolation PASS: five private participant networks; observer sealed; gateway-only provider egress and credentials.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, subprocess.SubprocessError) as error:
        print(f"Isolation FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
