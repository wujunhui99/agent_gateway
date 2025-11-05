# Agent Gateway MCP Python Interpreter

This module exposes a minimal MCP SSE server that runs Python code inside a
Docker sandbox. Each tool invocation launches `python:3.11-slim`, executes the
helper script located in `scripts/python_exec.py`, and returns stdout/stderr plus
any local variables produced by the code block.

## Layout

- `docker-compose.yml` – defines the sandbox container (`mcp-python-tool`).
- `scripts/` – helper scripts executed inside the container (currently `python_exec.py`).
- `tools/runner.py` – container entrypoint used by the MCP server to run scripts.
- `server.py` – FastAPI application compatible with the MCP SSE protocol.
- `servers/python_interpreter.py` – registers the `python_execute` tool.
- `executor.py` – shared helper to run sandbox commands from either MCP or LangChain tools.

## Running locally

```bash
cd agent_gateway/mcp
uvicorn agent_gateway.mcp.server:app --port 8070
```

Set `AGENT_GATEWAY_MCP_SERVER` to choose a different server module (future
expansion). By default the server exposes one tool:

- `agent-python-interpreter/python_execute`

### Direct Docker invocation

```bash
cd agent_gateway/mcp
./scripts/run_tool.sh python_exec.py '{"code": "print(1+1)"}'
```

The helper script simply proxies to the Docker container, mirroring how the MCP
server launches tools under the hood.

## Requirements

The agent gateway must install the `mcp` package alongside FastAPI when running
this server. See `agent_gateway/requirements.txt` for the dependency list.
