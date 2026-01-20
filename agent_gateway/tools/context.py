from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

_current_request_user: ContextVar[str | None] = ContextVar("current_request_user", default=None)


def set_current_request_user(user_id: str | None):
    """Store the user who is driving the current agent interaction."""
    return _current_request_user.set(user_id)


def reset_current_request_user(token) -> None:
    _current_request_user.reset(token)


def get_current_request_user() -> Optional[str]:
    return _current_request_user.get()
