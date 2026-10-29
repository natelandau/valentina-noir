"""Integration test for reading the connection sheet data from the database."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from scripts.devenv.connection import gather_connection, render_json
from scripts.devenv.ports import StackPorts

from vapi.constants import CompanyPermission, UserRole

pytestmark = pytest.mark.anyio


async def test_gather_connection_reads_database(
    company_factory, user_factory, developer_factory, developer_company_permission_factory
) -> None:
    """Developers, companies, and users come back with roles, keys, and company IDs."""
    # Given: a company with two users and a keyed developer holding a permission
    company = await company_factory()
    admin = await user_factory(company=company, role=UserRole.ADMIN)
    player = await user_factory(company=company, role=UserRole.PLAYER)
    developer = await developer_factory()
    stale = await developer_factory()
    archived = await developer_factory(is_archived=True)
    await developer_company_permission_factory(
        developer=developer, company=company, permission=CompanyPermission.OWNER
    )

    # When
    data = await gather_connection(
        keys={developer.id: "raw-key", archived.id: "archived-key"}, origin="populated"
    )

    # Then
    found = {d.id: d for d in data.developers}
    assert found[developer.id].api_key == "raw-key"
    assert found[developer.id].permissions == [(company.id, "OWNER")]
    assert found[stale.id].api_key is None
    assert archived.id not in found
    assert company.id in {c.id for c in data.companies}
    users = {u.id: u for u in data.users}
    assert users[admin.id].role == "ADMIN"
    assert users[player.id].company_id == company.id


async def test_gather_connection_excludes_archived_rows_and_stale_keys(
    company_factory, user_factory, developer_factory
) -> None:
    """Archived companies and users are omitted, and keys of unknown developers never appear."""
    # Given: an archived company, an archived user in a live company, and an orphan key
    live = await company_factory()
    dead = await company_factory(is_archived=True)
    hidden_user = await user_factory(company=live, is_archived=True)
    orphan_key = "orphan-raw-key"
    developer = await developer_factory()

    # When
    data = await gather_connection(
        keys={developer.id: "raw-key", uuid4(): orphan_key}, origin="populated"
    )

    # Then
    assert live.id in {c.id for c in data.companies}
    assert dead.id not in {c.id for c in data.companies}
    assert hidden_user.id not in {u.id for u in data.users}
    assert orphan_key not in render_json(
        data, ports=StackPorts.for_slot(0), project="vapi-main", generated_at=datetime.now(tz=UTC)
    )
