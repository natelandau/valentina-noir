"""Tests for the identity resolution endpoints."""

from collections.abc import Callable
from typing import Any

import pytest
from httpx import AsyncClient
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_409_CONFLICT,
    HTTP_422_UNPROCESSABLE_ENTITY,
)
from pytest_mock import MockerFixture

from vapi.constants import AUTH_HEADER_KEY
from vapi.db.sql_models.audit_log import AuditLog
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.developer import Developer
from vapi.db.sql_models.user import User
from vapi.domain import urls
from vapi.domain.services.developer_svc import DeveloperService
from vapi.lib.exceptions import UnprocessableEntityError
from vapi.utils.identity import VerifiedIdentity

pytestmark = pytest.mark.anyio

VERIFY_TARGET = "vapi.domain.controllers.identity.controllers.verify_provider_token"

_developer_service = DeveloperService()


def _identity(**overrides: Any) -> VerifiedIdentity:
    """Build a VerifiedIdentity with sensible defaults."""
    defaults: dict[str, Any] = {
        "provider": "apple",
        "provider_id": "apple-sub-001",
        "email": "person@example.com",
        "email_verified": True,
        "profile": {"id": "apple-sub-001", "email": "person@example.com"},
    }
    defaults.update(overrides)
    return VerifiedIdentity(**defaults)


class TestIdentifyEndpoint:
    """Test POST /companies/{company_id}/auth/identify."""

    async def test_identify_creates_user(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        token_company_user: dict[str, str],
        mocker: MockerFixture,
    ) -> None:
        """Verify an unknown verified identity creates an UNAPPROVED user."""
        # Given a verified identity with no matching user
        mock_verify = mocker.patch(VERIFY_TARGET, autospec=True)
        mock_verify.return_value = _identity()

        # When the client identifies the login
        response = await client.post(
            build_url(urls.Identity.IDENTIFY, company_id=session_company.id),
            headers=token_company_user,
            json={"provider": "apple", "token": "verified-upstream"},
        )

        # Then a new UNAPPROVED user is created
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["resolution"] == "created"
        assert data["user"]["role"] == "UNAPPROVED"
        assert data["user"]["apple_profile"]["id"] == "apple-sub-001"

    async def test_identify_matches_existing_user(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        token_company_user: dict[str, str],
        user_factory: Callable[..., User],
        mocker: MockerFixture,
    ) -> None:
        """Verify a known provider ID resolves to the existing user."""
        # Given a user already holding the apple identity
        user = await user_factory(company=session_company, apple_profile={"id": "apple-sub-001"})
        mock_verify = mocker.patch(VERIFY_TARGET, autospec=True)
        mock_verify.return_value = _identity()

        # When the client identifies the login
        response = await client.post(
            build_url(urls.Identity.IDENTIFY, company_id=session_company.id),
            headers=token_company_user,
            json={"provider": "apple", "token": "verified-upstream"},
        )

        # Then the existing user is matched
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["resolution"] == "matched"
        assert data["user"]["id"] == str(user.id)

    async def test_identify_auto_links_by_verified_email(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        token_company_user: dict[str, str],
        user_factory: Callable[..., User],
        mocker: MockerFixture,
    ) -> None:
        """Verify a verified-email match auto-links the provider to the existing user."""
        # Given a user with the matching email and no apple identity
        user = await user_factory(company=session_company, email="person@example.com")
        mock_verify = mocker.patch(VERIFY_TARGET, autospec=True)
        mock_verify.return_value = _identity()

        # When the client identifies the login
        response = await client.post(
            build_url(urls.Identity.IDENTIFY, company_id=session_company.id),
            headers=token_company_user,
            json={"provider": "apple", "token": "verified-upstream"},
        )

        # Then the identity is linked to the existing user
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["resolution"] == "linked"
        assert data["user"]["id"] == str(user.id)
        assert data["user"]["apple_profile"]["id"] == "apple-sub-001"

    async def test_identify_unknown_provider(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        token_company_user: dict[str, str],
    ) -> None:
        """Verify an unknown provider is rejected with 400."""
        # Given a request naming an unsupported provider

        # When the client sends it
        response = await client.post(
            build_url(urls.Identity.IDENTIFY, company_id=session_company.id),
            headers=token_company_user,
            json={"provider": "myspace", "token": "x"},
        )

        # Then the request is rejected
        assert response.status_code == HTTP_400_BAD_REQUEST

    async def test_identify_verification_failure(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        token_company_user: dict[str, str],
        mocker: MockerFixture,
    ) -> None:
        """Verify a failed token verification surfaces as 422 with the error code."""
        # Given verification fails upstream
        mock_verify = mocker.patch(VERIFY_TARGET, autospec=True)
        mock_verify.side_effect = UnprocessableEntityError(
            detail="bad token", code="TOKEN_VERIFICATION_FAILED"
        )

        # When the client identifies the login
        response = await client.post(
            build_url(urls.Identity.IDENTIFY, company_id=session_company.id),
            headers=token_company_user,
            json={"provider": "apple", "token": "expired"},
        )

        # Then the verification failure is surfaced with its code
        assert response.status_code == HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()["code"] == "TOKEN_VERIFICATION_FAILED"

    async def test_identify_missing_email_requires_fallback(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        token_company_user: dict[str, str],
        mocker: MockerFixture,
    ) -> None:
        """Verify creation without provider email succeeds when the body supplies one."""
        # Given a provider identity with no email
        mock_verify = mocker.patch(VERIFY_TARGET, autospec=True)
        mock_verify.return_value = _identity(
            provider="github",
            provider_id="4242",
            email=None,
            email_verified=False,
            profile={"id": "4242", "login": "octocat", "email": None},
        )

        # When the client supplies a fallback email
        response = await client.post(
            build_url(urls.Identity.IDENTIFY, company_id=session_company.id),
            headers=token_company_user,
            json={"provider": "github", "token": "gho_x", "email": "octo@example.com"},
        )

        # Then the user is created with the fallback email
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["resolution"] == "created"
        assert data["user"]["email"] == "octo@example.com"

    @pytest.mark.clean_db
    async def test_identify_redacts_token_in_audit_log(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        token_company_user: dict[str, str],
        mocker: MockerFixture,
    ) -> None:
        """Verify the provider token is replaced with [REDACTED] in the audit log."""
        # Given a verified identity and a clean audit log
        await AuditLog.all().delete()
        mock_verify = mocker.patch(VERIFY_TARGET, autospec=True)
        mock_verify.return_value = _identity()

        # When the client identifies the login with a raw bearer token
        response = await client.post(
            build_url(urls.Identity.IDENTIFY, company_id=session_company.id),
            headers=token_company_user,
            json={"provider": "apple", "token": "verified-upstream"},
        )

        # Then the request succeeds
        assert response.status_code == HTTP_200_OK

        # And the audit log entry stores [REDACTED] instead of the raw token
        audit = await AuditLog.filter(operation_id="identifyUser").first()
        assert audit is not None
        assert audit.request_json is not None
        assert audit.request_json.get("token") == "[REDACTED]"
        assert "verified-upstream" not in str(audit.request_json)
        assert "verified-upstream" not in (audit.request_body or "")

    async def test_identify_forbidden_for_non_member_developer(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        developer_factory: Callable,
        mocker: MockerFixture,
    ) -> None:
        """Verify a developer with no permission for the company receives 403."""
        # Given a developer that has no access to the company
        outsider = await developer_factory(username="outsider-dev", email="outsider@example.com")
        api_key = await _developer_service.generate_api_key(outsider)
        outsider_token = {AUTH_HEADER_KEY: api_key}

        mock_verify = mocker.patch(VERIFY_TARGET, autospec=True)
        mock_verify.return_value = _identity()

        # When the outsider calls identify for a company they don't belong to
        response = await client.post(
            build_url(urls.Identity.IDENTIFY, company_id=session_company.id),
            headers=outsider_token,
            json={"provider": "apple", "token": "verified-upstream"},
        )

        # Then the guard rejects the request
        assert response.status_code == HTTP_403_FORBIDDEN


class TestLinkIdentityEndpoint:
    """Test POST /companies/{company_id}/users/{user_id}/identities."""

    async def test_link_self(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        token_company_user: dict[str, str],
        user_factory: Callable[..., User],
        mocker: MockerFixture,
    ) -> None:
        """Verify a user can link a second provider to their own account."""
        # Given an active user acting on their own behalf
        user = await user_factory(company=session_company, role="PLAYER")
        mock_verify = mocker.patch(VERIFY_TARGET, autospec=True)
        mock_verify.return_value = _identity()

        # When they link a verified apple identity
        response = await client.post(
            build_url(urls.Identity.LINK, company_id=session_company.id, user_id=user.id),
            headers=token_company_user | {"On-Behalf-Of": str(user.id)},
            json={"provider": "apple", "token": "verified-upstream"},
        )

        # Then the identity is attached
        assert response.status_code == HTTP_200_OK
        assert response.json()["apple_profile"]["id"] == "apple-sub-001"

    async def test_link_other_user_requires_admin(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        token_company_user: dict[str, str],
        user_factory: Callable[..., User],
        mocker: MockerFixture,
    ) -> None:
        """Verify a non-admin cannot link identities for another user."""
        # Given a player acting on another user's account
        actor = await user_factory(company=session_company, role="PLAYER")
        target = await user_factory(company=session_company, role="PLAYER")
        mock_verify = mocker.patch(VERIFY_TARGET, autospec=True)
        mock_verify.return_value = _identity()

        # When they attempt to link
        response = await client.post(
            build_url(urls.Identity.LINK, company_id=session_company.id, user_id=target.id),
            headers=token_company_user | {"On-Behalf-Of": str(actor.id)},
            json={"provider": "apple", "token": "verified-upstream"},
        )

        # Then the request is denied
        assert response.status_code == HTTP_403_FORBIDDEN

    async def test_link_admin_for_other_user(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        token_company_user: dict[str, str],
        user_factory: Callable[..., User],
        mocker: MockerFixture,
    ) -> None:
        """Verify an admin can link identities for another user."""
        # Given an admin acting on another user's account
        admin = await user_factory(company=session_company, role="ADMIN")
        target = await user_factory(company=session_company, role="PLAYER")
        mock_verify = mocker.patch(VERIFY_TARGET, autospec=True)
        mock_verify.return_value = _identity()

        # When the admin links the identity
        response = await client.post(
            build_url(urls.Identity.LINK, company_id=session_company.id, user_id=target.id),
            headers=token_company_user | {"On-Behalf-Of": str(admin.id)},
            json={"provider": "apple", "token": "verified-upstream"},
        )

        # Then the identity is attached
        assert response.status_code == HTTP_200_OK

    async def test_link_unapproved_acting_user_rejected(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        token_company_user: dict[str, str],
        user_factory: Callable[..., User],
    ) -> None:
        """Verify an unapproved acting user cannot link identities."""
        # Given an UNAPPROVED user sending On-Behalf-Of with their own id
        user = await user_factory(company=session_company, role="UNAPPROVED")

        # When they attempt to link an identity on their own behalf
        response = await client.post(
            build_url(urls.Identity.LINK, company_id=session_company.id, user_id=user.id),
            headers=token_company_user | {"On-Behalf-Of": str(user.id)},
            json={"provider": "apple", "token": "verified-upstream"},
        )

        # Then user_active_guard blocks the request before the handler runs
        assert response.status_code == HTTP_403_FORBIDDEN

    async def test_link_verification_failure(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        token_company_user: dict[str, str],
        user_factory: Callable[..., User],
        mocker: MockerFixture,
    ) -> None:
        """Verify a failed token verification surfaces as 422 on the link endpoint."""
        # Given a user and a token that fails verification upstream
        user = await user_factory(company=session_company, role="PLAYER")
        mock_verify = mocker.patch(VERIFY_TARGET, autospec=True)
        mock_verify.side_effect = UnprocessableEntityError(
            detail="bad token", code="TOKEN_VERIFICATION_FAILED"
        )

        # When they attempt to link
        response = await client.post(
            build_url(urls.Identity.LINK, company_id=session_company.id, user_id=user.id),
            headers=token_company_user | {"On-Behalf-Of": str(user.id)},
            json={"provider": "apple", "token": "expired"},
        )

        # Then the verification failure is surfaced with its code
        assert response.status_code == HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()["code"] == "TOKEN_VERIFICATION_FAILED"

    async def test_link_conflict(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        token_company_user: dict[str, str],
        user_factory: Callable[..., User],
        mocker: MockerFixture,
    ) -> None:
        """Verify linking an identity owned by another user returns 409."""
        # Given the identity already belongs to someone else
        await user_factory(company=session_company, apple_profile={"id": "apple-sub-001"})
        user = await user_factory(company=session_company, role="PLAYER")
        mock_verify = mocker.patch(VERIFY_TARGET, autospec=True)
        mock_verify.return_value = _identity()

        # When the user attempts to link it
        response = await client.post(
            build_url(urls.Identity.LINK, company_id=session_company.id, user_id=user.id),
            headers=token_company_user | {"On-Behalf-Of": str(user.id)},
            json={"provider": "apple", "token": "verified-upstream"},
        )

        # Then the conflict is reported with the error code
        assert response.status_code == HTTP_409_CONFLICT
        assert response.json()["code"] == "IDENTITY_ALREADY_LINKED"
