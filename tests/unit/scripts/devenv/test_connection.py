"""Unit tests for the connection sheet renderers."""

import json
import stat
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from scripts.devenv import connection
from scripts.devenv.connection import (
    CompanyInfo,
    ConnectionData,
    DeveloperInfo,
    UserInfo,
    render_json,
    render_markdown,
)
from scripts.devenv.ports import StackPorts

PORTS = StackPorts.for_slot(0)
NOW = datetime(2026, 10, 29, 12, 30, 0, tzinfo=UTC)


def _data() -> ConnectionData:
    company = CompanyInfo(id=uuid4(), name="Acme Co")
    keyed = DeveloperInfo(
        id=uuid4(),
        username="keyed",
        email="keyed@example.com",
        is_global_admin=False,
        api_key="raw-key-1",
        permissions=[(company.id, "ADMIN")],
    )
    unkeyed = DeveloperInfo(
        id=uuid4(),
        username="unkeyed",
        email="unkeyed@example.com",
        is_global_admin=True,
        api_key=None,
        permissions=[],
    )
    user = UserInfo(
        id=uuid4(),
        name="Ada Lovelace",
        role="STORYTELLER",
        company_id=company.id,
    )
    return ConnectionData(
        origin="populated", developers=[keyed, unkeyed], companies=[company], users=[user]
    )


def test_render_markdown_lists_every_section() -> None:
    """The sheet carries the URL, each section, and a curl line per keyed developer."""
    # Given
    data = _data()

    # When
    text = render_markdown(data, ports=PORTS, project="vapi-main", generated_at=NOW)

    # Then
    assert "http://127.0.0.1:24100" in text
    assert "http://host.docker.internal:24100" in text
    assert "## Developers" in text
    assert "## Companies" in text
    assert "## Users" in text
    assert "raw-key-1" in text
    assert "Acme Co" in text
    assert "Ada Lovelace" in text
    assert text.count('curl -H "X-API-KEY: ') == 1


def test_render_markdown_marks_missing_key() -> None:
    """A developer without a recorded key says so and gets no curl example."""
    # Given: only the unkeyed developer
    data = _data()
    data = ConnectionData(
        origin=data.origin, developers=[data.developers[1]], companies=[], users=[]
    )

    # When
    text = render_markdown(data, ports=PORTS, project="vapi-main", generated_at=NOW)

    # Then
    assert "key not recorded" in text
    assert "curl" not in text


def test_render_json_round_trips() -> None:
    """The JSON sheet preserves developer, company, and user IDs."""
    # Given
    data = _data()

    # When
    parsed = json.loads(render_json(data, ports=PORTS, project="vapi-main", generated_at=NOW))

    # Then
    assert [d["id"] for d in parsed["developers"]] == [str(d.id) for d in data.developers]
    assert [c["id"] for c in parsed["companies"]] == [str(c.id) for c in data.companies]
    assert [u["id"] for u in parsed["users"]] == [str(u.id) for u in data.users]
    assert parsed["api_url"] == "http://127.0.0.1:24100"
    assert parsed["ports"]["postgres"] == PORTS.postgres


def test_render_markdown_has_generated_at_and_every_port() -> None:
    """The sheet is timestamped and lists every published port."""
    # Given
    data = _data()

    # When
    text = render_markdown(data, ports=PORTS, project="vapi-main", generated_at=NOW)

    # Then
    assert "2026-10-29T12:30:00+00:00" in text
    for port in (
        PORTS.api,
        PORTS.postgres,
        PORTS.redis,
        PORTS.s3,
        PORTS.s3_console,
        PORTS.postgres_test,
        PORTS.redis_test,
        PORTS.debugpy,
    ):
        assert str(port) in text
    assert "only when started with debug=true" in text


def test_render_markdown_has_shell_commands() -> None:
    """The sheet gives ready-to-run psql and redis-cli commands for this stack."""
    # Given
    data = _data()

    # When
    text = render_markdown(data, ports=PORTS, project="vapi-main", generated_at=NOW)

    # Then
    assert "psql postgresql://valentina:valentina@127.0.0.1:24101/valentina-noir" in text
    assert "redis-cli -h 127.0.0.1 -p 24102" in text
    assert "uv run duty psql" in text
    assert "uv run duty redis-cli" in text


def test_render_json_has_generated_at() -> None:
    """The JSON sheet carries the same timestamp."""
    # Given / When
    parsed = json.loads(render_json(_data(), ports=PORTS, project="vapi-main", generated_at=NOW))

    # Then
    assert parsed["generated_at"] == "2026-10-29T12:30:00+00:00"


def test_write_files_are_private_and_json_is_valid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both sheet files contain raw keys, so only the owner can read them."""
    # Given
    monkeypatch.setattr(connection, "SHEET_DIR", tmp_path)

    # When
    connection._write_files(data=_data(), ports=PORTS, project="vapi-main")

    # Then
    for name in ("connection.md", "connection.json"):
        assert stat.S_IMODE((tmp_path / name).stat().st_mode) == 0o600
    assert "generated_at" in json.loads((tmp_path / "connection.json").read_text())
