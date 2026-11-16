"""Test developer controller (Tortoise ORM)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
)

from vapi.constants import AUTH_HEADER_KEY, CompanyPermission
from vapi.db.sql_models.developer import Developer, DeveloperCompanyPermission
from vapi.domain import deps
from vapi.domain.services.developer_svc import DeveloperService
from vapi.domain.urls import Developers, GlobalAdmin

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.sql_models.company import Company

pytestmark = pytest.mark.anyio

_developer_service = DeveloperService()


async def test_developer_me(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    build_url: Callable[[str, ...], str],
    session_global_admin: Developer,
    session_company: ...,
) -> None:
    """Verify the developer me endpoint returns developer with companies."""
    # When we request the current developer
    response = await client.get(build_url(Developers.ME), headers=token_global_admin)

    # Then the response has the developer data
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert data["id"] == str(session_global_admin.id)
    assert data["username"] == session_global_admin.username
    assert data["email"] == session_global_admin.email
    assert "companies" in data
    assert isinstance(data["companies"], list)


async def test_developer_new_key(
    client: AsyncClient,
    build_url: Callable[[str, ...], str],
    developer_factory: Callable[..., Any],
    session_company: Company,
) -> None:
    """Verify the developer can generate a new API key."""
    # Given a developer with a valid API key (use a local developer to avoid
    # mutating the session-scoped session_global_admin's key)
    developer = await developer_factory(is_global_admin=True)
    await DeveloperCompanyPermission.create(
        developer=developer, company=session_company, permission=CompanyPermission.OWNER
    )
    api_key = await _developer_service.generate_api_key(developer)
    token = {AUTH_HEADER_KEY: api_key}

    db_developer = await Developer.get(id=developer.id)
    original_hashed_api_key = db_developer.hashed_api_key
    original_api_key_fingerprint = db_developer.api_key_fingerprint

    # When we request a new key
    response = await client.post(
        build_url(Developers.NEW_KEY),
        headers=token,
    )

    # Then the response has the new key info
    assert response.status_code == HTTP_201_CREATED
    json_data = response.json()
    assert json_data["api_key"] is not None
    assert json_data["username"] == developer.username
    assert json_data["email"] == developer.email

    # And the key is updated in the database
    db_developer = await Developer.get(id=developer.id)
    assert db_developer.key_generated is not None
    assert db_developer.key_generated.strftime("%Y-%m-%dT%H:%M:%SZ") == json_data["key_generated"]
    assert db_developer.hashed_api_key is not None
    assert db_developer.api_key_fingerprint is not None
    assert db_developer.hashed_api_key != original_hashed_api_key
    assert db_developer.api_key_fingerprint != original_api_key_fingerprint


async def test_developer_update(
    client: AsyncClient,
    build_url: Callable[[str, ...], str],
    developer_factory: Callable[..., Any],
    session_company: Company,
) -> None:
    """Verify the developer can update their username and email."""
    # Given a developer with a valid API key (use a local developer to avoid
    # mutating the session-scoped session_global_admin)
    developer = await developer_factory(is_global_admin=True)
    await DeveloperCompanyPermission.create(
        developer=developer, company=session_company, permission=CompanyPermission.OWNER
    )
    api_key = await _developer_service.generate_api_key(developer)
    token = {AUTH_HEADER_KEY: api_key}

    # When we update the developer's info
    response = await client.patch(
        build_url(Developers.UPDATE),
        headers=token,
        json={"username": "updated user", "email": "updated@test.com"},
    )

    # Then the response has the updated info (username is slugified by pre_save signal)
    assert response.status_code == HTTP_200_OK
    assert response.json()["username"] == "updated-user"
    assert response.json()["email"] == "updated@test.com"

    # And the database is updated
    db_developer = await Developer.get(id=developer.id)
    assert db_developer.username == "updated-user"
    assert db_developer.email == "updated@test.com"


async def test_developer_update_provider_audiences_valid(
    client: AsyncClient,
    build_url: Callable[[str, ...], str],
    developer_factory: Callable[..., Any],
    session_company: Company,
) -> None:
    """Verify PATCH /developers/me persists and returns valid provider_audiences."""
    # Given a developer with a valid API key
    developer = await developer_factory(is_global_admin=True)
    await DeveloperCompanyPermission.create(
        developer=developer, company=session_company, permission=CompanyPermission.OWNER
    )
    api_key = await _developer_service.generate_api_key(developer)
    token = {AUTH_HEADER_KEY: api_key}

    audiences = {
        "apple": ["com.example.myapp"],
        "google": ["1234-abc.apps.googleusercontent.com"],
    }

    # When we set provider_audiences
    response = await client.patch(
        build_url(Developers.UPDATE),
        headers=token,
        json={"provider_audiences": audiences},
    )

    # Then the response is 200 and includes the audiences
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert data["provider_audiences"] == audiences

    # And the value is persisted in the database
    db_developer = await Developer.get(id=developer.id)
    assert db_developer.provider_audiences == audiences


async def test_developer_update_provider_audiences_invalid_key(
    client: AsyncClient,
    build_url: Callable[[str, ...], str],
    developer_factory: Callable[..., Any],
    session_company: Company,
) -> None:
    """Verify PATCH /developers/me rejects provider_audiences with an unsupported key."""
    # Given a developer with a valid API key
    developer = await developer_factory(is_global_admin=True)
    await DeveloperCompanyPermission.create(
        developer=developer, company=session_company, permission=CompanyPermission.OWNER
    )
    api_key = await _developer_service.generate_api_key(developer)
    token = {AUTH_HEADER_KEY: api_key}

    # When we send an unsupported provider key
    response = await client.patch(
        build_url(Developers.UPDATE),
        headers=token,
        json={"provider_audiences": {"github": ["some-client-id"]}},
    )

    # Then the request is rejected with 400
    assert response.status_code == HTTP_400_BAD_REQUEST


async def test_developer_update_provider_audiences_too_many(
    client: AsyncClient,
    build_url: Callable[[str, ...], str],
    developer_factory: Callable[..., Any],
    session_company: Company,
) -> None:
    """Verify PATCH /developers/me rejects more than 20 audiences per provider."""
    # Given a developer with a valid API key
    developer = await developer_factory(is_global_admin=True)
    await DeveloperCompanyPermission.create(
        developer=developer, company=session_company, permission=CompanyPermission.OWNER
    )
    api_key = await _developer_service.generate_api_key(developer)
    token = {AUTH_HEADER_KEY: api_key}

    # When we send 21 audiences for a provider
    response = await client.patch(
        build_url(Developers.UPDATE),
        headers=token,
        json={"provider_audiences": {"apple": [f"com.app.{i}" for i in range(21)]}},
    )

    # Then the request is rejected with 400
    assert response.status_code == HTTP_400_BAD_REQUEST


async def test_developer_update_provider_audiences_empty_string(
    client: AsyncClient,
    build_url: Callable[[str, ...], str],
    developer_factory: Callable[..., Any],
    session_company: Company,
) -> None:
    """Verify PATCH /developers/me rejects empty-string audience values."""
    # Given a developer with a valid API key
    developer = await developer_factory(is_global_admin=True)
    await DeveloperCompanyPermission.create(
        developer=developer, company=session_company, permission=CompanyPermission.OWNER
    )
    api_key = await _developer_service.generate_api_key(developer)
    token = {AUTH_HEADER_KEY: api_key}

    # When we send an empty string as an audience
    response = await client.patch(
        build_url(Developers.UPDATE),
        headers=token,
        json={"provider_audiences": {"apple": [""]}},
    )

    # Then the request is rejected with 400
    assert response.status_code == HTTP_400_BAD_REQUEST


async def test_developer_update_provider_audiences_whitespace_string(
    client: AsyncClient,
    build_url: Callable[[str, ...], str],
    developer_factory: Callable[..., Any],
    session_company: Company,
) -> None:
    """Verify PATCH /developers/me rejects whitespace-only audience values."""
    # Given a developer with a valid API key
    developer = await developer_factory(is_global_admin=True)
    await DeveloperCompanyPermission.create(
        developer=developer, company=session_company, permission=CompanyPermission.OWNER
    )
    api_key = await _developer_service.generate_api_key(developer)
    token = {AUTH_HEADER_KEY: api_key}

    # When we send a whitespace-only string as an audience
    response = await client.patch(
        build_url(Developers.UPDATE),
        headers=token,
        json={"provider_audiences": {"apple": ["   "]}},
    )

    # Then the request is rejected with 400
    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.parametrize("route", ["update", "new_key"])
@pytest.mark.parametrize("admin_action", ["archive", "demote", "rotate"])
async def test_developer_self_edit_keeps_concurrent_admin_revocation(
    client: AsyncClient,
    build_url: Callable[[str, ...], str],
    token_global_admin: dict[str, str],
    developer_factory: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
    route: str,
    admin_action: str,
) -> None:
    """Verify a global-admin revocation that lands mid-request survives the developer's self edit."""
    # Given a global admin developer authenticated with its own key
    developer = await developer_factory(is_global_admin=True)
    old_key = await _developer_service.generate_api_key(developer)
    developer_id = str(developer.id)
    admin_result: dict[str, Any] = {}

    async def run_admin_action() -> None:
        if admin_action == "archive":
            response = await client.delete(
                build_url(GlobalAdmin.DEVELOPER_DELETE, developer_id=developer_id),
                headers=token_global_admin,
            )
        elif admin_action == "demote":
            response = await client.patch(
                build_url(GlobalAdmin.DEVELOPER_UPDATE, developer_id=developer_id),
                headers=token_global_admin,
                json={"is_global_admin": False},
            )
        else:
            response = await client.post(
                build_url(GlobalAdmin.DEVELOPER_NEW_KEY, developer_id=developer_id),
                headers=token_global_admin,
            )
            admin_result["fingerprint"] = (await Developer.get(id=developer_id)).api_key_fingerprint
        assert response.is_success

    # When the admin action commits after the self request's developer provider loaded the row
    class LoadThenRunAdminAction:
        """Stand-in for Developer in the provider module that runs the admin action after the load."""

        @staticmethod
        def filter(*args: Any, **kwargs: Any) -> Any:
            query = Developer.filter(*args, **kwargs)

            class Query:
                def prefetch_related(self, *relations: str) -> Query:
                    nonlocal query
                    query = query.prefetch_related(*relations)
                    return self

                async def first(self) -> Developer | None:
                    loaded = await query.first()
                    monkeypatch.undo()
                    await run_admin_action()
                    return loaded

            return Query()

    monkeypatch.setattr(deps, "Developer", LoadThenRunAdminAction)
    if route == "update":
        response = await client.patch(
            build_url(Developers.UPDATE),
            headers={AUTH_HEADER_KEY: old_key},
            json={"username": f"renamed-{admin_action}"},
        )
    else:
        response = await client.post(
            build_url(Developers.NEW_KEY), headers={AUTH_HEADER_KEY: old_key}
        )
    monkeypatch.undo()

    # Then the admin change holds
    final = await Developer.get(id=developer_id)
    if admin_action == "archive":
        assert response.status_code == HTTP_401_UNAUTHORIZED
        assert final.is_archived is True
    elif admin_action == "demote":
        assert response.status_code == (HTTP_200_OK if route == "update" else HTTP_201_CREATED)
        assert final.is_global_admin is False
    else:
        assert response.status_code == HTTP_401_UNAUTHORIZED
        assert final.api_key_fingerprint == admin_result["fingerprint"]
