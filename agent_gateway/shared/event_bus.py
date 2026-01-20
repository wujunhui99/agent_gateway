from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

import redis
from redis.exceptions import ResponseError

from .events import BaseEvent

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StreamMessage:
    message_id: str
    event_type: str
    payload: Dict[str, Any]


class RedisEventBus:
    def __init__(self, redis_url: str) -> None:
        if not redis_url:
            raise RuntimeError("REDIS_URL is required for event bus")
        self._client = redis.Redis.from_url(redis_url, decode_responses=True)

    def ensure_group(self, stream: str, group: str) -> None:
        try:
            self._client.xgroup_create(stream, group, id="0-0", mkstream=True)
            logger.info("Created consumer group '%s' on stream '%s'", group, stream)
        except ResponseError as exc:
            if "BUSYGROUP" in str(exc):
                return
            raise

    def publish(self, stream: str, event: BaseEvent) -> str:
        payload = event.model_dump()
        event_type = payload.pop("event_type")
        data = {
            "type": event_type,
            "payload": json.dumps(payload, ensure_ascii=True),
        }
        return self._client.xadd(stream, data)

    def read_group(
        self,
        stream: str,
        group: str,
        consumer: str,
        *,
        count: int = 10,
        block_ms: int = 2000,
    ) -> List[StreamMessage]:
        raw = self._client.xreadgroup(
            group,
            consumer,
            {stream: ">"},
            count=count,
            block=block_ms,
        )
        return self._decode_messages(raw)

    def ack(self, stream: str, group: str, message_id: str) -> None:
        self._client.xack(stream, group, message_id)

    @staticmethod
    def _decode_messages(raw: Iterable[Any]) -> List[StreamMessage]:
        messages: List[StreamMessage] = []
        for _stream, entries in raw:
            for message_id, fields in entries:
                event_type = fields.get("type", "")
                payload_raw = fields.get("payload", "{}")
                try:
                    payload = json.loads(payload_raw)
                except json.JSONDecodeError:
                    payload = {}
                messages.append(StreamMessage(message_id, event_type, payload))
        return messages


__all__ = ["RedisEventBus", "StreamMessage"]
