from __future__ import annotations

import time
import uuid
from typing import Literal, Optional

from pydantic import BaseModel


class BaseEvent(BaseModel):
    event_type: str
    trace_id: str
    created_at: int


class MessageReceivedEvent(BaseEvent):
    event_type: Literal["message_received"] = "message_received"
    message_id: Optional[str] = None
    send_id: str
    recv_id: Optional[str] = None
    group_id: Optional[str] = None
    text: str
    content_type: int
    session_type: Optional[int] = None
    sender_nickname: Optional[str] = None
    sender_face_url: Optional[str] = None
    at_user_list: Optional[list[str]] = None
    is_group: bool
    seq: Optional[int] = None


class ReplyReadyEvent(BaseEvent):
    event_type: Literal["reply_ready"] = "reply_ready"
    reply_id: str
    target_type: Literal["single", "group"]
    agent_id: str
    to_user_id: Optional[str] = None
    group_id: Optional[str] = None
    content: str


def new_trace_id() -> str:
    return uuid.uuid4().hex


def new_reply_id() -> str:
    return uuid.uuid4().hex


def now_ts() -> int:
    return int(time.time())


__all__ = [
    "BaseEvent",
    "MessageReceivedEvent",
    "ReplyReadyEvent",
    "new_trace_id",
    "new_reply_id",
    "now_ts",
]
