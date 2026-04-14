"""Unit tests for provide_acting_user dependency provider."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from uuid_utils import uuid7

from vapi.constants import ON_BEHALF_OF_HEADER_KEY
from vapi.domain.deps import provide_acting_user
from vapi.lib.exceptions import NotFoundError, ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable

    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.user import User

pytestmark = pytest.mark.anyio


def _make_request(headers: dict[str, str] | None = None, acting_user: object = None) -> MagicMock:
    """Build a mock Litestar Request with configurable headers and state."""
    request = MagicMock()
    request.headers = headers or {}

    state = MagicMock()
    # Use a sentinel so getattr(..., "acting_user", None) returns None by default
    if acting_user is not None:
        state.acting_user = acting_user
    else:
        del state.acting_user
    request.state = state
    return request


class TestProvideActingUser:
    """Tests for provide_acting_user dependency provider."""

    async def test_missing_header_raises_validation_error(
        self, company_factory: Callable[..., Company]
    ) -> None:
        """Verify raising ValidationError when On-Behalf-Of header is missing."""
        # Given a company and a request with no On-Behalf-Of header
        company = await company_factory()
        request = _make_request(headers={})

        # When calling provide_acting_user
        # Then a ValidationError is raised
        with pytest.raises(ValidationError, match="header is required"):
            await provide_acting_user(request=request, company=company)

    async def test_invalid_uuid_raises_validation_error(
        self, company_factory: Callable[..., Company]
    ) -> None:
        """Verify raising ValidationError when header value is not a valid UUID."""
        # Given a company and a request with an invalid UUID in the header
        company = await company_factory()
        request = _make_request(headers={ON_BEHALF_OF_HEADER_KEY: "not-a-uuid"})

        # When calling provide_acting_user
        # Then a ValidationError is raised
        with pytest.raises(ValidationError, match="must be a valid UUID"):
            await provide_acting_user(request=request, company=company)

    async def test_nonexistent_user_raises_not_found(
        self, company_factory: Callable[..., Company]
    ) -> None:
        """Verify raising NotFoundError when user does not exist."""
        # Given a company and a request with a UUID that does not match any user
        company = await company_factory()
        request = _make_request(headers={ON_BEHALF_OF_HEADER_KEY: str(uuid7())})

        # When calling provide_acting_user
        # Then a NotFoundError is raised
        with pytest.raises(NotFoundError, match="Acting user not found"):
            await provide_acting_user(request=request, company=company)

    async def test_valid_header_returns_user(
        self,
        company_factory: Callable[..., Company],
        user_factory: Callable[..., User],
    ) -> None:
        """Verify returning the correct user when header contains a valid user UUID."""
        # Given a company and a user belonging to that company
        company = await company_factory()
        user = await user_factory(company=company)
        request = _make_request(headers={ON_BEHALF_OF_HEADER_KEY: str(user.id)})

        # When calling provide_acting_user
        result = await provide_acting_user(request=request, company=company)

        # Then the correct user is returned and cached on request.state
        assert result.id == user.id
        assert request.state.acting_user.id == user.id

    async def test_cached_user_skips_query(
        self,
        company_factory: Callable[..., Company],
        user_factory: Callable[..., User],
    ) -> None:
        """Verify returning cached user from request.state without querying the database."""
        # Given a company and a user already cached on request.state
        company = await company_factory()
        user = await user_factory(company=company)
        request = _make_request(acting_user=user)

        # When calling provide_acting_user (no header needed since cache is used)
        result = await provide_acting_user(request=request, company=company)

        # Then the cached user is returned directly
        assert result.id == user.id

    async def test_user_in_wrong_company_raises_not_found(
        self,
        company_factory: Callable[..., Company],
        user_factory: Callable[..., User],
    ) -> None:
        """Verify raising NotFoundError when user belongs to a different company."""
        # Given two companies and a user belonging to the first company
        company_a = await company_factory(name="Company A")
        company_b = await company_factory(name="Company B")
        user = await user_factory(company=company_a)
        request = _make_request(headers={ON_BEHALF_OF_HEADER_KEY: str(user.id)})

        # When calling provide_acting_user with the second company
        # Then a NotFoundError is raised
        with pytest.raises(NotFoundError, match="Acting user not found"):
            await provide_acting_user(request=request, company=company_b)

    async def test_archived_user_raises_not_found(
        self,
        company_factory: Callable[..., Company],
        user_factory: Callable[..., User],
    ) -> None:
        """Verify raising NotFoundError when user is archived."""
        # Given a company and an archived user
        company = await company_factory()
        user = await user_factory(company=company, is_archived=True)
        request = _make_request(headers={ON_BEHALF_OF_HEADER_KEY: str(user.id)})

        # When calling provide_acting_user
        # Then a NotFoundError is raised
        with pytest.raises(NotFoundError, match="Acting user not found"):
            await provide_acting_user(request=request, company=company)
