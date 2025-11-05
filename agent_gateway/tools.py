from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import timedelta
from functools import wraps
from typing import Any, Awaitable, Callable, Dict, List, Optional

from langchain_community.utilities import SerpAPIWrapper
from langchain_core.tools import StructuredTool
from pydantic import AnyHttpUrl, BaseModel, Field

from mcp import types as mcp_types
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.shared.exceptions import McpError

from .config import Settings
from .openim import OpenIMClient
from .rag.store import RAGStore

# Configure logging
logger = logging.getLogger(__name__)


def debug_tool_call(tool_name: str):
    """Decorator to add debug logging for tool calls"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Log tool invocation
            logger.info(f"[TOOL CALL] {tool_name}")
            logger.info(f"[TOOL ARGS] args={args}, kwargs={kwargs}")

            # Print to console for visibility
            print(f"\n{'='*60}")
            print(f"🔧 TOOL CALLED: {tool_name}")
            print(f"{'='*60}")

            # Format arguments nicely
            if args:
                print(f"📥 Positional Arguments:")
                for i, arg in enumerate(args):
                    arg_str = str(arg)[:200]  # Limit length
                    print(f"   [{i}] {arg_str}")

            if kwargs:
                print(f"📥 Keyword Arguments:")
                for key, value in kwargs.items():
                    value_str = str(value)[:400]  # Limit length
                    print(f"   {key} = {value_str}")

            try:
                # Execute the actual function
                result = func(*args, **kwargs)

                # Log success
                logger.info(f"[TOOL SUCCESS] {tool_name}")
                logger.debug(f"[TOOL RESULT] {result}")

                print(f"✅ TOOL SUCCESS")

                # Format result nicely
                if isinstance(result, dict):
                    print(f"📤 Result:")
                    for key, value in result.items():
                        value_str = str(value)[:200]
                        print(f"   {key} = {value_str}")
                else:
                    result_str = str(result)[:300]
                    print(f"📤 Result: {result_str}")

                print(f"{'='*60}\n")

                return result

            except Exception as exc:
                # Log error
                logger.error(f"[TOOL ERROR] {tool_name}: {exc}")

                print(f"❌ TOOL ERROR: {exc}")
                print(f"{'='*60}\n")

                raise

        return wrapper
    return decorator


def _run_async(coro: Awaitable[Any]) -> Any:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _call_mcp_tool(
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
    try:
        async with sse_client(url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                return await session.call_tool(
                    name=name,
                    arguments=arguments,
                    read_timeout_seconds=timedelta(seconds=timeout_seconds),
                )
    except McpError as exc:
        logger.error("MCP error from tool '%s': %s", name, exc)
        raise RuntimeError(f"MCP tool '{name}' failed: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to invoke MCP tool '%s': %s", name, exc)
        raise RuntimeError(f"MCP tool '{name}' call failed: {exc}") from exc


def _format_tool_content(contents: List[mcp_types.Content]) -> str:
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


def _parse_mcp_call_result(result: mcp_types.CallToolResult) -> Dict[str, Any]:
    """Normalise an MCP CallToolResult into a Python dict."""
    if result.isError:
        message = _format_tool_content(result.content) or "Unknown MCP tool error"
        raise RuntimeError(message)

    if not result.content:
        return {}

    text_payload = _format_tool_content(result.content)
    if not text_payload:
        return {}

    try:
        return json.loads(text_payload)
    except json.JSONDecodeError:
        return {"output": text_payload}


class CreateBotAccountInput(BaseModel):
    user_id: str = Field(..., description="Bot userID to create (prefix must match OpenIM config).")
    nickname: str = Field(..., description="Nickname displayed to contacts in OpenIM clients.")
    face_url: str | None = Field(
        default=None,
        description="Optional avatar URL to assign to the bot profile.",
    )


class ImportFriendshipsInput(BaseModel):
    owner_user_id: str = Field(
        ...,
        description="UserID whose friend list should be updated (e.g., bot or human account).",
    )
    friend_ids: List[str] = Field(
        ...,
        description="List of userIDs to import as friends for the owner_user_id.",
    )


class WebSearchInput(BaseModel):
    query: str = Field(
        ...,
        description="Search query or question to execute against the SerpAPI web search backend.",
    )


class RagSearchInput(BaseModel):
    query: str = Field(
        ...,
        description="Search query or question to execute against the RAG store.",
    )


class PythonExecuteInput(BaseModel):
    code: str = Field(..., description="Python source code to execute inside the sandbox.")
    input: Optional[str] = Field(
        default=None,
        description="Optional raw user input forwarded to the interpreter.",
    )


class CreateAgentInput(BaseModel):
    bot_user_id: str = Field(..., description="Unique bot user ID (must match configured prefix).")
    name: str = Field(..., description="Internal agent name used in prompts and metadata.")
    nickname: str = Field(..., description="Nickname shown to users inside OpenIM.")
    api_base: AnyHttpUrl = Field(..., description="LLM API base URL.")
    api_key: str = Field(..., description="LLM API key or token.")
    model: str = Field(..., description="LLM model name.")
    system_prompt: str = Field(default="You are a helpful assistant.", description="System prompt for the agent.")
    memory_size: int = Field(default=10, ge=0, description="Conversation memory window size.")
    friends: List[str] = Field(default_factory=list, description="Initial friend user IDs.")
    redis_url: str | None = Field(default=None, description="Optional Redis URL override.")
    face_url: str | None = Field(default=None, description="Optional avatar URL.")
    allowed_tools: List[str] | None = Field(
        default=None,
        description="Subset of tool names the agent is allowed to call (defaults to all).",
    )
    enabled: bool = Field(default=True, description="Whether to enable the agent immediately.")


def build_agent_tools(
    client: OpenIMClient,
    settings: Settings | None = None,
    *,
    create_agent_fn: Optional[Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = None,
    mcp_server_url: Optional[str] = None,
) -> Dict[str, StructuredTool]:
    python_mcp_url = mcp_server_url or (settings.mcp_server_url if settings else None)

    @debug_tool_call("create_bot_account")
    def _create_bot_account_sync(
        user_id: str,
        nickname: str,
        face_url: str | None = None,
    ) -> Dict[str, Any]:
        """Synchronous version for langchain-classic AgentExecutor"""
        import asyncio
        import concurrent.futures

        async def _run():
            await client.create_bot_account(user_id=user_id, nickname=nickname, face_url=face_url)
            return {"status": "success", "user_id": user_id, "nickname": nickname}

        # Use a thread pool to run the async function to avoid event loop conflicts
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, _run())
            return future.result()

    async def _create_bot_account(
        user_id: str,
        nickname: str,
        face_url: str | None = None,
    ) -> Dict[str, Any]:
        """Async version for webhook handlers"""
        return await asyncio.to_thread(_create_bot_account_sync, user_id, nickname, face_url)

    @debug_tool_call("import_friendships")
    def _import_friendships_sync(
        owner_user_id: str,
        friend_ids: List[str],
    ) -> Dict[str, Any]:
        """Synchronous version for langchain-classic AgentExecutor"""
        import asyncio
        import concurrent.futures

        async def _run():
            await client.import_friendships(owner_user_id=owner_user_id, friend_ids=friend_ids)
            return {"status": "success", "owner_user_id": owner_user_id, "friend_ids": friend_ids}

        # Use a thread pool to run the async function to avoid event loop conflicts
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, _run())
            return future.result()

    async def _import_friendships(
        owner_user_id: str,
        friend_ids: List[str],
    ) -> Dict[str, Any]:
        """Async version for webhook handlers"""
        return await asyncio.to_thread(_import_friendships_sync, owner_user_id, friend_ids)

    @debug_tool_call("web_search")
    def _web_search_sync(query: str) -> Dict[str, Any]:
        """Synchronous version for langchain-classic AgentExecutor"""
        api_key = os.getenv("SERPAPI_API_KEY")
        if not api_key:
            raise RuntimeError("SERPAPI_API_KEY not configured")

        wrapper = SerpAPIWrapper(serpapi_api_key=api_key)
        result = wrapper.run(query)
        return {"status": "success", "query": query, "result": result}

    async def _web_search(query: str) -> Dict[str, Any]:
        """Async version for webhook handlers"""
        return await asyncio.to_thread(_web_search_sync, query)

    async def _python_execute_async_impl(code: str, input: Optional[str] = None) -> Dict[str, Any]:
        if not python_mcp_url:
            raise RuntimeError("MCP server URL not configured for python_execute tool.")

        arguments: Dict[str, Any] = {"code": code}
        if input is not None:
            arguments["input"] = input

        call_result = await _call_mcp_tool(
            python_mcp_url,
            "python_execute",
            arguments,
        )
        payload = _parse_mcp_call_result(call_result)
        return {"status": "success", **payload}

    @debug_tool_call("python_execute")
    def _python_execute_sync(code: str, input: Optional[str] = None) -> Dict[str, Any]:
        """Synchronous version for langchain-classic AgentExecutor"""
        return _run_async(_python_execute_async_impl(code, input))

    async def _python_execute(code: str, input: Optional[str] = None) -> Dict[str, Any]:
        """Async version for webhook handlers"""
        return await _python_execute_async_impl(code, input)

    @debug_tool_call("rag_search")
    def _rag_search_sync(query: str) -> Dict[str, Any]:
        """Synchronous version for langchain-classic AgentExecutor"""
        if not settings or not settings.rag_enabled:
            raise RuntimeError("RAG tool is not enabled in settings.")

        rag_store = RAGStore(
            persist_directory=settings.rag_persist_directory,
            embedding_model=settings.rag_embedding_model,
            embedding_api_key=settings.rag_embedding_api_key,
            embedding_api_base=settings.rag_embedding_api_base,
        )
        retriever = rag_store.as_retriever(k=settings.rag_top_k)
        docs = retriever.invoke(query)
        return {"status": "success", "query": query, "results": [doc.page_content for doc in docs]}

    async def _rag_search(query: str) -> Dict[str, Any]:
        """Async version for webhook handlers"""
        return await asyncio.to_thread(_rag_search_sync, query)

    tools: Dict[str, StructuredTool] = {
        "create_bot_account": StructuredTool.from_function(
            name="create_bot_account",
            description=(
                "Create a new bot account in OpenIM.\n"
                "Parameters:\n"
                "- user_id: Bot userID that must satisfy the configured bot prefix.\n"
                "- nickname: Nickname presented to other users.\n"
                "- face_url: Optional avatar URL."
            ),
            func=_create_bot_account_sync,
            args_schema=CreateBotAccountInput,
        ),
        "import_friendships": StructuredTool.from_function(
            name="import_friendships",
            description=(
                "Import friend relationships for a given OpenIM user.\n"
                "Parameters:\n"
                "- owner_user_id: User whose friend list is being updated.\n"
                "- friend_ids: One or more userIDs to add as friends."
            ),
            func=_import_friendships_sync,
            args_schema=ImportFriendshipsInput,
        ),
        "web_search": StructuredTool.from_function(
            name="web_search",
            description=(
                "Execute a web search using SerpAPI to retrieve up-to-date information.\n"
                "Parameters:\n"
                "- query: Natural language search query."
            ),
            func=_web_search_sync,
            args_schema=WebSearchInput,
        ),
    }

    if settings and settings.rag_enabled:
        tools["rag_search"] = StructuredTool.from_function(
            name="rag_search",
            description=(
                "Search the RAG (Retrieval-Augmented Generation) store for relevant documents.\n"
                "Parameters:\n"
                "- query: Natural language query to search the RAG store."
            ),
            func=_rag_search_sync,
            args_schema=RagSearchInput,
        )

    python_tool_enabled = settings is None or settings.enable_python_tool
    if python_tool_enabled and python_mcp_url:
        tools["python_execute"] = StructuredTool.from_function(
            name="python_execute",
            description=(
                "Execute Python code inside the MCP sandbox for quick calculations or scripting.\n"
                "Parameters:\n"
                "- code: Python source code to run.\n"
                "- input: Optional raw user input forwarded to the interpreter."
            ),
            func=_python_execute_sync,
            args_schema=PythonExecuteInput,
        )
    elif python_tool_enabled and not python_mcp_url:
        logger.warning("Python tool enabled but MCP server URL missing; tool not registered.")

    if create_agent_fn is not None:
        @debug_tool_call("create_agent")
        def _create_agent_sync(**payload: Any) -> Dict[str, Any]:
            """Synchronous version for langchain-classic AgentExecutor"""
            import asyncio
            import concurrent.futures

            # Use a thread pool to run the async function to avoid event loop conflicts
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, create_agent_fn(payload))
                return future.result()

        async def _create_agent_async(**payload: Any) -> Dict[str, Any]:
            """Async version for webhook handlers"""
            return await asyncio.to_thread(_create_agent_sync, **payload)

        tools["create_agent"] = StructuredTool.from_function(
            name="create_agent",
            description=(
                "Create a new agent via the gateway (equivalent to POST /agents). "
                "Provide bot_user_id, name, nickname, API credentials, allowed_tools, etc."
            ),
            func=_create_agent_sync,
            args_schema=CreateAgentInput,
        )

    return tools


__all__ = [
    "build_agent_tools",
    "CreateBotAccountInput",
    "ImportFriendshipsInput",
    "WebSearchInput",
    "RagSearchInput",
    "PythonExecuteInput",
    "CreateAgentInput",
]
