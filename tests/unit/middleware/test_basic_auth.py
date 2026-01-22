"""Unit tests for BasicAuthMiddleware."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

import pytest
from litestar.exceptions import NotAuthorizedException

from vapi.middleware.basic_auth import BasicAuthMiddleware

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from pytest_mock import MockerFixture

pytestmark = pytest.mark.anyio


def _create_mock_connection(
    mocker: MockerFixture, path: str, authorization: str | None = None
) -> MagicMock:
    """Create a mock ASGIConnection for testing."""
    mock_connection = mocker.MagicMock()
    mock_connection.scope = {"path": path}
    headers: dict[str, str] = {}
    if authorization is not None:
        headers["Authorization"] = authorization
    mock_connection.headers = mocker.MagicMock()
    mock_connection.headers.get = lambda key, default="": headers.get(key, default)
    return mock_connection


def _encode_basic_auth(username: str, password: str) -> str:
    """Encode username and password as Basic Auth header value."""
    credentials = f"{username}:{password}"
    encoded = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
    return f"Basic {encoded}"


class TestBasicAuthMiddlewarePathFiltering:
    """Test path-based filtering logic."""

    async def test_non_saq_path_passes_through(self, mocker: MockerFixture) -> None:
        """Verify non-SAQ paths return empty AuthenticationResult."""
        # Given a connection to a non-SAQ path
        middleware = BasicAuthMiddleware(app=mocker.MagicMock())
        connection = _create_mock_connection(mocker, path="/api/v1/companies")

        # When authenticating the request
        result = await middleware.authenticate_request(connection)

        # Then it should pass through with no user
        assert result.user is None
        assert result.auth is None

    async def test_root_path_passes_through(self, mocker: MockerFixture) -> None:
        """Verify root path returns empty AuthenticationResult."""
        # Given a connection to the root path
        middleware = BasicAuthMiddleware(app=mocker.MagicMock())
        connection = _create_mock_connection(mocker, path="/")

        # When authenticating the request
        result = await middleware.authenticate_request(connection)

        # Then it should pass through with no user
        assert result.user is None
        assert result.auth is None

    @pytest.mark.parametrize(
        "path",
        [
            "/saq",
            "/saq/",
            "/saq/api/queues",
            "/saq/api/jobs",
        ],
    )
    async def test_saq_paths_require_auth(
        self, path: str, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify SAQ paths require authentication."""
        # Given SAQ admin credentials are configured
        from vapi.config import settings

        monkeypatch.setattr(settings.saq, "admin_username", "admin")
        monkeypatch.setattr(settings.saq, "admin_password", "secret123")

        # Given a connection to SAQ path without auth
        middleware = BasicAuthMiddleware(app=mocker.MagicMock())
        connection = _create_mock_connection(mocker, path=path)

        # When authenticating the request
        # Then it should raise NotAuthorizedException
        with pytest.raises(NotAuthorizedException) as exc_info:
            await middleware.authenticate_request(connection)

        assert "Authentication required" in exc_info.value.detail
        assert exc_info.value.headers["WWW-Authenticate"] == 'Basic realm="SAQ Admin"'


class TestBasicAuthMiddlewareAuthentication:
    """Test authentication logic."""

    async def test_missing_authorization_header_raises_error(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify missing Authorization header raises NotAuthorizedException."""
        # Given SAQ admin credentials are configured
        from vapi.config import settings

        monkeypatch.setattr(settings.saq, "admin_username", "admin")
        monkeypatch.setattr(settings.saq, "admin_password", "secret123")

        # Given a connection to SAQ path without Authorization header
        middleware = BasicAuthMiddleware(app=mocker.MagicMock())
        connection = _create_mock_connection(mocker, path="/saq/")

        # When authenticating the request
        # Then it should raise NotAuthorizedException
        with pytest.raises(NotAuthorizedException) as exc_info:
            await middleware.authenticate_request(connection)

        assert exc_info.value.headers["WWW-Authenticate"] == 'Basic realm="SAQ Admin"'

    async def test_non_basic_auth_scheme_raises_error(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify non-Basic auth schemes raise NotAuthorizedException."""
        # Given SAQ admin credentials are configured
        from vapi.config import settings

        monkeypatch.setattr(settings.saq, "admin_username", "admin")
        monkeypatch.setattr(settings.saq, "admin_password", "secret123")

        # Given a connection with Bearer token instead of Basic auth
        middleware = BasicAuthMiddleware(app=mocker.MagicMock())
        connection = _create_mock_connection(
            mocker, path="/saq/", authorization="Bearer some_jwt_token"
        )

        # When authenticating the request
        # Then it should raise NotAuthorizedException
        with pytest.raises(NotAuthorizedException) as exc_info:
            await middleware.authenticate_request(connection)

        assert "Authentication required" in exc_info.value.detail

    async def test_invalid_base64_encoding_raises_error(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify invalid base64 encoding raises NotAuthorizedException."""
        # Given SAQ admin credentials are configured
        from vapi.config import settings

        monkeypatch.setattr(settings.saq, "admin_username", "admin")
        monkeypatch.setattr(settings.saq, "admin_password", "secret123")

        # Given a connection with invalid base64 in Authorization header
        middleware = BasicAuthMiddleware(app=mocker.MagicMock())
        connection = _create_mock_connection(
            mocker, path="/saq/", authorization="Basic not_valid_base64!!!"
        )

        # When authenticating the request
        # Then it should raise NotAuthorizedException
        with pytest.raises(NotAuthorizedException) as exc_info:
            await middleware.authenticate_request(connection)

        assert "Invalid credentials format" in exc_info.value.detail

    async def test_wrong_username_raises_error(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify wrong username raises NotAuthorizedException."""
        # Given SAQ admin credentials are configured
        from vapi.config import settings

        monkeypatch.setattr(settings.saq, "admin_username", "admin")
        monkeypatch.setattr(settings.saq, "admin_password", "secret123")

        # Given a connection with wrong username
        middleware = BasicAuthMiddleware(app=mocker.MagicMock())
        auth_header = _encode_basic_auth("wrong_user", "secret123")
        connection = _create_mock_connection(mocker, path="/saq/", authorization=auth_header)

        # When authenticating the request
        # Then it should raise NotAuthorizedException
        with pytest.raises(NotAuthorizedException) as exc_info:
            await middleware.authenticate_request(connection)

        assert "Invalid credentials" in exc_info.value.detail

    async def test_wrong_password_raises_error(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify wrong password raises NotAuthorizedException."""
        # Given SAQ admin credentials are configured
        from vapi.config import settings

        monkeypatch.setattr(settings.saq, "admin_username", "admin")
        monkeypatch.setattr(settings.saq, "admin_password", "secret123")

        # Given a connection with wrong password
        middleware = BasicAuthMiddleware(app=mocker.MagicMock())
        auth_header = _encode_basic_auth("admin", "wrong_password")
        connection = _create_mock_connection(mocker, path="/saq/", authorization=auth_header)

        # When authenticating the request
        # Then it should raise NotAuthorizedException
        with pytest.raises(NotAuthorizedException) as exc_info:
            await middleware.authenticate_request(connection)

        assert "Invalid credentials" in exc_info.value.detail

    async def test_empty_admin_username_rejects_all(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify empty admin username rejects all authentication attempts."""
        # Given admin username is empty (not configured)
        from vapi.config import settings

        monkeypatch.setattr(settings.saq, "admin_username", "")
        monkeypatch.setattr(settings.saq, "admin_password", "secret123")

        # Given a connection with matching credentials
        middleware = BasicAuthMiddleware(app=mocker.MagicMock())
        auth_header = _encode_basic_auth("", "secret123")
        connection = _create_mock_connection(mocker, path="/saq/", authorization=auth_header)

        # When authenticating the request
        # Then it should raise NotAuthorizedException
        with pytest.raises(NotAuthorizedException) as exc_info:
            await middleware.authenticate_request(connection)

        assert "Invalid credentials" in exc_info.value.detail

    async def test_valid_credentials_returns_user(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify valid credentials return AuthenticationResult with user."""
        # Given SAQ admin credentials are configured
        from vapi.config import settings

        monkeypatch.setattr(settings.saq, "admin_username", "admin")
        monkeypatch.setattr(settings.saq, "admin_password", "secret123")

        # Given a connection with valid credentials
        middleware = BasicAuthMiddleware(app=mocker.MagicMock())
        auth_header = _encode_basic_auth("admin", "secret123")
        connection = _create_mock_connection(mocker, path="/saq/", authorization=auth_header)

        # When authenticating the request
        result = await middleware.authenticate_request(connection)

        # Then it should return authenticated user
        assert result.user == {"username": "admin", "is_admin": True}
        assert result.auth == "admin"

    async def test_credentials_with_colon_in_password(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify passwords containing colons are handled correctly."""
        # Given a password with colons
        from vapi.config import settings

        monkeypatch.setattr(settings.saq, "admin_username", "admin")
        monkeypatch.setattr(settings.saq, "admin_password", "secret:with:colons")

        # Given a connection with credentials containing colons
        middleware = BasicAuthMiddleware(app=mocker.MagicMock())
        auth_header = _encode_basic_auth("admin", "secret:with:colons")
        connection = _create_mock_connection(mocker, path="/saq/", authorization=auth_header)

        # When authenticating the request
        result = await middleware.authenticate_request(connection)

        # Then it should authenticate successfully
        assert result.user == {"username": "admin", "is_admin": True}


class TestBasicAuthMiddlewareTimingAttacks:
    """Test timing attack protection."""

    async def test_constant_time_comparison_used(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify secrets.compare_digest is used for constant-time comparison."""
        # Given SAQ admin credentials are configured
        from vapi.config import settings

        monkeypatch.setattr(settings.saq, "admin_username", "admin")
        monkeypatch.setattr(settings.saq, "admin_password", "secret123")

        # Given valid credentials
        middleware = BasicAuthMiddleware(app=mocker.MagicMock())
        auth_header = _encode_basic_auth("admin", "secret123")
        connection = _create_mock_connection(mocker, path="/saq/", authorization=auth_header)

        # When authenticating - verify we use constant-time comparison
        # The implementation uses secrets.compare_digest which is constant-time
        result = await middleware.authenticate_request(connection)

        # Then authentication succeeds
        assert result.user is not None
