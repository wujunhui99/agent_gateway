"""Isolated Python sandbox executor with state reset.

Improvements over executor_optimized.py:
1. Resets global state after each execution
2. Periodic process restart to prevent state accumulation
3. Better memory management
4. Configurable isolation level
"""

from __future__ import annotations

import atexit
import gc
import json
import logging
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Dict, Optional

BASE_DIR = Path(__file__).resolve().parent
COMPOSE_FILE = BASE_DIR / "docker-compose.yml"

logger = logging.getLogger(__name__)


class IsolatedPythonExecutor:
    """Manages an isolated persistent Python process with state reset."""

    def __init__(
        self,
        max_executions: int = 1000,
        cleanup_modules: bool = False,
        force_gc_interval: int = 100,
    ):
        """
        Args:
            max_executions: 多少次执行后重启进程（防止状态累积）
            cleanup_modules: 是否清理新导入的模块（会影响性能）
            force_gc_interval: 多少次执行后强制垃圾回收
        """
        self._process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._initialized = False
        self._execution_count = 0
        self._max_executions = max_executions
        self._cleanup_modules = cleanup_modules
        self._force_gc_interval = force_gc_interval

    def _start_process(self):
        """Start the persistent Python process with state reset support."""
        if not COMPOSE_FILE.exists():
            raise RuntimeError("Docker compose file not found")

        # Python 代码：包含状态重置逻辑
        python_code = """
import json
import sys
import traceback
import gc
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO

def run_code_with_reset(code: str, cleanup_modules: bool) -> dict:
    '''Execute code with optional state reset.'''

    # 保存原始状态
    if cleanup_modules:
        original_modules = set(sys.modules.keys())
    original_path_len = len(sys.path)

    stdout_buffer = StringIO()
    stderr_buffer = StringIO()
    local_vars = {}

    try:
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            # 使用空的 globals，每次新的 locals
            exec(code, {}, local_vars)

        result = {
            "stdout": stdout_buffer.getvalue().strip(),
            "stderr": stderr_buffer.getvalue().strip(),
            "locals": {k: str(v) for k, v in local_vars.items()},
        }

    except Exception as exc:
        result = {
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "stdout": stdout_buffer.getvalue().strip(),
            "stderr": stderr_buffer.getvalue().strip(),
        }

    finally:
        # 清理全局状态
        # 1. 清理新导入的模块（可选）
        if cleanup_modules:
            for mod in list(sys.modules.keys()):
                if mod not in original_modules and not mod.startswith('_'):
                    try:
                        del sys.modules[mod]
                    except:
                        pass  # 某些模块不能删除

        # 2. 恢复 sys.path（如果被修改）
        while len(sys.path) > original_path_len:
            sys.path.pop()

    return result

# Ready signal
print("READY", flush=True)

# Main loop
while True:
    try:
        line = sys.stdin.readline()
        if not line:
            break

        request = json.loads(line)
        code = request.get("code", "")
        cleanup = request.get("cleanup_modules", False)

        if not code:
            result = {"error": "No code provided"}
        else:
            result = run_code_with_reset(code, cleanup)

        # Send result as single line JSON
        print(json.dumps(result, default=str, ensure_ascii=False), flush=True)

    except Exception as e:
        error_result = {"error": str(e), "traceback": traceback.format_exc()}
        print(json.dumps(error_result), flush=True)
"""

        cmd = [
            "docker", "compose", "-f", str(COMPOSE_FILE),
            "exec", "-T", "mcp-python-tool",
            "python", "-u", "-c", python_code
        ]

        logger.info("Starting isolated Python process...")
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=str(BASE_DIR),
        )

        # Wait for READY signal
        ready_line = self._process.stdout.readline().strip()
        if ready_line != "READY":
            stderr = self._process.stderr.read()
            raise RuntimeError(f"Failed to start process. stderr: {stderr}")

        logger.info("Isolated Python process started successfully")
        self._initialized = True
        self._execution_count = 0

        atexit.register(self.cleanup)

    def _restart_process(self):
        """Restart the process to clear all state."""
        logger.info(f"Restarting process after {self._execution_count} executions")
        self.cleanup()
        self._initialized = False
        self._start_process()

    def cleanup(self):
        """Clean up the persistent process."""
        if self._process and self._process.poll() is None:
            logger.info("Shutting down isolated Python process...")
            try:
                self._process.stdin.close()
                self._process.wait(timeout=5)
            except Exception as e:
                logger.warning(f"Error during cleanup: {e}")
                self._process.kill()

    def execute(self, code: str, user_input: Optional[str] = None) -> Dict[str, Any]:
        """Execute Python code with state isolation."""
        with self._lock:
            # Initialize on first use
            if not self._initialized:
                self._start_process()

            # Check execution count and restart if needed
            if self._execution_count >= self._max_executions:
                self._restart_process()

            # Check if process is still alive
            if self._process.poll() is not None:
                logger.warning("Process died, restarting...")
                self._initialized = False
                self._start_process()

            # Increment execution counter
            self._execution_count += 1

            # Force garbage collection periodically
            if self._execution_count % self._force_gc_interval == 0:
                gc.collect()

            # Send request
            request = {
                "code": code,
                "cleanup_modules": self._cleanup_modules,
            }
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
                result["execution_count"] = self._execution_count
                return result

            except Exception as e:
                logger.error(f"Execution error: {e}")
                self._initialized = False
                raise RuntimeError(f"Execution failed: {e}") from e

    def get_stats(self) -> Dict[str, Any]:
        """Get executor statistics."""
        return {
            "execution_count": self._execution_count,
            "max_executions": self._max_executions,
            "cleanup_modules": self._cleanup_modules,
            "process_alive": self._process is not None and self._process.poll() is None,
        }


# Global executor instance
_executor = IsolatedPythonExecutor(
    max_executions=1000,      # 每1000次执行后重启
    cleanup_modules=False,    # 不清理模块（保持性能）
    force_gc_interval=100,    # 每100次执行强制GC
)


def run_python_sandbox_isolated(code: str, user_input: str | None = None) -> Dict[str, Any]:
    """
    Isolated version with state reset.

    Drop-in replacement for run_python_sandbox from executor.py
    """
    return _executor.execute(code, user_input)


def cleanup_executor():
    """Cleanup function to be called on shutdown."""
    _executor.cleanup()


def get_executor_stats() -> Dict[str, Any]:
    """Get statistics about the executor."""
    return _executor.get_stats()


__all__ = ["run_python_sandbox_isolated", "cleanup_executor", "get_executor_stats"]
