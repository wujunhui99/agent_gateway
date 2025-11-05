import uvicorn

from agent_gateway.config import load_settings
from agent_gateway.app import build_app


if __name__ == "__main__":
    settings = load_settings()
    app = build_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port)
