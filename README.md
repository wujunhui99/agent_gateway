# Agent Gateway (Echo Demo)

Minimal webhook service that connects OpenIM callbacks to agent behaviour. The current demo listens for `afterSendSingleMsg` callbacks and sends an echo response back to the sender using OpenIM's `/msg/send_simple_msg` API.

## Features

- FastAPI application with a single callback endpoint.
- Admin-token management for OpenIM REST API calls.
- Base64 key generation compatible with OpenIM's `send_simple_msg` helper.
- Configurable agent user prefix to scope callbacks (defaults to `bot_`).

## Quick Start

1. **Install dependencies**

   ```bash
   cd agent_gateway
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Export configuration**

   ```bash
   export AGENT_GATEWAY_OPENIM_API_BASE="http://127.0.0.1:10002"  # OpenIM API host:port
   export AGENT_GATEWAY_OPENIM_ADMIN_USER_ID="openIMAdmin"       # matches config.share.imAdminUser.userIDs[0]
   export AGENT_GATEWAY_OPENIM_ADMIN_SECRET="openIMAdminSecret"  # matches config.share.imAdminUser.secrets[0]
   export AGENT_GATEWAY_PORT=8081
   export AGENT_GATEWAY_AGENT_USER_PREFIX="bot_"
   export AGENT_GATEWAY_REDIS_URL="redis://127.0.0.1:6379/0"
   export AGENT_GATEWAY_MONGO_URI="mongodb://127.0.0.1:27017"
   export AGENT_GATEWAY_MONGO_DB="agent_gateway"
   export AGENT_GATEWAY_MONGO_AGENT_COLLECTION="agents"
   ```

   You can place the same keys inside an `.env` file for local development.

3. **Run the gateway**

   ```bash
   uvicorn agent_gateway.app:app --host 0.0.0.0 --port ${AGENT_GATEWAY_PORT:-8081}
   # or
   python -m agent_gateway.main
   ```

4. **Configure OpenIM webhook**

   Update `open-im-server/config/webhooks.yml` (or the active deployment config) so that `afterSendSingleMsg` points to the gateway:

   ```yaml
   url: http://127.0.0.1:8081/im_callback
   afterSendSingleMsg:
     enable: true
     timeout: 5
   afterSendGroupMsg:
     enable: true
     timeout: 5
   afterAddFriend:
     enable: true
     timeout: 5
   ```

   OpenIM automatically appends the callback command to the base URL, so the service receives POST requests at `/im_callback/callbackAfterSendSingleMsgCommand`.
   `afterSendGroupMsg` handles `@bot_xxx` mentions in groups, `afterAddFriend` is used to automatically approve friend requests directed at bot accounts.

5. **Create an agent account**

   Use the helper script (loads `.env`) so the bot ID automatically matches the configured prefix:

   ```bash
   cd agent_gateway
   python scripts/register_bot.py --user-id bot_echo --nickname "Echo Bot" --friend alice
   ```

   这会：

   - 获取管理员 token 并调用 `/user/add_notification_account` 注册 `bot_echo`。
   - 可选地把 `alice` 与机器人互相导入好友（`--friend` 参数可重复）。

   注册完成后，用普通用户给 `bot_echo` 发私聊消息即可观察到回声；若在群聊中 `@bot_echo`，只会回声提及后的文本；如果普通用户主动申请加好友，网关会自动代表机器人同意申请。

6. **新增模型代理**

   1. 在 MongoDB 中插入一条配置记录（默认集合 `agents`）：
      ```json
      {
        "bot_user_id": "bot_agent_qwen",
        "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "sk-***",
        "model": "qwen-plus",
        "system_prompt": "You are Qwen, a helpful assistant.",
        "memory_size": 10,
        "enabled": true
      }
      ```
   2. 使用脚本注册对应的机器人账号：
      ```bash
      python scripts/register_bot.py --user-id bot_agent_qwen --nickname "Qwen Agent" --friend alice
      ```
   3. 网关会在启动时读取 Mongo 配置并创建模型实例；无需改代码即可再新增 DeepSeek、Kimi 等多种模型，只要写入新文档并注册对应的 bot。

## Response Flow

1. User sends a single chat text message to the bot account.
2. OpenIM triggers the `afterSendSingleMsg` webhook.
3. The gateway extracts the text payload and calls `/msg/send_simple_msg` using the OpenIM admin token.
4. OpenIM delivers the echoed content back to the original sender.

## Notes

- Only `contentType` values corresponding to plain text are echoed. Other message types are ignored gracefully.
- Errors from OpenIM propagation return HTTP 400 to the webhook; OpenIM follows its retry strategy.
- The gateway caches the admin token for 4 minutes (OpenIM tokens are valid for 5 minutes by default).
