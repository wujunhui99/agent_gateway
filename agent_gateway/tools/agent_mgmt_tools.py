from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional

from langchain_core.tools import tool

from .async_utils import run_coro_sync
from .context import get_current_request_user
from .schemas import CreateAgentInput


def build_agent_mgmt_tools(
    create_agent_fn: Optional[Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]]
) -> Dict[str, Any]:
    if create_agent_fn is None:
        return {}

    @tool("create_agent", args_schema=CreateAgentInput)
    def create_agent(**payload: Any) -> Dict[str, Any]:
        """Create a new agent."""
        friends: list[str] = []
        current_user = get_current_request_user()
        if current_user:
            friends.append(current_user)

        payload_with_friends = {**payload, "friends": friends}
        return run_coro_sync(create_agent_fn(payload_with_friends))

    return {"create_agent": create_agent}
