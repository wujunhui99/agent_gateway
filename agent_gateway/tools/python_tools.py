from __future__ import annotations

from typing import Any, Dict, Optional

from langchain_core.tools import tool

from .async_utils import run_coro_sync
from .mcp_client import call_mcp_tool, parse_mcp_call_result
from .schemas import PythonExecuteInput


def build_python_tools(mcp_url: Optional[str], *, enabled: bool) -> Dict[str, Any]:
    if not enabled or not mcp_url:
        return {}

    @tool("python_execute", args_schema=PythonExecuteInput)
    def python_execute(code: str, input: Optional[str] = None) -> Dict[str, Any]:
        """Execute Python code via the MCP sandbox and return the result."""
        async def _run():
            arguments: Dict[str, Any] = {"code": code}
            if input is not None:
                arguments["input"] = input
            call_result = await call_mcp_tool(mcp_url, "python_execute", arguments)
            payload = parse_mcp_call_result(call_result)
            return {"status": "success", **payload}

        return run_coro_sync(_run())

    return {"python_execute": python_execute}
