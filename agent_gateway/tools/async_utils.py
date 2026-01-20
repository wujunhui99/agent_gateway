from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, TypeVar

_T = TypeVar("_T")
logger = logging.getLogger(__name__)


def run_coro_sync(coro: Awaitable[_T]) -> _T:
    """Run a coroutine from sync code with a dedicated loop."""
    # Always use a new event loop to avoid conflicts
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    except Exception as exc:
        logger.error("Error running coroutine: %s", exc, exc_info=True)
        raise
    finally:
        try:
            # Give a brief moment for cleanup tasks to complete naturally
            # This is important for MCP's SSE client which uses TaskGroup
            loop.run_until_complete(asyncio.sleep(0.05))

            # Cancel all remaining tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            # Run the loop briefly to let tasks clean up
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception as cleanup_exc:
            logger.debug("Error during loop cleanup: %s", cleanup_exc)
        finally:
            loop.close()
