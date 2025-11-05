import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, List

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from pymongo import MongoClient
from pydantic import AnyHttpUrl, BaseModel, Field
from starlette.status import HTTP_400_BAD_REQUEST
from langchain_core.tools import StructuredTool

from .config import Settings, load_settings
from .openim import OpenIMClient
from .llm_agent import LLMConfig, LLMAgentService
from .services import create_agent_entry
from .tools import build_agent_tools
from .rag import RAGStore

TEXT_CONTENT_TYPES = {101, 106, 117}


class CommonCallbackFields(BaseModel):
    sendID: str
    callbackCommand: str
    contentType: int
    content: str
    sessionType: int | None = None
    ex: str | None = None
    seq: Optional[int] = None


class AfterSendSingleMsgRequest(CommonCallbackFields):
    recvID: str
    sendID: str


class AfterSendGroupMsgRequest(CommonCallbackFields):
    groupID: str
    atUserList: list[str] | None = None


class CallbackResponse(BaseModel):
    errCode: int = 0
    errMsg: str = ""
    errDlt: str = ""
    actionCode: int = 0


class CreateAgentRequest(BaseModel):
    bot_user_id: str
    name: str
    api_base: AnyHttpUrl
    api_key: str
    model: str
    system_prompt: str = "You are a helpful assistant."
    memory_size: int = Field(default=10, ge=0)
    enabled: bool = True
    nickname: str
    friends: list[str] = Field(default_factory=list)
    friend: str | None = None
    face_url: str | None = None
    redis_url: str | None = None
    allowed_tools: list[str] | None = None

    def resolve_friends(self) -> list[str]:
        raw: list[str] = []
        if self.friend:
            raw.append(self.friend)
        raw.extend(self.friends)
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in raw:
            value = item.strip()
            if not value or value in seen:
                continue
            seen.add(value)
            cleaned.append(value)
        return cleaned


class AfterAddFriendRequest(BaseModel):
    callbackCommand: str
    fromUserID: str
    toUserID: str
    reqMsg: str | None = None


def get_settings() -> Settings:
    return load_settings()


def build_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="Agent Gateway", version="0.1.0")
    client = OpenIMClient(settings)
    mongo_client = MongoClient(settings.mongo_uri)
    app.state.agent_tools = {}
    app.state.agent_services = {}

    rag_store: Optional[RAGStore] = None
    if settings.rag_enabled:
        embedding_key = settings.rag_embedding_api_key or os.getenv("OPENAI_API_KEY")
        rag_store = RAGStore(
            persist_directory=settings.rag_persist_directory,
            embedding_model=settings.rag_embedding_model,
            embedding_api_key=embedding_key,
            embedding_api_base=settings.rag_embedding_api_base,
            search_type=settings.rag_search_type,
            fetch_k=settings.rag_fetch_k,
            mmr_lambda=settings.rag_mmr_lambda,
        )
    app.state.rag_store = rag_store

    async def _create_agent(data: Dict[str, Any]) -> Dict[str, Any]:
        return await create_agent_entry(
            data,
            settings=settings,
            client=client,
            mongo_client=mongo_client,
            agent_services=app.state.agent_services,
            agent_tools=app.state.agent_tools,
            rag_store=app.state.rag_store,
        )

    agent_tools = build_agent_tools(
        client,
        settings,
        create_agent_fn=_create_agent,
        mcp_server_url=settings.mcp_server_url,
    )
    agent_services = _load_agent_services(mongo_client, settings, agent_tools, rag_store)
    print("agent services:", agent_services)
    app.state.mongo_client = mongo_client
    app.state.agent_services = agent_services
    app.state.agent_tools = agent_tools

    @app.post("/agents")
    async def create_agent(body: CreateAgentRequest) -> JSONResponse:
        payload = body.model_dump()
        payload["friends"] = body.resolve_friends()
        result = await create_agent_entry(
            payload,
            settings=settings,
            client=client,
            mongo_client=mongo_client,
            agent_services=app.state.agent_services,
            agent_tools=app.state.agent_tools,
            rag_store=app.state.rag_store,
        )
        return JSONResponse(content=result)

    @app.post("/documents/upload")
    async def upload_document(file: UploadFile = File(...)) -> JSONResponse:
        rag: Optional[RAGStore] = app.state.rag_store
        if rag is None:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="RAG module disabled")

        suffix = Path(file.filename).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            contents = await file.read()
            tmp.write(contents)
            temp_path = tmp.name

        try:
            result = await rag.add_file(temp_path, file.filename)
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass

        payload = {"filename": file.filename, **result}
        return JSONResponse(content=payload)

    @app.get("/agents/new", response_class=HTMLResponse)
    async def create_agent_form() -> HTMLResponse:
        """Render the agent creation form with available tools."""
        from pathlib import Path

        tool_names = sorted(app.state.agent_tools.keys())
        tools_markup = "\n".join(
            f'<label class="checkbox"><input type="checkbox" name="allowed_tools" value="{name}" checked /> {name}</label>'
            for name in tool_names
        ) or '<div class="hint">No tools available.</div>'

        # Load HTML template from file
        template_path = Path(__file__).parent / "templates" / "create_agent.html"
        html = template_path.read_text(encoding="utf-8")
        html = html.replace("{{TOOLS}}", tools_markup)

        return HTMLResponse(content=html)

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await client.close()
        app.state.agent_services.clear()
        mongo_client.close()

    @app.post("/im_callback/callbackAfterSendSingleMsgCommand")
    async def handle_single_message(body: AfterSendSingleMsgRequest) -> JSONResponse:
        # 打印 AfterSendSingleMsgRequest 的内容以便调试
        print("[DEBUG] Received AfterSendSingleMsgRequest:", body.json())
        print(f"[DEBUG] Single message received: sendID={body.sendID}, recvID={body.recvID}")
        print(f"[DEBUG] content: {body.content}")
        print(f"[DEBUG] contentType: {body.contentType}")

        if settings.agent_user_prefix and not body.recvID.startswith(settings.agent_user_prefix):
            return JSONResponse(content=CallbackResponse().dict())

        if body.contentType not in TEXT_CONTENT_TYPES:
            return JSONResponse(content=CallbackResponse().dict())

        text = _extract_text(body.content)
        if text is None:
            return JSONResponse(content=CallbackResponse().dict())

        if body.seq is not None:
            conversation_id = _build_single_conversation_id(body.sendID, body.recvID)
            try:
                await client.mark_message_as_read(body.recvID, conversation_id, body.seq)
            except Exception as exc:  # noqa: BLE001
                logging.warning("mark_message_as_read failed: %s", exc)

        service = app.state.agent_services.get(body.recvID)
        if service:
            session_key = f"{body.recvID}:{body.sendID}:p"
            try:
                reply = await asyncio.to_thread(service.generate_reply, session_key, text)
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

            if reply:
                try:
                    await client.send_text_reply(user_id=body.sendID, agent_id=body.recvID, content=reply)
                except Exception as exc:  # noqa: BLE001
                    raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
            return JSONResponse(content=CallbackResponse().dict())

        try:
            await client.send_text_reply(user_id=body.sendID, agent_id=body.recvID, content=text)
        except Exception as exc:  # noqa: BLE001
            print("[ERROR] send_text_reply failed:", exc)
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        return JSONResponse(content=CallbackResponse().dict())

    @app.post("/im_callback/callbackAfterSendGroupMsgCommand")
    async def handle_group_message(body: AfterSendGroupMsgRequest) -> JSONResponse:
        if settings.agent_user_prefix is None:
            return JSONResponse(content=CallbackResponse().dict())

        at_list = body.atUserList or []
        target_ids = [uid for uid in at_list if uid.startswith(settings.agent_user_prefix)]
        if not target_ids:
            return JSONResponse(content=CallbackResponse().dict())

        if body.contentType not in TEXT_CONTENT_TYPES:
            return JSONResponse(content=CallbackResponse().dict())

        extracted = _extract_text(body.content)
        if extracted is None:
            return JSONResponse(content=CallbackResponse().dict())

        async def send_group_message(bot_id: str, message: str) -> None:
            await client.send_group_text_reply(
                group_id=body.groupID,
                agent_id=bot_id,
                content=message,
            )

        tasks = []
        for bot_id in target_ids:
            text = extracted
            if body.atUserList:
                text = text.replace(f"@{bot_id}", "", 1).strip()
            if not text:
                continue

            service = app.state.agent_services.get(bot_id)
            if service:
                session_key = f"{bot_id}:{body.groupID}:g"
                try:
                    reply = await asyncio.to_thread(service.generate_reply, session_key, text)
                except Exception as exc:  # noqa: BLE001
                    raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
                if not reply:
                    continue
                tasks.append(send_group_message(bot_id, reply))
                continue

            tasks.append(send_group_message(bot_id, text))

        try:
            for task in tasks:
                await task
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        return JSONResponse(content=CallbackResponse().dict())

    @app.post("/im_callback/callbackAfterAddFriendCommand")
    async def handle_friend_request(body: AfterAddFriendRequest) -> JSONResponse:
        if settings.agent_user_prefix and not body.toUserID.startswith(settings.agent_user_prefix):
            return JSONResponse(content=CallbackResponse().dict())

        try:
            await client.accept_friend_request(from_user_id=body.fromUserID, to_user_id=body.toUserID)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        return JSONResponse(content=CallbackResponse().dict())

    return app


def _load_agent_services(
    mongo_client: MongoClient,
    settings: Settings,
    available_tools: Dict[str, StructuredTool],
    rag_store: Optional[RAGStore],
) -> Dict[str, LLMAgentService]:
    services: Dict[str, LLMAgentService] = {}
    db = mongo_client[settings.mongo_database]
    collection = db[settings.mongo_agent_collection]

    try:
        docs = collection.find({"enabled": {"$ne": False}})
    except Exception as exc:  # noqa: BLE001
        logging.error("Failed to load agents from MongoDB: %s", exc)
        return services

    for doc in docs:
        bot_user_id = doc.get("bot_user_id") or doc.get("botId") or doc.get("bot_userID")
        api_base = doc.get("api_base")
        api_key = doc.get("api_key")
        model = doc.get("model")
        if not bot_user_id or not api_base or not api_key or not model:
            logging.warning("Skip agent doc missing required fields: %s", doc)
            continue

        system_prompt = doc.get("system_prompt") or "You are a helpful assistant."
        memory_size = int(doc.get("memory_size", 10))
        redis_url = doc.get("redis_url") or settings.redis_url

        allowed_names = doc.get("allowed_tools")
        if isinstance(allowed_names, list):
            selected_tools: List[StructuredTool] = []
            for name in allowed_names:
                tool = available_tools.get(name)
                if tool:
                    selected_tools.append(tool)
                else:
                    logging.warning("Unknown tool '%s' referenced by agent %s", name, bot_user_id)
        else:
            selected_tools = list(available_tools.values())

        retriever = None
        if rag_store and settings.rag_enabled:
            try:
                retriever = rag_store.as_retriever(settings.rag_top_k)
            except Exception as exc:  # noqa: BLE001
                logging.warning("Failed to create retriever for %s: %s", bot_user_id, exc)

        config = LLMConfig(
            api_base=api_base,
            api_key=api_key,
            model=model,
            system_prompt=system_prompt,
            memory_size=memory_size,
            redis_url=redis_url,
            tools=selected_tools,
            retriever=retriever,
        )
        services[bot_user_id] = LLMAgentService(config)

    logging.info("Loaded %d agents from MongoDB", len(services))
    return services


def _extract_text(content: str) -> Optional[str]:
    try:
        payload: Dict[str, Any] = json.loads(content)
    except json.JSONDecodeError:
        return None
    value = payload.get("content") or payload.get("text")
    if isinstance(value, str):
        return value
    return None


def _build_single_conversation_id(user_a: str, user_b: str) -> str:
    ordered = sorted([user_a, user_b])
    return "si_" + "_".join(ordered)


settings = get_settings()
app = build_app(settings)
