"""Protocol smoke test for the isolated Authority World MCP server.

This checks the actual stdio process and tool registry, rather than merely
checking that a Codex config file contains an MCP stanza.
"""

from __future__ import annotations

import asyncio
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


EXPECTED = {
    "get_panel", "post_public_message", "send_private_message",
    "transfer_energy", "submit_puzzle_answer", "declare_candidacy",
    "cast_leader_vote", "select_resource_pack", "cast_package_vote", "sleep",
}


async def main() -> None:
    params = StdioServerParameters(
        command="python3", args=["/app/agent_codex/authority_mcp.py"], env=os.environ.copy()
    )
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            registered = {tool.name for tool in (await session.list_tools()).tools}
    missing = EXPECTED - registered
    if missing:
        raise SystemExit("MCP tools missing: " + ", ".join(sorted(missing)))
    print("Authority World MCP protocol smoke PASS")


if __name__ == "__main__":
    asyncio.run(main())
