"""Entry point for running Agent Gateway MCP SSE servers."""

import os
from importlib import import_module

DEFAULT_SERVER = "python_interpreter"
ENV_KEY = "AGENT_GATEWAY_MCP_SERVER"


def load_server(name: str = DEFAULT_SERVER):
    module = import_module(f"agent_gateway.mcp.servers.{name}")
    if not hasattr(module, "build_server"):
        raise RuntimeError(f"Server module {name} does not expose build_server()")
    return module.build_server()


selected = os.getenv(ENV_KEY, DEFAULT_SERVER)
print(f"[Agent Gateway MCP] Loading server: {selected}")
mcp_server = load_server(selected)
print(f"[Agent Gateway MCP] Server loaded: {mcp_server}")
app = mcp_server.sse_app()


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("AGENT_GATEWAY_MCP_PORT", "8065"))
    uvicorn.run(app, host="0.0.0.0", port=port)
