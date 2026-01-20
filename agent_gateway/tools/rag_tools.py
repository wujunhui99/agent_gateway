from __future__ import annotations

from typing import Any, Dict, Optional

from langchain_core.tools import tool

from .schemas import RagSearchInput
from ..config import Settings
from ..rag.store import RAGStore


def build_rag_tools(settings: Optional[Settings], rag_store: Optional[RAGStore]) -> Dict[str, Any]:
    retriever_cache: Dict[str, Any] = {}

    def _get_retriever():
        if retriever_cache.get("retriever"):
            return retriever_cache["retriever"]
        if not settings or not settings.rag_enabled:
            raise RuntimeError("RAG tool is not enabled in settings.")
        store = rag_store or RAGStore(
            persist_directory=settings.rag_persist_directory,
            embedding_model=settings.rag_embedding_model,
            embedding_api_key=settings.rag_embedding_api_key,
            embedding_api_base=settings.rag_embedding_api_base,
        )
        retriever_cache["retriever"] = store.as_retriever(k=settings.rag_top_k)
        return retriever_cache["retriever"]

    @tool("rag_search", args_schema=RagSearchInput)
    def rag_search(query: str) -> Dict[str, Any]:
        """Search the configured RAG store for content relevant to the query."""
        retriever = _get_retriever()
        docs = retriever.invoke(query)
        return {"status": "success", "query": query, "results": [doc.page_content for doc in docs]}

    return {"rag_search": rag_search} if settings and settings.rag_enabled else {}
