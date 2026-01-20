from __future__ import annotations

from typing import Any, Dict, List

from langchain_core.tools import tool

from .async_utils import run_coro_sync
from .schemas import CreateBotAccountInput, ImportFriendshipsInput
from ..openim import OpenIMClient


def build_openim_tools(client: OpenIMClient) -> Dict[str, Any]:
    @tool("create_bot_account", args_schema=CreateBotAccountInput)
    def create_bot_account(user_id: str, nickname: str, face_url: str | None = None) -> Dict[str, Any]:
        """Create an OpenIM bot account with optional avatar."""
        run_coro_sync(client.create_bot_account(user_id=user_id, nickname=nickname, face_url=face_url))
        return {"status": "success", "user_id": user_id, "nickname": nickname}

    @tool("import_friendships", args_schema=ImportFriendshipsInput)
    def import_friendships(owner_user_id: str, friend_ids: List[str]) -> Dict[str, Any]:
        """Import friendship relations for a user and the provided friends."""
        run_coro_sync(client.import_friendships(owner_user_id=owner_user_id, friend_ids=friend_ids))
        return {"status": "success", "owner_user_id": owner_user_id, "friend_ids": friend_ids}

    return {
        "create_bot_account": create_bot_account,
        "import_friendships": import_friendships,
    }
