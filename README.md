# Agent Gateway

Agent Gateway 是一个基于 FastAPI 构建的智能代理网关服务，旨在连接 OpenIM 即时通讯系统与大语言模型（LLM）。它充当了 OpenIM 和 AI Agent 之间的桥梁，赋予 IM 系统智能对话、知识库检索（RAG）和工具调用（MCP）的能力。

##  主要特性

*   **OpenIM 深度集成**：
    *   处理 OpenIM 的回调事件（单聊消息、群聊消息、好友申请）。
    *   自动回复用户消息，支持群聊中 @Bot 触发。
    *   自动接受好友请求。
*   **多 Agent 管理**：
    *   支持创建和管理多个具有不同角色、提示词（System Prompt）和能力的 Agent。
    *   Agent 配置持久化存储于 MongoDB。
*   **多 LLM 提供商支持**：
    *   通过环境变量灵活配置多个 LLM 提供商（如 OpenAI, Claude, DeepSeek 等）。
*   **RAG（检索增强生成）**：
    *   支持文档上传与向量化处理。
    *   基于 Qdrant 或本地存储的向量检索。
    *   让 Agent 能够基于私有知识库回答问题。
*   **工具与 MCP 支持**：
    *   集成 Model Context Protocol (MCP)，扩展 Agent 能力。
    *   支持 Python 代码执行等内置工具。
*   **记忆功能**：
    *   支持基于 Redis 或内存的会话上下文记忆。

## 🛠️ 技术栈

*   **Python 3.10+**
*   **FastAPI**: Web 框架
*   **LangChain**: LLM 应用开发框架
*   **MongoDB**: Agent 数据存储
*   **Redis**: 会话缓存（可选）
*   **Qdrant**: 向量数据库（RAG 用）
*   **OpenIM**: 即时通讯服务

## 🚀 快速开始

### 1. 环境准备

确保你已经安装了以下依赖服务：
*   OpenIM Server (https://github.com/openimsdk)
*   MongoDB
*   Redis
*   Qdrant

### 2. 安装依赖

```bash
cd agent_gateway
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

### 3. 配置文件 (.env)

在 `agent_gateway` 目录下创建 `.env` 文件，参照 `.env.example`（如果有）或以下配置：

```ini
# 服务监听配置
AGENT_GATEWAY_HOST=0.0.0.0
AGENT_GATEWAY_PORT=8081

# OpenIM 配置
AGENT_GATEWAY_OPENIM_API_BASE=http://your-openim-api-url
AGENT_GATEWAY_OPENIM_ADMIN_USER_ID=openIMAdminID
AGENT_GATEWAY_OPENIM_ADMIN_SECRET=openIMSecret
AGENT_GATEWAY_AGENT_USER_PREFIX=bot_

# 数据库配置
AGENT_GATEWAY_MONGO_URI=mongodb://localhost:27017
AGENT_GATEWAY_MONGO_DB=agent_gateway
AGENT_GATEWAY_MONGO_AGENT_COLLECTION=agents
AGENT_GATEWAY_REDIS_URL=redis://localhost:6379/0

# LLM 提供商配置 (示例: OpenAI)
# 格式: AGENT_GATEWAY_LLM_{PROVIDER_NAME}_API_BASE 和 AGENT_GATEWAY_LLM_{PROVIDER_NAME}_API_KEY
AGENT_GATEWAY_LLM_OPENAI_API_BASE=https://api.openai.com/v1
AGENT_GATEWAY_LLM_OPENAI_API_KEY=sk-your-api-key

# RAG (知识库) 配置
AGENT_GATEWAY_RAG_ENABLED=True
AGENT_GATEWAY_RAG_QDRANT_URL=http://localhost:6333
AGENT_GATEWAY_RAG_EMBEDDING_MODEL=text-embedding-3-large
AGENT_GATEWAY_RAG_EMBEDDING_DIMENSION=3072
AGENT_GATEWAY_RAG_TOP_K=4

# MCP 配置
AGENT_GATEWAY_MCP_URL=http://127.0.0.1:8065/sse
```

### 4. 启动服务

```bash
python main.py
```
或者使用 uvicorn 直接启动：
```bash
uvicorn agent_gateway.app:build_app --factory --host 0.0.0.0 --port 8081
```

### 5. OpenIM 回调配置

为了让 Agent Gateway 接收 OpenIM 的消息，你需要在 OpenIM 的配置文件（通常是 `config.yaml` 或通过 OpenIM Admin 后台）中配置回调地址：

*   **Callback URL**: `http://<your-gateway-ip>:8081/im_callback`
*   **启用回调**:
    *   `callbackAfterSendSingleMsgCommand` (单聊消息后回调)
    *   `callbackAfterSendGroupMsgCommand` (群聊消息后回调)
    *   `callbackAfterAddFriendCommand` (添加好友后回调)

## 📖 API 使用说明

### 创建 Agent

**POST** `/agents`

```json
{
  "bot_user_id": "bot_assistant",
  "name": "AI Assistant",
  "nickname": "小助手",
  "provider": "openai",
  "model": "gpt-4o",
  "system_prompt": "你是一个乐于助人的 AI 助手。",
  "enabled": true,
  "memory_size": 20
}
```

*   `bot_user_id`: 对应 OpenIM 中的 UserID（需以 `AGENT_GATEWAY_AGENT_USER_PREFIX` 开头，如 `bot_`）。
*   `provider`: 在 `.env` 中配置的 LLM 提供商名称（小写）。

### 上传知识库文档

**POST** `/documents/upload`

*   `file`: Multipart/form-data 文件上传。

支持 PDF 等格式，上传后 Agent 可通过 RAG 能力检索相关内容。

## 📂 目录结构

```
agent_gateway/
├── agent_gateway/
│   ├── app.py           # FastAPI 应用入口与路由
│   ├── config.py        # 配置加载与管理
│   ├── openim.py        # OpenIM API 客户端封装
│   ├── llm_agent/       # LLM Agent 核心逻辑
│   ├── rag/             # RAG (向量检索) 模块
│   ├── services/        # 业务逻辑服务
│   ├── tools/           # 工具集 (Python Tool, MCP)
│   └── templates/       # 简单的 HTML 模板
├── data/                # 数据目录
├── main.py              # 启动脚本
└── requirements.txt     # 项目依赖
```
