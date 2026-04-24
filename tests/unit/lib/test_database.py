"""Tests for vapi.lib.database helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from vapi.lib.database import drop_and_recreate_database

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

pytestmark = pytest.mark.anyio


class TestDropAndRecreateDatabase:
    """Tests for the drop_and_recreate_database helper."""

    async def test_drops_and_recreates_via_asyncpg(self, mocker: MockerFixture) -> None:
        """Verify drop_and_recreate_database terminates connections, drops, then creates."""
        # Given a mocked asyncpg connection
        mock_conn = AsyncMock()
        mock_connect = mocker.patch(
            "vapi.lib.database.asyncpg.connect",
            new=AsyncMock(return_value=mock_conn),
        )

        # When the helper runs
        await drop_and_recreate_database()

        # Then it connected to the postgres maintenance database
        mock_connect.assert_awaited_once()
        kwargs = mock_connect.await_args.kwargs
        assert kwargs["database"] == "postgres"

        # Then it terminated backends, dropped, and recreated in that order
        calls = [c.args[0] for c in mock_conn.execute.await_args_list]
        assert len(calls) == 3
        assert "pg_terminate_backend" in calls[0]
        assert calls[1].startswith("DROP DATABASE IF EXISTS")
        assert calls[2].startswith("CREATE DATABASE")

        # Then it closed the connection even on success
        mock_conn.close.assert_awaited_once()
