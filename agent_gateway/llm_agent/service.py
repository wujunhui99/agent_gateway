from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    trim_messages,
)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI


@dataclass
class LLMConfig:
    api_base: str
    api_key: str
    model: str
    system_prompt: str
    memory_size: int
    redis_url: Optional[str] = None
    tools: Optional[Sequence[StructuredTool]] = None
    tool_iteration_limit: int = 3
    retriever: Optional[BaseRetriever] = None


class LLMAgentService:
    """LangChain-based chat agent with optional RAG support."""

    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        self._client = ChatOpenAI(
            model=config.model,
            openai_api_key=config.api_key,
            openai_api_base=config.api_base,
        )

        runnable = self._build_runnable()
        self._agent_with_history = RunnableWithMessageHistory(
            runnable=runnable,
            get_session_history=self._get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
        )
        self._histories: Dict[str, RedisChatMessageHistory] = {}
        self._retriever = config.retriever

    def _build_runnable(self):
        if self._config.tools:
            prompt = ChatPromptTemplate.from_messages([
                ("system", "{system_prompt}"),
                MessagesPlaceholder(variable_name="chat_history"),
                ("system", "{context}"),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ])
            agent = create_tool_calling_agent(self._client, list(self._config.tools), prompt)
            verbose = os.getenv("AGENT_VERBOSE", "false").lower() == "true"
            return AgentExecutor(
                agent=agent,
                tools=list(self._config.tools),
                verbose=verbose,
                max_iterations=self._config.tool_iteration_limit,
            )

        prompt = ChatPromptTemplate.from_messages([
            ("system", "{system_prompt}"),
            MessagesPlaceholder(variable_name="chat_history"),
            ("system", "{context}"),
            ("human", "{input}"),
        ])
        return prompt | self._client

    def _get_session_history(self, session_id: str) -> RedisChatMessageHistory:
        if session_id not in self._histories:
            if not self._config.redis_url:
                raise RuntimeError("Redis URL not configured for LLM agent")
            self._histories[session_id] = RedisChatMessageHistory(
                url=self._config.redis_url,
                session_id=session_id,
            )
        return self._histories[session_id]

    def generate_reply(self, session_key: str, message: str) -> str:
        if not message:
            return ""

        context_block = self._build_context_block(message)

        try:
            result = self._agent_with_history.invoke(
                {
                    "input": message,
                    "system_prompt": self._config.system_prompt,
                    "context": context_block,
                },
                config={"configurable": {"session_id": session_key}},
            )
            self._trim_history_if_needed(session_key)
            return self._extract_output(result)
        except Exception as exc:  # noqa: BLE001
            logging.error("Failed to generate reply: %s", exc)
            raise

    def _trim_history_if_needed(self, session_key: str) -> None:
        if self._config.memory_size <= 0:
            self._get_session_history(session_key).clear()
            return

        history = self._get_session_history(session_key)
        messages = list(history.messages)
        max_messages = self._config.memory_size * 2

        if len(messages) > max_messages:
            try:
                trimmed = trim_messages(
                    messages=messages,
                    max_tokens=max_messages * 200,
                    strategy="last",
                    token_counter=lambda msgs: sum(len(str(m.content)) for m in msgs),
                )
                history.clear()
                for msg in trimmed:
                    history.add_message(msg)
                logging.info(
                    "Trimmed history for %s: %d -> %d messages",
                    session_key,
                    len(messages),
                    len(trimmed),
                )
            except Exception as exc:  # noqa: BLE001
                logging.warning("Failed to trim history: %s", exc)

    def _extract_output(self, result: Any) -> str:
        if isinstance(result, dict):
            return result.get("output", "").strip()
        if hasattr(result, "content"):
            return str(result.content).strip()
        return str(result).strip()

    def _build_context_block(self, message: str) -> str:
        if not self._retriever:
            return ""
        try:
            docs = self._retriever.get_relevant_documents(message)
        except Exception as exc:  # noqa: BLE001
            logging.warning("RAG retrieval failed: %s", exc)
            return ""
        if not docs:
            return ""

        snippets: List[str] = []
        for idx, doc in enumerate(docs, start=1):
            meta = doc.metadata or {}
            source = meta.get("source") or meta.get("file") or "knowledge"
            content = doc.page_content.strip()
            if len(content) > 500:
                content = content[:497] + "..."
            snippets.append(f"[{idx}] ({source}) {content}")
        return "Relevant knowledge:\n" + "\n\n".join(snippets)