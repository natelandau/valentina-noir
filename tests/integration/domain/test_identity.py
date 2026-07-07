"""Tests for the identity resolution endpoints."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_422_UNPROCESSABLE_ENTITY,
)
from pytest_mock import MockerFixture

from tests.fixtures import build_verified_identity as _identity
from vapi.constants import AUTH_HEADER_KEY, AuditOperation, CompanyPermission
from vapi.db.sql_models.audit_log import AuditLog
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.developer import Developer, DeveloperCompanyPermission
from vapi.db.sql_models.user import User
from vapi.domain import urls
from vapi.domain.services.developer_svc import DeveloperService
from vapi.lib.exceptions import UnprocessableEntityError
from vapi.utils.time import time_now

pytestmark = pytest.mark.anyio

VERIFY_TARGET = "vapi.domain.controllers.identity.controllers.verify_provider_token"

_developer_service = DeveloperService()


@pytest.fixture
def mock_verify(mocker: MockerFixture) -> MagicMock:
    """Patch provider-token verification to return a default verified Apple identity.

    Tests needing a different identity reassign ``return_value``; tests exercising a
    verification failure set ``side_effect`` on the returned mock.
    """
    mock = mocker.patch(VERIFY_TARGET, autospec=True)
    mock.return_value = _identity()
    return mock


class TestIdentifyEndpoint:
    """Test POST /companies/{company_id}/auth/identify."""

    async def test_identify_creates_user(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        token_company_user: dict[str, str],
        mock_verify: MagicMock,
    ) -> None:
        """Verify an unknown verified identity creates an UNAPPROVED user."""
        # Given a verified identity with no matching user

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
        mock_verify: MagicMock,
    ) -> None:
        """Verify a known provider ID resolves to the existing user."""
        # Given a user already holding the apple identity
        user = await user_factory(company=session_company, apple_profile={"id": "apple-sub-001"})

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
        mock_verify: MagicMock,
    ) -> None:
        """Verify a verified-email match auto-links the provider to the existing user."""
        # Given a user with the matching email and no apple identity
        user = await user_factory(company=session_company, email="person@example.com")

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
        mock_verify: MagicMock,
    ) -> None:
        """Verify a failed token verification surfaces as 422 with the error code."""
        # Given verification fails upstream
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
        mock_verify: MagicMock,
    ) -> None:
        """Verify creation without provider email succeeds when the body supplies one."""
        # Given a provider identity with no email
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

    async def test_identify_redacts_token_in_audit_log(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        token_company_user: dict[str, str],
        mock_verify: MagicMock,
    ) -> None:
        """Verify the provider token is replaced with [REDACTED] in the audit log."""
        # Given a verified identity and a clean audit log
        await AuditLog.all().delete()

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
        mock_verify: MagicMock,
    ) -> None:
        """Verify a developer with no permission for the company receives 403."""
        # Given a developer that has no access to the company
        outsider = await developer_factory(username="outsider-dev", email="outsider@example.com")
        api_key = await _developer_service.generate_api_key(outsider)
        outsider_token = {AUTH_HEADER_KEY: api_key}

        # When the outsider calls identify for a company they don't belong to
        response = await client.post(
            build_url(urls.Identity.IDENTIFY, company_id=session_company.id),
            headers=outsider_token,
            json={"provider": "apple", "token": "verified-upstream"},
        )

        # Then the guard rejects the request
        assert response.status_code == HTTP_403_FORBIDDEN

    async def test_identify_returns_annotated_counts(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        token_company_user: dict[str, str],
        user_factory: Callable[..., User],
        quickroll_factory: Any,
        mock_verify: MagicMock,
    ) -> None:
        """Verify the identify response includes accurate child-resource counts for existing users."""
        # Given an existing user with one quickroll
        user = await user_factory(
            company=session_company,
            role="PLAYER",
            apple_profile={"id": "apple-sub-001", "email": "person@example.com"},
        )
        await quickroll_factory(user=user)

        # When the client identifies the user
        response = await client.post(
            build_url(urls.Identity.IDENTIFY, company_id=session_company.id),
            headers=token_company_user,
            json={"provider": "apple", "token": "verified-upstream"},
        )

        # Then the response includes accurate counts rather than zeros
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["resolution"] == "matched"
        assert data["user"]["num_quickrolls"] == 1

    async def test_identify_with_unapproved_on_behalf_of_header(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        token_company_user: dict[str, str],
        user_factory: Callable[..., User],
        mock_verify: MagicMock,
    ) -> None:
        """Verify an unapproved acting user can call identify when On-Behalf-Of is set."""
        # Given an UNAPPROVED user whose ID will be sent as the On-Behalf-Of header
        unapproved = await user_factory(company=session_company, role="UNAPPROVED")
        mock_verify.return_value = _identity(
            provider_id="apple-sub-unapproved",
            email="unapproved@example.com",
            profile={"id": "apple-sub-unapproved", "email": "unapproved@example.com"},
        )

        # When the client calls identify with On-Behalf-Of pointing to the unapproved user
        response = await client.post(
            build_url(urls.Identity.IDENTIFY, company_id=session_company.id),
            headers=token_company_user | {"On-Behalf-Of": str(unapproved.id)},
            json={"provider": "apple", "token": "verified-upstream"},
        )

        # Then the request succeeds (allow_unapproved_user bypasses the active guard) and
        # resolves to a new user (the identity matches no existing provider id or email)
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["resolution"] == "created"

    async def test_identify_audit_operation_is_update_for_matched_user(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        token_company_user: dict[str, str],
        user_factory: Callable[..., User],
        mock_verify: MagicMock,
    ) -> None:
        """Verify the audit log records UPDATE when identify resolves to an existing user."""
        # Given an existing user and a clean audit log
        await AuditLog.all().delete()
        await user_factory(
            company=session_company,
            apple_profile={"id": "apple-sub-001", "email": "person@example.com"},
        )

        # When the client identifies the user (matched resolution)
        response = await client.post(
            build_url(urls.Identity.IDENTIFY, company_id=session_company.id),
            headers=token_company_user,
            json={"provider": "apple", "token": "verified-upstream"},
        )

        # Then the resolution is matched
        assert response.status_code == HTTP_200_OK
        assert response.json()["resolution"] == "matched"

        # And the audit log records UPDATE (not CREATE) because no new user was created
        audit = await AuditLog.filter(operation_id="identifyUser").first()
        assert audit is not None
        assert audit.operation == AuditOperation.UPDATE

    async def test_identify_audit_operation_is_create_for_new_user(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        token_company_user: dict[str, str],
        mock_verify: MagicMock,
    ) -> None:
        """Verify the audit log records CREATE when identify creates a new user."""
        # Given a clean audit log and no matching user
        await AuditLog.all().delete()

        # When the client identifies an unknown identity
        response = await client.post(
            build_url(urls.Identity.IDENTIFY, company_id=session_company.id),
            headers=token_company_user,
            json={"provider": "apple", "token": "verified-upstream"},
        )

        # Then the resolution is created
        assert response.status_code == HTTP_200_OK
        assert response.json()["resolution"] == "created"

        # And the audit log records CREATE
        audit = await AuditLog.filter(operation_id="identifyUser").first()
        assert audit is not None
        assert audit.operation == AuditOperation.CREATE

    @pytest.mark.parametrize(
        ("stored_profile", "expect_bump"),
        [
            # An identical stored profile means the login changes nothing, so the
            # cache flush and company timestamp bump are suppressed.
            pytest.param(
                {"id": "apple-sub-001", "email": "person@example.com"},
                False,
                id="unchanged-match-suppressed",
            ),
            # A differing stored profile is refreshed by the login, so the company
            # timestamp must bump to invalidate stale cached user data.
            pytest.param(
                {"id": "apple-sub-001", "email": "stale@example.com"},
                True,
                id="changed-match-invalidates",
            ),
        ],
    )
    async def test_identify_match_bumps_company_timestamp_only_when_changed(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        token_company_user: dict[str, str],
        user_factory: Callable[..., User],
        mock_verify: MagicMock,
        stored_profile: dict[str, str],
        expect_bump: bool,
    ) -> None:
        """Verify a matched login bumps resources_modified_at only when it changes the user."""
        # Given a user holding the apple identity and a company timestamp set 10 days back
        await user_factory(company=session_company, apple_profile=stored_profile)
        old_ts = time_now() - timedelta(days=10)
        await Company.filter(id=session_company.id).update(resources_modified_at=old_ts)

        # When the client identifies the login (matched by provider id)
        response = await client.post(
            build_url(urls.Identity.IDENTIFY, company_id=session_company.id),
            headers=token_company_user,
            json={"provider": "apple", "token": "verified-upstream"},
        )

        # Then the timestamp bumps only when the matched login actually changed the user
        assert response.status_code == HTTP_200_OK
        assert response.json()["resolution"] == "matched"
        refreshed = await Company.get(id=session_company.id)
        if expect_bump:
            assert refreshed.resources_modified_at > time_now() - timedelta(days=1)
        else:
            assert refreshed.resources_modified_at < time_now() - timedelta(days=1)

    async def test_identify_passes_developer_audiences_to_verify(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        developer_factory: Callable[..., Any],
        mock_verify: MagicMock,
    ) -> None:
        """Verify identify calls verify_provider_token with the developer's registered audiences."""
        # Given a fresh developer with provider_audiences registered for apple
        developer = await developer_factory(
            username="audiences-test-dev",
            email="audiences-dev@example.com",
            provider_audiences={"apple": ["com.myapp.bundle"]},
        )
        await DeveloperCompanyPermission.create(
            developer=developer,
            company=session_company,
            permission=CompanyPermission.USER,
        )
        api_key = await _developer_service.generate_api_key(developer)
        token = {AUTH_HEADER_KEY: api_key}

        # When the developer calls identify for apple
        response = await client.post(
            build_url(urls.Identity.IDENTIFY, company_id=session_company.id),
            headers=token,
            json={"provider": "apple", "token": "verified-upstream"},
        )

        # Then the request succeeds
        assert response.status_code == HTTP_200_OK

        # And verify_provider_token was called with the developer's registered audiences
        mock_verify.assert_called_once()
        call_kwargs = mock_verify.call_args.kwargs
        assert call_kwargs.get("additional_audiences") == ["com.myapp.bundle"]


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
        mock_verify: MagicMock,
    ) -> None:
        """Verify a user can link a second provider to their own account."""
        # Given an active user acting on their own behalf
        user = await user_factory(company=session_company, role="PLAYER")

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
        mock_verify: MagicMock,
    ) -> None:
        """Verify a non-admin cannot link identities for another user."""
        # Given a player acting on another user's account
        actor = await user_factory(company=session_company, role="PLAYER")
        target = await user_factory(company=session_company, role="PLAYER")

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
        mock_verify: MagicMock,
    ) -> None:
        """Verify an admin can link identities for another user."""
        # Given an admin acting on another user's account
        admin = await user_factory(company=session_company, role="ADMIN")
        target = await user_factory(company=session_company, role="PLAYER")

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
        mock_verify: MagicMock,
    ) -> None:
        """Verify a failed token verification surfaces as 422 on the link endpoint."""
        # Given a user and a token that fails verification upstream
        user = await user_factory(company=session_company, role="PLAYER")
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
        mock_verify: MagicMock,
    ) -> None:
        """Verify linking an identity owned by another user returns 409."""
        # Given the identity already belongs to someone else
        await user_factory(company=session_company, apple_profile={"id": "apple-sub-001"})
        user = await user_factory(company=session_company, role="PLAYER")

        # When the user attempts to link it
        response = await client.post(
            build_url(urls.Identity.LINK, company_id=session_company.id, user_id=user.id),
            headers=token_company_user | {"On-Behalf-Of": str(user.id)},
            json={"provider": "apple", "token": "verified-upstream"},
        )

        # Then the conflict is reported with the error code
        assert response.status_code == HTTP_409_CONFLICT
        assert response.json()["code"] == "IDENTITY_ALREADY_LINKED"

    async def test_link_redacts_token_in_audit_log(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        token_company_user: dict[str, str],
        user_factory: Callable[..., User],
        mock_verify: MagicMock,
    ) -> None:
        """Verify the provider token is replaced with [REDACTED] in the audit log for the link endpoint."""
        # Given an active user and a clean audit log
        await AuditLog.all().delete()
        user = await user_factory(company=session_company, role="PLAYER")

        # When the user links a provider identity with a raw bearer token
        response = await client.post(
            build_url(urls.Identity.LINK, company_id=session_company.id, user_id=user.id),
            headers=token_company_user | {"On-Behalf-Of": str(user.id)},
            json={"provider": "apple", "token": "verified-upstream"},
        )

        # Then the request succeeds
        assert response.status_code == HTTP_200_OK

        # And the audit log entry stores [REDACTED] instead of the raw token
        audit = await AuditLog.filter(operation_id="linkUserIdentity").first()
        assert audit is not None
        assert audit.request_json is not None
        assert audit.request_json.get("token") == "[REDACTED]"
        assert "verified-upstream" not in str(audit.request_json)
        assert "verified-upstream" not in (audit.request_body or "")

        # And the operation is classified as UPDATE (linking modifies an existing user)
        assert audit.operation == AuditOperation.UPDATE


class TestUnlinkIdentityEndpoint:
    """Test DELETE /companies/{company_id}/users/{user_id}/identities/{provider}."""

    async def test_unlink_self(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        token_company_user: dict[str, str],
        user_factory: Callable[..., User],
    ) -> None:
        """Verify a user can unlink a provider from their own account."""
        # Given a user with two linked identities acting on their own behalf
        user = await user_factory(
            company=session_company,
            role="PLAYER",
            apple_profile={"id": "apple-sub-001"},
            github_profile={"id": "4242"},
        )

        # When they unlink the apple identity
        response = await client.delete(
            build_url(
                urls.Identity.UNLINK,
                company_id=session_company.id,
                user_id=user.id,
                provider="apple",
            ),
            headers=token_company_user | {"On-Behalf-Of": str(user.id)},
        )

        # Then the apple identity is removed and the github identity remains
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["apple_profile"] is None
        assert data["github_profile"]["id"] == "4242"

    async def test_unlink_other_user_requires_admin(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        token_company_user: dict[str, str],
        user_factory: Callable[..., User],
    ) -> None:
        """Verify a non-admin cannot unlink identities for another user."""
        # Given a player acting on another user's account
        actor = await user_factory(company=session_company, role="PLAYER")
        target = await user_factory(
            company=session_company,
            role="PLAYER",
            apple_profile={"id": "apple-sub-001"},
            github_profile={"id": "4242"},
        )

        # When they attempt to unlink
        response = await client.delete(
            build_url(
                urls.Identity.UNLINK,
                company_id=session_company.id,
                user_id=target.id,
                provider="apple",
            ),
            headers=token_company_user | {"On-Behalf-Of": str(actor.id)},
        )

        # Then the request is denied
        assert response.status_code == HTTP_403_FORBIDDEN

    async def test_unlink_admin_for_other_user(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        token_company_user: dict[str, str],
        user_factory: Callable[..., User],
    ) -> None:
        """Verify an admin can unlink identities for another user."""
        # Given an admin acting on another user's account
        admin = await user_factory(company=session_company, role="ADMIN")
        target = await user_factory(
            company=session_company,
            role="PLAYER",
            apple_profile={"id": "apple-sub-001"},
            github_profile={"id": "4242"},
        )

        # When the admin unlinks the apple identity
        response = await client.delete(
            build_url(
                urls.Identity.UNLINK,
                company_id=session_company.id,
                user_id=target.id,
                provider="apple",
            ),
            headers=token_company_user | {"On-Behalf-Of": str(admin.id)},
        )

        # Then the identity is removed
        assert response.status_code == HTTP_200_OK
        assert response.json()["apple_profile"] is None

    async def test_unlink_not_linked(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        token_company_user: dict[str, str],
        user_factory: Callable[..., User],
    ) -> None:
        """Verify unlinking a provider the user never linked returns 404."""
        # Given a user with only an apple identity
        user = await user_factory(
            company=session_company, role="PLAYER", apple_profile={"id": "apple-sub-001"}
        )

        # When they unlink a github identity they never linked
        response = await client.delete(
            build_url(
                urls.Identity.UNLINK,
                company_id=session_company.id,
                user_id=user.id,
                provider="github",
            ),
            headers=token_company_user | {"On-Behalf-Of": str(user.id)},
        )

        # Then the request reports the identity is not linked
        assert response.status_code == HTTP_404_NOT_FOUND
        assert response.json()["code"] == "IDENTITY_NOT_LINKED"

    async def test_unlink_last_identity_rejected(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        token_company_user: dict[str, str],
        user_factory: Callable[..., User],
    ) -> None:
        """Verify a user cannot unlink their only linked identity."""
        # Given a user with a single linked identity
        user = await user_factory(
            company=session_company, role="PLAYER", apple_profile={"id": "apple-sub-001"}
        )

        # When they attempt to unlink it
        response = await client.delete(
            build_url(
                urls.Identity.UNLINK,
                company_id=session_company.id,
                user_id=user.id,
                provider="apple",
            ),
            headers=token_company_user | {"On-Behalf-Of": str(user.id)},
        )

        # Then the request is refused with the error code
        assert response.status_code == HTTP_409_CONFLICT
        assert response.json()["code"] == "LAST_IDENTITY"

    async def test_unlink_audit_operation_is_update(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        token_company_user: dict[str, str],
        user_factory: Callable[..., User],
    ) -> None:
        """Verify the audit log records UPDATE when an identity is unlinked."""
        # Given a clean audit log and a user with two linked identities
        await AuditLog.all().delete()
        user = await user_factory(
            company=session_company,
            role="PLAYER",
            apple_profile={"id": "apple-sub-001"},
            github_profile={"id": "4242"},
        )

        # When the user unlinks the apple identity
        response = await client.delete(
            build_url(
                urls.Identity.UNLINK,
                company_id=session_company.id,
                user_id=user.id,
                provider="apple",
            ),
            headers=token_company_user | {"On-Behalf-Of": str(user.id)},
        )

        # Then the request succeeds
        assert response.status_code == HTTP_200_OK

        # And the audit log records UPDATE (the user row persists, only a field is cleared)
        audit = await AuditLog.filter(operation_id="unlinkUserIdentity").first()
        assert audit is not None
        assert audit.operation == AuditOperation.UPDATE
