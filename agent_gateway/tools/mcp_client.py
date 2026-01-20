from __future__ import annotations

import asyncio
import json
import logging
from datetime import timedelta
from typing import Any, Dict, List

from mcp import types as mcp_types
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.shared.exceptions import McpError

logger = logging.getLogger(__name__)


async def call_mcp_tool(
    url: str,
    name: str,
    arguments: Dict[str, Any],
    *,
    timeout_seconds: int = 120,
) -> mcp_types.CallToolResult:
    """Invoke an MCP tool over SSE and return the raw CallToolResult."""
    if not url:
        raise RuntimeError("MCP server URL is not configured for tool execution.")

    logger.debug("Invoking MCP tool '%s' via %s", name, url)
    read_stream = None
    write_stream = None
    session = None

    try:
        async with sse_client(url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(
                    name=name,
                    arguments=arguments,
                    read_timeout_seconds=timedelta(seconds=timeout_seconds),
                )
                logger.debug("MCP tool '%s' completed successfully", name)
                # Give the session time to clean up properly before exiting
                await asyncio.sleep(0.1)
                return result
    except McpError as exc:
        logger.error("MCP error from tool '%s': %s", name, exc, exc_info=True)
        raise RuntimeError(f"MCP tool '{name}' failed: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to invoke MCP tool '%s': %s", name, exc, exc_info=True)
        raise RuntimeError(f"MCP tool '{name}' call failed: {exc}") from exc


def format_tool_content(contents: List[mcp_types.Content]) -> str:
    """Convert MCP content items into a single text blob."""
    chunks: List[str] = []
    for item in contents:
        if isinstance(item, mcp_types.TextContent):
            chunks.append(item.text)
        else:
            try:
                chunks.append(json.dumps(item.model_dump(), ensure_ascii=False))
            except Exception:  # noqa: BLE001
                chunks.append(str(item))
    return "\n".join(chunk for chunk in chunks if chunk).strip()


def parse_mcp_call_result(result: mcp_types.CallToolResult) -> Dict[str, Any]:
    """Normalise an MCP CallToolResult into a Python dict."""
    if result.isError:
        message = format_tool_content(result.content) or "Unknown MCP tool error"
        raise RuntimeError(message)

    if not result.content:
        return {}

    text_payload = format_tool_content(result.content)
    if not text_payload:
        return {}

    try:
        return json.loads(text_payload)
    except json.JSONDecodeError:
        return {"output": text_payload}
