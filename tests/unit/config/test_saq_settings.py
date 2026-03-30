"""Unit tests for SAQ settings validation."""

from __future__ import annotations

import pytest

from vapi.config.base import SAQSettings


class TestSAQCredentialValidation:
    """Tests for SAQ admin credential validation."""

    def test_web_enabled_without_username_raises(self) -> None:
        """Verify startup fails when web_enabled is True but admin_username is None."""
        # Given web_enabled is True with only a password set
        # When creating SAQSettings
        # Then a ValueError is raised
        with pytest.raises(ValueError, match="admin_username and admin_password must be set"):
            SAQSettings(web_enabled=True, admin_password="secret")  # noqa: S106

    def test_web_enabled_without_password_raises(self) -> None:
        """Verify startup fails when web_enabled is True but admin_password is None."""
        # Given web_enabled is True with only a username set
        # When creating SAQSettings
        # Then a ValueError is raised
        with pytest.raises(ValueError, match="admin_username and admin_password must be set"):
            SAQSettings(web_enabled=True, admin_username="admin")

    def test_web_enabled_without_both_credentials_raises(self) -> None:
        """Verify startup fails when web_enabled is True but both credentials are None."""
        # Given web_enabled is True with no credentials
        # When creating SAQSettings
        # Then a ValueError is raised
        with pytest.raises(ValueError, match="admin_username and admin_password must be set"):
            SAQSettings(web_enabled=True)

    def test_web_enabled_with_credentials_succeeds(self) -> None:
        """Verify startup succeeds when web_enabled is True with both credentials set."""
        # Given web_enabled is True with valid credentials
        # When creating SAQSettings
        settings = SAQSettings(web_enabled=True, admin_username="admin", admin_password="secret")  # noqa: S106

        # Then settings are created successfully
        assert settings.admin_username == "admin"
        assert settings.admin_password == "secret"  # noqa: S105

    def test_web_disabled_without_credentials_succeeds(self) -> None:
        """Verify startup succeeds when web_enabled is False without credentials."""
        # Given web_enabled is False (default) with no credentials
        # When creating SAQSettings
        settings = SAQSettings()

        # Then settings are created with None credentials
        assert settings.admin_username is None
        assert settings.admin_password is None

    def test_web_disabled_is_default(self) -> None:
        """Verify web_enabled defaults to False."""
        # Given default SAQSettings
        # When creating SAQSettings
        settings = SAQSettings()

        # Then web_enabled is False
        assert settings.web_enabled is False
