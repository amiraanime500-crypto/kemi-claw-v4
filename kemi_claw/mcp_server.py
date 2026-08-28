"""Kemi MCP server.

A small MCP surface inspired by Hermes Agent's MCP bridge, adapted to Kemi's
architecture. It exposes Kemi as a local stdio MCP server so clients such as
Claude Code, Cursor, and Codex can discover Kemi and invoke its capabilities.

Execution tools are disabled by default. Set KEMI_MCP_ALLOW_EXECUTION=1 in the
MCP server environment to enable agent execution and authorized security scans.
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("Kemi-Claw")


def _execution_enabled() -> bool:
    return os.getenv("KEMI_MCP_ALLOW_EXECUTION", "0").strip().lower() in {
        "1", "true", "yes", "on"
    }


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


@mcp.tool()
def kemi_health() -> str:
    """Return Kemi version and registered tool count."""
    from kemi_claw.config import VERSION
    from kemi_claw.tools.mcp_registry import registry

    return _json({
        "agent": "Kemi-Claw",
        "version": VERSION,
        "tools_count": len(registry.manifest()),
        "execution_enabled": _execution_enabled(),
    })


@mcp.tool()
def kemi_tools() -> str:
    """List Kemi's registered tool manifest."""
    from kemi_claw.tools.mcp_registry import registry

    return _json(registry.manifest())


@mcp.tool()
async def kemi_agent(goal: str, user_id: str = "mcp") -> str:
    """Run Kemi's general autonomous agent for a task.

    This tool can execute shell commands, browser actions, HTTP requests, file
    operations, and package installation. It is therefore disabled unless the
    MCP host explicitly sets KEMI_MCP_ALLOW_EXECUTION=1.
    """
    if not _execution_enabled():
        return _json({
            "error": "MCP execution is disabled",
            "hint": "Set KEMI_MCP_ALLOW_EXECUTION=1 for this MCP server process.",
        })

    if not goal or len(goal) > 4000:
        return _json({"error": "goal must be between 1 and 4000 characters"})

    from kemi_claw.core.general_agent import GeneralAgent

    result = await GeneralAgent().run(goal, user_id=user_id or "mcp")
    return _json(result)


@mcp.tool()
async def kemi_scan(target: str, goal: str = "full reconnaissance") -> str:
    """Run Kemi's authorized security agent against an HTTP(S) target."""
    if not _execution_enabled():
        return _json({
            "error": "MCP execution is disabled",
            "hint": "Set KEMI_MCP_ALLOW_EXECUTION=1 for this MCP server process.",
        })

    parsed = urlparse(target)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return _json({"error": "target must be an http(s) URL"})
    if parsed.username or parsed.password:
        return _json({"error": "target credentials are not allowed"})
    if len(target) > 2048:
        return _json({"error": "target is too long"})

    from kemi_claw.core.agent import KemiClawAgent

    result = await KemiClawAgent().run(goal, target, authorized=True)
    return _json(result)


@mcp.tool()
def kemi_read_file(path: str, max_lines: int = 200) -> str:
    """Read a text file using Kemi's existing file tool."""
    from kemi_claw.tools.env_control import file_read

    max_lines = max(1, min(int(max_lines), 5000))
    return _json(file_read(path, max_lines))


@mcp.tool()
def kemi_list_files(directory: str = ".", pattern: str = "*") -> str:
    """List files using Kemi's existing file tool."""
    from kemi_claw.tools.env_control import file_list

    return _json(file_list(directory, pattern))


@mcp.tool()
def kemi_web_search(query: str, max_results: int = 5) -> str:
    """Search the web using Kemi's existing search tool."""
    from kemi_claw.tools.web_search import web_search

    max_results = max(1, min(int(max_results), 20))
    return _json(web_search(query, max_results))


def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
