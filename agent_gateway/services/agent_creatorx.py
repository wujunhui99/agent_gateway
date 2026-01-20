from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from pymongo import MongoClient
from starlette.status import HTTP_400_BAD_REQUEST

from ..llm_agent import LLMConfig, LLMAgentService
from ..openim import OpenIMClient
from ..rag import RAGStore
from ..tools import CreateAgentInput
from ..config import Settings


async def create_agent_entry(
    payload: Dict[str, Any],
    *,
    settings: Settings,
    client: OpenIMClient,
    mongo_client: MongoClient,
    agent_services: Dict[str, LLMAgentService],
    agent_tools: Dict[str, Any],
    rag_store: Optional[RAGStore] = None,
) -> Dict[str, Any]:
    raw_friends = payload.get("friends") or []
    if isinstance(raw_friends, str):
        raw_friends = [raw_friends]

    payload_without_friends = {key: value for key, value in payload.items() if key != "friends"}
    request = CreateAgentInput(**payload_without_friends)

    if settings.agent_user_prefix and not request.bot_user_id.startswith(settings.agent_user_prefix):
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"bot_user_id must start with '{settings.agent_user_prefix}'",
        )
    if not request.nickname.strip():
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="nickname is required")
    if not request.name.strip():
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="name is required")

    # Get LLM provider configuration
    provider_config = settings.get_llm_provider(request.provider)
    if not provider_config:
        available_providers = list(settings.llm_providers.keys())
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"Unknown provider '{request.provider}'. Available providers: {available_providers}",
        )

    friend_ids = _clean_friends(raw_friends, request.bot_user_id)
    redis_url = request.redis_url or settings.redis_url
    if request.enabled and not redis_url:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="Redis URL is required when enabling the agent",
        )

    cleaned_tools = _validate_tools(request.allowed_tools, agent_tools)

    collection = mongo_client[settings.mongo_database][settings.mongo_agent_collection]
    existing = collection.find_one(
        {
            "$or": [
                {"bot_user_id": request.bot_user_id},
                {"bot_userID": request.bot_user_id},
                {"botId": request.bot_user_id},
            ]
        }
    )
    if existing:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Agent already exists")

    try:
        await client.create_bot_account(
            user_id=request.bot_user_id,
            nickname=request.nickname,
            face_url=request.face_url,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    for friend_id in friend_ids:
        try:
            await client.import_friendships(request.bot_user_id, [friend_id])
            await client.import_friendships(friend_id, [request.bot_user_id])
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    doc: Dict[str, Any] = {
        "bot_user_id": request.bot_user_id,
        "name": request.name,
        "nickname": request.nickname,
        "provider": request.provider,
        "model": request.model,
        "system_prompt": request.system_prompt,
        "memory_size": request.memory_size,
        "enabled": request.enabled,
        "friends": friend_ids,
        "redis_url": redis_url,
        "face_url": request.face_url,
        "allowed_tools": cleaned_tools,
    }

    doc = {key: value for key, value in doc.items() if value is not None}
    try:
        collection.insert_one(doc)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    service_registered = False
    if request.enabled:
        selected_tools = [agent_tools[name] for name in cleaned_tools]
        retriever = None
        if rag_store and settings.rag_enabled:
            retriever = rag_store.as_retriever(settings.rag_top_k)

        config = LLMConfig(
            agent_id=request.bot_user_id,
            agent_name=request.name,
            api_base=provider_config.api_base,
            api_key=provider_config.api_key,
            model=request.model,
            system_prompt=request.system_prompt,
            memory_size=request.memory_size,
            redis_url=redis_url,
            tools=selected_tools,
            retriever=retriever,
            agent_user_prefix=settings.agent_user_prefix,
        )
        service = LLMAgentService(config)
        agent_services[request.bot_user_id] = service
        service_registered = True

    response_payload: Dict[str, Any] = {
        "bot_user_id": request.bot_user_id,
        "name": request.name,
        "enabled": request.enabled,
        "friends": friend_ids,
        "allowed_tools": cleaned_tools,
    }
    if service_registered:
        response_payload["service_ready"] = True
    if redis_url:
        response_payload["redis_url"] = redis_url
    return response_payload


def _clean_friends(friends: List[str], bot_user_id: str) -> List[str]:
    cleaned: List[str] = []
    for friend in friends:
        value = friend.strip()
        if not value or value == bot_user_id:
            continue
        if value not in cleaned:
            cleaned.append(value)
    return cleaned


def _validate_tools(requested: List[str] | None, available: Dict[str, Any]) -> List[str]:
    available_names = set(available.keys())
    names = requested or list(available_names)
    cleaned: List[str] = []
    for name in names:
        value = name.strip()
        if not value:
            continue
        if value not in available_names:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=f"Unknown tool '{value}'. Available: {sorted(available_names)}",
            )
        if value not in cleaned:
            cleaned.append(value)
    return cleaned
