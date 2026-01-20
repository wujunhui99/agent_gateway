from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


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
    provider: str = Field(..., description="LLM provider name (e.g., 'aliyun', 'siliconflow').")
    model: str = Field(..., description="LLM model name.")
    system_prompt: str = Field(default="You are a helpful assistant.", description="System prompt for the agent.")
    memory_size: int = Field(default=10, ge=0, description="Conversation memory window size.")
    redis_url: str | None = Field(default=None, description="Optional Redis URL override.")
    face_url: str | None = Field(default=None, description="Optional avatar URL.")
    allowed_tools: List[str] | None = Field(
        default=None,
        description="Subset of tool names the agent is allowed to call (defaults to all).",
    )
    enabled: bool = Field(default=True, description="Whether to enable the agent immediately.")
