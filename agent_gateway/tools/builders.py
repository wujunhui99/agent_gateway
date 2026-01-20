from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict, Optional

from langchain_core.tools import BaseTool, StructuredTool

from ..config import Settings
from ..openim import OpenIMClient
from ..rag.store import RAGStore
from .agent_mgmt_tools import build_agent_mgmt_tools
from .openim_tools import build_openim_tools
from .python_tools import build_python_tools
from .rag_tools import build_rag_tools
from .search_tools import build_search_tools

logger = logging.getLogger(__name__)


def build_agent_tools(
    client: OpenIMClient,
    settings: Settings | None = None,
    *,
    create_agent_fn: Optional[Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = None,
    mcp_server_url: Optional[str] = None,
    rag_store: Optional[RAGStore] = None,
) -> Dict[str, BaseTool]:
    """Assemble available tools with lightweight wrappers."""
    tools: Dict[str, Any] = {}
    tools.update(build_openim_tools(client))
    tools.update(build_search_tools())
    tools.update(build_rag_tools(settings, rag_store))

    python_enabled = settings is None or settings.enable_python_tool
    tools.update(build_python_tools(mcp_server_url, enabled=python_enabled))
    tools.update(build_agent_mgmt_tools(create_agent_fn))

    if python_enabled and not mcp_server_url:
        logger.warning("Python tool enabled but MCP server URL missing; tool not registered.")

    # LangChain agents expect StructuredTool/BaseTool instances
    structured: Dict[str, StructuredTool | BaseTool] = {}
    for name, fn in tools.items():
        if isinstance(fn, BaseTool):
            structured[name] = fn
        else:
            structured_tool = StructuredTool.from_function(fn)
            structured[name] = structured_tool
    return structured
