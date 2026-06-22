"""Lifecycle helper for CLI commands that need Tortoise ORM."""

import asyncio
from collections.abc import Coroutine
from typing import Any

from tortoise import Tortoise

from vapi.lib.database import init_tortoise


def run_with_tortoise(coro: Coroutine[Any, Any, None]) -> None:
    """Run an async CLI command body with Tortoise initialized then torn down.

    Initialize Tortoise standalone, await the command coroutine, and always
    close connections afterwards, so each command stays free of connection
    lifecycle boilerplate and shuts down cleanly even when it raises.

    Args:
        coro: The command coroutine to run against an open Tortoise connection.
    """

    async def _run() -> None:
        await init_tortoise()
        try:
            await coro
        finally:
            await Tortoise.close_connections()

    asyncio.run(_run())
