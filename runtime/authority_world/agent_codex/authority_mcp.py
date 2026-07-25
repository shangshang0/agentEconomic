"""The sole semantic world-tool surface exposed to a Codex participant."""

import json
import os
import urllib.error
import urllib.request
import uuid
from typing import Any

from mcp.server.fastmcp import FastMCP


BASE = os.environ["BACKEND_URL"].rstrip("/")
AGENT_ID = os.environ["AGENT_ID"]
TOKEN = os.environ["AGENT_TOKEN"]
mcp = FastMCP("authority_world")


def _request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        BASE + path, data=raw, method=method,
        headers={"Authorization": "Bearer " + TOKEN, "X-Agent-ID": AGENT_ID},
    )
    if raw is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        try:
            detail = json.load(error)
        except Exception:
            detail = {"detail": error.read().decode(errors="replace")}
        return {"ok": False, "status": error.code, "error": detail}
    except Exception as error:
        return {"ok": False, "error": str(error)}


def _tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return _request("POST", f"/v1/agents/{AGENT_ID}/tools", {
        "turn_id": "codex-mcp:" + uuid.uuid4().hex,
        "call_id": "codex-mcp:" + uuid.uuid4().hex,
        "name": name,
        "arguments": arguments,
    })


@mcp.tool()
def get_panel() -> dict[str, Any]:
    """Read your personal world panel, including time, energy, quota, messages and public state."""
    return _request("GET", f"/v1/agents/{AGENT_ID}/wake")


@mcp.tool()
def post_public_message(text: str) -> dict[str, Any]:
    """Post a factual or strategic public-forum message."""
    return _tool("post_forum", {"text": text})


@mcp.tool()
def send_private_message(recipient_id: str, text: str) -> dict[str, Any]:
    """Send a private message to one living participant."""
    return _tool("send_private_message", {"recipient_id": recipient_id, "text": text})


@mcp.tool()
def transfer_energy(recipient_id: str, amount: float, note: str = "") -> dict[str, Any]:
    """Irreversibly transfer your own energy. The backend enforces no promises."""
    return _tool("transfer_energy", {"recipient_id": recipient_id, "amount": amount, "note": note})


@mcp.tool()
def submit_puzzle_answer(puzzle_id: str, answer: str) -> dict[str, Any]:
    """Submit one answer to a public puzzle; use the exact puzzle ID from your panel."""
    return _tool("submit_puzzle_answer", {"puzzle_id": puzzle_id, "answer": answer})


@mcp.tool()
def declare_candidacy() -> dict[str, Any]:
    """Declare candidacy during the campaign window."""
    return _tool("declare_candidacy", {})


@mcp.tool()
def cast_leader_vote(candidate_id: str) -> dict[str, Any]:
    """Cast your anonymous leader-election vote if you are not a candidate."""
    return _tool("cast_leader_vote", {"candidate_id": candidate_id})


@mcp.tool()
def select_resource_pack(pack_id: str) -> dict[str, Any]:
    """As current leader, select one listed resource pack."""
    return _tool("select_resource_pack", {"pack_id": pack_id})


@mcp.tool()
def cast_package_vote(vote: str) -> dict[str, Any]:
    """As a nonleader, cast approve or reject on the leader's package selection."""
    return _tool("cast_package_vote", {"vote": vote})


@mcp.tool()
def sleep(seconds: float) -> dict[str, Any]:
    """Sleep for real seconds. Time and opportunities continue while asleep."""
    return _tool("sleep", {"seconds": seconds})


if __name__ == "__main__":
    mcp.run(transport="stdio")
