import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

import httpx

from .config import Settings


class OpenIMClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http = httpx.AsyncClient(timeout=10.0)
        self._cached_token: Optional[str] = None
        self._token_expires_at: datetime = datetime.min
        self._profile_cache: dict[str, dict[str, str]] = {}

    async def close(self) -> None:
        await self._http.aclose()

    async def ensure_token(self) -> str:
        now = datetime.utcnow()
        if self._cached_token and now < self._token_expires_at:
            return self._cached_token
        payload = {
            "secret": self._settings.openim_admin_secret,
            "userID": self._settings.openim_admin_user_id,
        }
        headers = {"operationID": uuid.uuid4().hex}
        resp = await self._http.post(
            f"{self._settings.api_base_str}/auth/get_admin_token",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("errCode") != 0:
            raise RuntimeError(
                f"openIM get_admin_token failed: {data.get('errCode')} {data.get('errMsg')}"
            )
        token = data["data"]["token"]
        # token lifetime is 5 minutes, refresh slightly earlier
        self._cached_token = token
        self._token_expires_at = now + timedelta(minutes=4)
        return token

    async def send_text_reply(self, user_id: str, agent_id: str, content: str) -> None:
        token = await self.ensure_token()
        headers = {
            "operationID": uuid.uuid4().hex,
            "token": token,
        }
        profile = await self._get_user_profile(agent_id)
        payload = {
            "recvID": user_id,
            "sendID": agent_id,
            "content": {"content": content},
            "contentType": 101,
            "sessionType": 1,
            "senderNickname": profile.get("nickname"),
            "senderFaceURL": profile.get("faceURL"),
        }
        resp = await self._http.post(
            f"{self._settings.api_base_str}/msg/send_msg",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("errCode") != 0:
            raise RuntimeError(
                f"openIM send_msg failed: {data.get('errCode')} {data.get('errMsg')}"
            )

    async def mark_message_as_read(self, agent_id: str, conversation_id: str, seq: int) -> None:
        token = await self.ensure_token()
        headers = {
            "operationID": uuid.uuid4().hex,
            "token": token,
        }
        payload = {
            "conversationID": conversation_id,
            "seqs": [int(seq)],
            "userID": agent_id,
        }
        resp = await self._http.post(
            f"{self._settings.api_base_str}/msg/mark_msgs_as_read",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("errCode") != 0:
            raise RuntimeError(
                f"openIM mark_msgs_as_read failed: {data.get('errCode')} {data.get('errMsg')}"
            )

    async def create_bot_account(
        self,
        user_id: str,
        nickname: str,
        *,
        face_url: Optional[str] = None,
    ) -> None:
        token = await self.ensure_token()
        headers = {
            "operationID": uuid.uuid4().hex,
            "token": token,
        }
        payload: dict[str, object] = {
            "userID": user_id,
            "nickName": nickname,
            "appMangerLevel": 3,  # AppNotificationAdmin level required
        }
        if face_url:
            payload["faceURL"] = face_url

        resp = await self._http.post(
            f"{self._settings.api_base_str}/user/add_notification_account",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("errCode") != 0:
            err_code = data.get("errCode")
            if err_code == 1001 and await self._user_exists(user_id):
                logging.info("openIM account %s already exists, skipping creation", user_id)
            else:
                raise RuntimeError(
                    f"openIM add_notification_account failed: {data.get('errCode')} {data.get('errMsg')}"
                )
        else:
            self._profile_cache[user_id] = {"nickname": nickname, "faceURL": face_url or ""}

    async def import_friendships(self, owner_user_id: str, friend_ids: list[str]) -> None:
        if not friend_ids:
            return

        token = await self.ensure_token()
        headers = {
            "operationID": uuid.uuid4().hex,
            "token": token,
        }
        payload = {"ownerUserID": owner_user_id, "friendUserIDs": friend_ids}
        resp = await self._http.post(
            f"{self._settings.api_base_str}/friend/import_friend",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("errCode") != 0:
            raise RuntimeError(
                f"openIM import_friend failed: {data.get('errCode')} {data.get('errMsg')}"
            )

    async def _get_user_profile(self, user_id: str) -> dict[str, str]:
        cached = self._profile_cache.get(user_id)
        if cached:
            return cached

        token = await self.ensure_token()
        headers = {
            "operationID": uuid.uuid4().hex,
            "token": token,
        }
        resp = await self._http.post(
            f"{self._settings.api_base_str}/user/get_users_info",
            json={"userIDs": [user_id]},
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("errCode") != 0:
            raise RuntimeError(
                f"openIM get_users_info failed: {data.get('errCode')} {data.get('errMsg')}"
            )

        profile = {"nickname": user_id, "faceURL": ""}
        users_block = data.get("data") or {}
        candidates = []
        if isinstance(users_block, dict):
            for key in ("usersInfo", "userInfoList", "users"):
                value = users_block.get(key)
                if isinstance(value, list):
                    candidates = value
                    break
        elif isinstance(users_block, list):
            candidates = users_block

        for item in candidates:
            if isinstance(item, dict) and item.get("userID") == user_id:
                profile["nickname"] = item.get("nickname") or profile["nickname"]
                profile["faceURL"] = item.get("faceURL") or ""
                break

        self._profile_cache[user_id] = profile
        return profile

    async def _user_exists(self, user_id: str) -> bool:
        try:
            await self._get_user_profile(user_id)
            return True
        except RuntimeError:
            return False
