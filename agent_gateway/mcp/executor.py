from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict

BASE_DIR = Path(__file__).resolve().parent
COMPOSE_FILE = BASE_DIR / "docker-compose.yml"
RUN_SCRIPT = BASE_DIR / "scripts" / "run_tool.sh"
SCRIPT_NAME = "python_exec.py"

logger = logging.getLogger(__name__)


def run_python_sandbox(code: str, user_input: str | None = None) -> Dict[str, Any]:
    """Synchronous function to run Python code in sandbox using docker compose exec"""
    if not COMPOSE_FILE.exists():
        raise RuntimeError("Sandbox runtime is not configured (missing docker-compose.yml)")

    if not RUN_SCRIPT.exists():
        raise RuntimeError(f"Run script not found: {RUN_SCRIPT}")

    payload = {"code": code}
    if user_input:
        payload["input"] = user_input
    payload_json = json.dumps(payload, ensure_ascii=False)

    # Use the run_tool.sh script which handles docker compose exec
    cmd = [str(RUN_SCRIPT), SCRIPT_NAME, payload_json]

    logger.debug("Executing MCP command: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            cwd=str(BASE_DIR),
            check=True,
            capture_output=True,
            text=True,
            timeout=30,  # 30 second timeout
        )
    except subprocess.CalledProcessError as exc:
        logger.error("Docker execution failed: %s", exc.stderr)
        raise RuntimeError(f"Python execution failed: {exc.stderr}") from exc
    except subprocess.TimeoutExpired as exc:
        logger.error("Docker execution timeout")
        raise RuntimeError("Python execution timeout") from exc

    stdout_text = result.stdout.strip()
    stderr_text = result.stderr.strip()

    try:
        parsed: Dict[str, Any] = json.loads(stdout_text) if stdout_text else {}
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON from interpreter: %s", stdout_text)
        raise RuntimeError(f"Interpreter returned invalid JSON: {exc}") from exc

    if stderr_text:
        parsed["stderr"] = stderr_text
    parsed["exit_code"] = result.returncode

    return parsed


__all__ = ["run_python_sandbox"]
