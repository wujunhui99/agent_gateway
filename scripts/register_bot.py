"""Utility script to register an OpenIM bot user for the echo demo.

Usage:
    python scripts/register_bot.py --user-id bot_echo --nickname "Echo Bot"

The script loads agent_gateway settings (via .env) so make sure the
environment variables are in place before running.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid

import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


from agent_gateway.config import load_settings
from agent_gateway.openim import OpenIMClient
from agent_gateway.tools import build_agent_tools


def _build_headers(token: str | None = None) -> dict[str, str]:
    headers = {"Content-Type": "application/json", "operationID": uuid.uuid4().hex}
    if token:
        headers["token"] = token
    return headers


async def fetch_admin_token(client: httpx.AsyncClient, base: str, user_id: str, secret: str) -> str:
    resp = await client.post(
        f"{base}/auth/get_admin_token",
        json={"secret": secret, "userID": user_id},
        headers=_build_headers(),
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("errCode") != 0:
        raise RuntimeError(f"get_admin_token failed: {payload}")
    return payload["data"]["token"]


async def add_notification_account(
    client: httpx.AsyncClient,
    base: str,
    token: str,
    user_id: str,
    nickname: str,
    face_url: str | None = None,
) -> None:
    body: dict[str, object] = {
        "userID": user_id,
        "nickName": nickname,
        # OpenIM requires AppMangerLevel >= AppNotificationAdmin (3) for bot accounts
        "appMangerLevel": 3,
    }
    if face_url:
        body["faceURL"] = face_url
    resp = await client.post(
        f"{base}/user/add_notification_account",
        json=body,
        headers=_build_headers(token),
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("errCode") != 0:
        raise RuntimeError(f"add_notification_account failed: {payload}")


async def import_friendships(
    client: httpx.AsyncClient,
    base: str,
    token: str,
    owner: str,
    friend_ids: list[str],
) -> None:
    if not friend_ids:
        return
    resp = await client.post(
        f"{base}/friend/import_friend",
        json={"ownerUserID": owner, "friendUserIDs": friend_ids},
        headers=_build_headers(token),
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("errCode") != 0:
        raise RuntimeError(f"import_friend failed for {owner}: {payload}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Register an OpenIM bot user for the echo demo")
    parser.add_argument("--user-id", required=True, help="Bot user ID (should match prefix, e.g., bot_echo)")
    parser.add_argument("--name", default=None, help="Agent internal name (defaults to nickname if omitted)")
    parser.add_argument("--nickname", default="Echo Bot", help="Bot nickname")
    parser.add_argument("--face-url", default=None, help="Optional avatar URL")
    parser.add_argument(
        "--friend",
        action="append",
        default=[],
        help="Human userID to add as friend (can repeat)",
    )
    parser.add_argument(
        "--tool",
        action="append",
        dest="allowed_tools",
        default=None,
        help="Tool name to enable for this agent (can repeat). Defaults to all available tools if omitted.",
    )
    args = parser.parse_args()

    settings = load_settings()
    if settings.agent_user_prefix and not args.user_id.startswith(settings.agent_user_prefix):
        raise SystemExit(
            f"Bot user ID must start with prefix '{settings.agent_user_prefix}', got '{args.user_id}'"
        )

    agent_name = (args.name or args.nickname or args.user_id).strip()
    if not agent_name:
        raise SystemExit("Agent name cannot be empty")

    openim_client = OpenIMClient(settings)
    available_tool_names = sorted(build_agent_tools(openim_client, settings).keys())
    if args.allowed_tools:
        invalid = [name for name in args.allowed_tools if name not in available_tool_names]
        if invalid:
            await openim_client.close()
            raise SystemExit(
                f"Unsupported tool(s) {invalid}. Available tools: {', '.join(available_tool_names)}"
            )
        cleaned_tools = []
        for name in args.allowed_tools:
            if name not in cleaned_tools:
                cleaned_tools.append(name)
    else:
        cleaned_tools = available_tool_names

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            token = await fetch_admin_token(
                client,
                settings.api_base_str,
                settings.openim_admin_user_id,
                settings.openim_admin_secret,
            )
            try:
                await add_notification_account(
                    client,
                    settings.api_base_str,
                    token,
                    args.user_id,
                    args.nickname,
                    face_url=args.face_url,
                )
            except httpx.HTTPStatusError as exc:
                detail = exc.response.text
                raise SystemExit(f"Failed to add bot account: {detail}") from exc
            except RuntimeError as exc:
                raise SystemExit(str(exc)) from exc

            # optional friendships to bootstrap conversation
            for friend in args.friend:
                await import_friendships(client, settings.api_base_str, token, args.user_id, [friend])
                await import_friendships(client, settings.api_base_str, token, friend, [args.user_id])
    finally:
        await openim_client.close()

    summary = {
        "userID": args.user_id,
        "name": agent_name,
        "nickname": args.nickname,
        "friends": args.friend,
        "allowed_tools": cleaned_tools,
    }
    print("Bot setup complete:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
