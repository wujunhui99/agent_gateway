import os
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv
from pydantic import AnyHttpUrl, BaseModel, Field, ValidationError

load_dotenv()


class Settings(BaseModel):
    host: str = Field(default="0.0.0.0", alias="AGENT_GATEWAY_HOST")
    port: int = Field(default=8081, alias="AGENT_GATEWAY_PORT")
    openim_api_base: AnyHttpUrl = Field(alias="AGENT_GATEWAY_OPENIM_API_BASE")
    openim_admin_user_id: str = Field(alias="AGENT_GATEWAY_OPENIM_ADMIN_USER_ID")
    openim_admin_secret: str = Field(alias="AGENT_GATEWAY_OPENIM_ADMIN_SECRET")
    agent_user_prefix: str = Field(default="bot_", alias="AGENT_GATEWAY_AGENT_USER_PREFIX")
    redis_url: Optional[str] = Field(default=None, alias="AGENT_GATEWAY_REDIS_URL")
    mongo_uri: str = Field(alias="AGENT_GATEWAY_MONGO_URI")
    mongo_database: str = Field(default="agent_gateway", alias="AGENT_GATEWAY_MONGO_DB")
    mongo_agent_collection: str = Field(default="agents", alias="AGENT_GATEWAY_MONGO_AGENT_COLLECTION")
    enable_python_tool: bool = Field(default=True, alias="AGENT_GATEWAY_ENABLE_PYTHON_TOOL")
    rag_enabled: bool = Field(default=True, alias="AGENT_GATEWAY_RAG_ENABLED")
    rag_persist_directory: str = Field(default="data/rag_store", alias="AGENT_GATEWAY_RAG_PERSIST_DIR")
    rag_embedding_model: str = Field(default="text-embedding-3-large", alias="AGENT_GATEWAY_RAG_EMBEDDING_MODEL")
    rag_embedding_api_key: Optional[str] = Field(default=None, alias="AGENT_GATEWAY_RAG_EMBEDDING_API_KEY")
    rag_embedding_api_base: Optional[str] = Field(default=None, alias="AGENT_GATEWAY_RAG_EMBEDDING_API_BASE")
    rag_top_k: int = Field(default=4, alias="AGENT_GATEWAY_RAG_TOP_K")
    rag_search_type: str = Field(default="mmr", alias="AGENT_GATEWAY_RAG_SEARCH_TYPE")
    rag_fetch_k: Optional[int] = Field(default=None, alias="AGENT_GATEWAY_RAG_FETCH_K")
    rag_mmr_lambda: Optional[float] = Field(default=0.5, alias="AGENT_GATEWAY_RAG_MMR_LAMBDA")
    mcp_server_url: str = Field(default="http://127.0.0.1:8070/sse", alias="AGENT_GATEWAY_MCP_URL")

    class Config:
        validate_by_name = True

    @property
    def api_base_str(self) -> str:
        return str(self.openim_api_base).rstrip("/")


ENV_KEYS = (
    "AGENT_GATEWAY_HOST",
    "AGENT_GATEWAY_PORT",
    "AGENT_GATEWAY_OPENIM_API_BASE",
    "AGENT_GATEWAY_OPENIM_ADMIN_USER_ID",
    "AGENT_GATEWAY_OPENIM_ADMIN_SECRET",
    "AGENT_GATEWAY_AGENT_USER_PREFIX",
    "AGENT_GATEWAY_REDIS_URL",
    "AGENT_GATEWAY_MONGO_URI",
    "AGENT_GATEWAY_MONGO_DB",
    "AGENT_GATEWAY_MONGO_AGENT_COLLECTION",
    "AGENT_GATEWAY_ENABLE_PYTHON_TOOL",
    "AGENT_GATEWAY_RAG_ENABLED",
    "AGENT_GATEWAY_RAG_PERSIST_DIR",
    "AGENT_GATEWAY_RAG_EMBEDDING_MODEL",
    "AGENT_GATEWAY_RAG_EMBEDDING_API_KEY",
    "AGENT_GATEWAY_RAG_EMBEDDING_API_BASE",
    "AGENT_GATEWAY_RAG_TOP_K",
    "AGENT_GATEWAY_RAG_SEARCH_TYPE",
    "AGENT_GATEWAY_RAG_FETCH_K",
    "AGENT_GATEWAY_RAG_MMR_LAMBDA",
    "AGENT_GATEWAY_MCP_URL",
)


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    env_values = {key: os.getenv(key) for key in ENV_KEYS}
    try:
        return Settings(**env_values)
    except ValidationError as exc:
        missing = [
            " ".join(map(str, err.get("loc", [])))
            for err in exc.errors()
            if err.get("type") == "missing"
        ]
        detail = ", ".join(filter(None, missing)) or str(exc)
        raise RuntimeError(f"agent-gateway settings invalid: {detail}") from exc


__all__ = ["Settings", "load_settings"]
