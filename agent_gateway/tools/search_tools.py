from __future__ import annotations

import os
from typing import Any, Dict

from langchain_community.utilities import SerpAPIWrapper
from langchain_core.tools import tool

from .schemas import WebSearchInput


def build_search_tools() -> Dict[str, Any]:
    @tool("web_search", args_schema=WebSearchInput)
    def web_search(query: str) -> Dict[str, Any]:
        """Run a SerpAPI web search and return the raw results."""
        api_key = os.getenv("SERPAPI_API_KEY")
        if not api_key:
            raise RuntimeError("SERPAPI_API_KEY not configured")
        wrapper = SerpAPIWrapper(serpapi_api_key=api_key)
        result = wrapper.run(query)
        return {"status": "success", "query": query, "result": result}

    return {"web_search": web_search}
