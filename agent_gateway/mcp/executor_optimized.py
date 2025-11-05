"""Optimized Python sandbox executor with persistent process.

Key improvements:
1. Maintains a persistent Python process in Docker container
2. Reuses the same process for multiple executions
3. Communicates via stdin/stdout pipe
4. Avoids repeated subprocess creation and docker exec overhead
"""

from __future__ import annotations

import atexit
import json
import logging
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, Optional

BASE_DIR = Path(__file__).resolve().parent
COMPOSE_FILE = BASE_DIR / "docker-compose.yml"

logger = logging.getLogger(__name__)


class PersistentPythonExecutor:
    """Manages a persistent Python process in Docker container."""

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._initialized = False

    def _start_process(self):
        """Start the persistent Python process."""
        if not COMPOSE_FILE.exists():
            raise RuntimeError("Docker compose file not found")

        # Start a persistent Python process that reads from stdin
        cmd = [
            "docker", "compose", "-f", str(COMPOSE_FILE),
            "exec", "-T", "mcp-python-tool",
            "python", "-u", "-c",
            """
import json
import sys
import traceback
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO

def run_code(code: str) -> dict:
    stdout_buffer = StringIO()
    stderr_buffer = StringIO()
    local_vars = {}
    try:
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            exec(code, {}, local_vars)
        return {
            "stdout": stdout_buffer.getvalue().strip(),
            "stderr": stderr_buffer.getvalue().strip(),
            "locals": {k: str(v) for k, v in local_vars.items()},
        }
    except Exception as exc:
        return {
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "stdout": stdout_buffer.getvalue().strip(),
            "stderr": stderr_buffer.getvalue().strip(),
        }

# Ready signal
print("READY", flush=True)

# Main loop: read requests from stdin, execute, write results to stdout
while True:
    try:
        line = sys.stdin.readline()
        if not line:
            break

        request = json.loads(line)
        code = request.get("code", "")

        if not code:
            result = {"error": "No code provided"}
        else:
            result = run_code(code)

        # Send result as single line JSON
        print(json.dumps(result, default=str, ensure_ascii=False), flush=True)

    except Exception as e:
        error_result = {"error": str(e), "traceback": traceback.format_exc()}
        print(json.dumps(error_result), flush=True)
"""
        ]

        logger.info("Starting persistent Python process...")
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
            cwd=str(BASE_DIR),
        )

        # Wait for READY signal
        ready_line = self._process.stdout.readline().strip()
        if ready_line != "READY":
            stderr = self._process.stderr.read()
            raise RuntimeError(f"Failed to start process. Got: {ready_line}, stderr: {stderr}")

        logger.info("Persistent Python process started successfully")
        self._initialized = True

        # Register cleanup
        atexit.register(self.cleanup)

    def cleanup(self):
        """Clean up the persistent process."""
        if self._process and self._process.poll() is None:
            logger.info("Shutting down persistent Python process...")
            try:
                self._process.stdin.close()
                self._process.wait(timeout=5)
            except Exception as e:
                logger.warning(f"Error during cleanup: {e}")
                self._process.kill()

    def execute(self, code: str, user_input: Optional[str] = None) -> Dict[str, Any]:
        """Execute Python code in the persistent process."""
        with self._lock:
            # Initialize on first use
            if not self._initialized:
                self._start_process()

            # Check if process is still alive
            if self._process.poll() is not None:
                logger.warning("Process died, restarting...")
                self._initialized = False
                self._start_process()

            # Send request
            request = {"code": code}
            if user_input:
                request["input"] = user_input

            request_line = json.dumps(request, ensure_ascii=False) + "\n"

            try:
                self._process.stdin.write(request_line)
                self._process.stdin.flush()

                # Read response
                response_line = self._process.stdout.readline()
                if not response_line:
                    raise RuntimeError("Process closed unexpectedly")

                result = json.loads(response_line)
                result["exit_code"] = 0
                return result

            except Exception as e:
                logger.error(f"Execution error: {e}")
                # Try to restart process
                self._initialized = False
                raise RuntimeError(f"Execution failed: {e}") from e


# Global executor instance
_executor = PersistentPythonExecutor()


def run_python_sandbox_optimized(code: str, user_input: str | None = None) -> Dict[str, Any]:
    """
    Optimized version using persistent Python process.

    Drop-in replacement for run_python_sandbox from executor.py
    """
    return _executor.execute(code, user_input)


def cleanup_executor():
    """Cleanup function to be called on shutdown."""
    _executor.cleanup()


__all__ = ["run_python_sandbox_optimized", "cleanup_executor"]
