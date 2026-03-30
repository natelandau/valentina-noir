"""Unit tests for SAQ settings validation."""

from __future__ import annotations

import pytest

from vapi.config.base import SAQSettings


class TestSAQCredentialValidation:
    """Tests for SAQ admin credential validation."""

    def test_web_enabled_without_username_raises(self) -> None:
        """Verify validation fails when web_enabled is True but admin_username is None."""
        # Given SAQ settings with web_enabled but no username
        saq = SAQSettings(web_enabled=True, admin_password="secret")  # noqa: S106

        # When validating credentials
        # Then a ValueError is raised
        with pytest.raises(ValueError, match="admin_username and admin_password must be set"):
            saq.validate_web_credentials()

    def test_web_enabled_without_password_raises(self) -> None:
        """Verify validation fails when web_enabled is True but admin_password is None."""
        # Given SAQ settings with web_enabled but no password
        saq = SAQSettings(web_enabled=True, admin_username="admin")

        # When validating credentials
        # Then a ValueError is raised
        with pytest.raises(ValueError, match="admin_username and admin_password must be set"):
            saq.validate_web_credentials()

    def test_web_enabled_without_both_credentials_raises(self) -> None:
        """Verify validation fails when web_enabled is True but both credentials are None."""
        # Given SAQ settings with web_enabled but no credentials
        saq = SAQSettings(web_enabled=True)

        # When validating credentials
        # Then a ValueError is raised
        with pytest.raises(ValueError, match="admin_username and admin_password must be set"):
            saq.validate_web_credentials()

    def test_web_enabled_with_credentials_succeeds(self) -> None:
        """Verify validation passes when web_enabled is True with both credentials set."""
        # Given SAQ settings with web_enabled and valid credentials
        saq = SAQSettings(web_enabled=True, admin_username="admin", admin_password="secret")  # noqa: S106

        # When validating credentials
        # Then no exception is raised
        saq.validate_web_credentials()
        assert saq.admin_username == "admin"
        assert saq.admin_password == "secret"  # noqa: S105

    def test_web_disabled_without_credentials_succeeds(self) -> None:
        """Verify validation passes when web_enabled is False without credentials."""
        # Given SAQ settings with web_enabled=False and no credentials
        saq = SAQSettings()

        # When validating credentials
        # Then no exception is raised
        saq.validate_web_credentials()
        assert saq.admin_username is None
        assert saq.admin_password is None

    def test_web_disabled_is_default(self) -> None:
        """Verify web_enabled defaults to False."""
        # Given default SAQSettings
        saq = SAQSettings()

        # Then web_enabled is False
        assert saq.web_enabled is False
