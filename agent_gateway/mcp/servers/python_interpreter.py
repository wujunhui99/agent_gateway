"""MCP server exposing a Dockerised Python interpreter tool."""

import asyncio
from typing import Any, Dict

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from ..executor import run_python_sandbox


def build_server() -> FastMCP:
    server = FastMCP(
        name="agent-python-interpreter",
        instructions="Execute ad-hoc Python code inside an isolated Docker sandbox.",
    )

    @server.tool(
        name="python_execute",
        description="Run Python code in the sandbox and return stdout/stderr plus locals.",
    )
    async def python_execute(code: str, input: str | None = None) -> Dict[str, Any]:
        preview_code = code[:80] + ("..." if len(code) > 80 else "")
        preview_input = (input or "")[:80] + ("..." if input and len(input) > 80 else "")
        print("[MCP] python_execute request:", {"code": preview_code, "input": preview_input})
        try:
            return await asyncio.to_thread(run_python_sandbox, code, input)
        except RuntimeError as exc:
            raise ToolError(str(exc)) from exc

    return server


__all__ = ["build_server"]
