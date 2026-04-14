"""Unit tests for campaign guards."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from vapi.constants import PermissionManageCampaign, UserRole
from vapi.domain.controllers.campaign.guards import user_can_manage_campaign
from vapi.lib.exceptions import ClientError, NotFoundError, PermissionDeniedError

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from pytest_mock import MockerFixture

pytestmark = pytest.mark.anyio


def _mock_connection(
    mocker: MockerFixture,
    path_params: dict[str, str],
    headers: dict[str, str] | None = None,
) -> MagicMock:
    """Create a mock ASGIConnection with the given path params and headers."""
    connection = mocker.MagicMock()
    connection.path_params = path_params
    connection.headers = headers or {}
    connection.scope = {}
    return connection


def _mock_handler(mocker: MockerFixture) -> MagicMock:
    """Create a mock BaseRouteHandler."""
    return mocker.MagicMock()


class TestUserCanManageCampaignValidation:
    """Test input validation for user_can_manage_campaign guard."""

    async def test_missing_company_id_raises_client_error(self, mocker: MockerFixture) -> None:
        """Verify missing company_id raises ClientError."""
        # Given a connection without company_id
        connection = _mock_connection(
            mocker, path_params={}, headers={"On-Behalf-Of": str(uuid4())}
        )

        # When calling the guard
        # Then it raises ClientError
        with pytest.raises(ClientError, match="Company ID is required"):
            await user_can_manage_campaign(connection, _mock_handler(mocker))

    async def test_missing_user_id_raises_client_error(self, mocker: MockerFixture) -> None:
        """Verify missing user_id raises ClientError."""
        # Given a connection without On-Behalf-Of header
        connection = _mock_connection(mocker, path_params={"company_id": str(uuid4())})

        # When calling the guard
        # Then it raises ClientError
        with pytest.raises(ClientError, match="User ID is required"):
            await user_can_manage_campaign(connection, _mock_handler(mocker))


class TestUserCanManageCampaignLookup:
    """Test database lookup failures."""

    async def test_company_not_found_raises_not_found_error(self, mocker: MockerFixture) -> None:
        """Verify non-existent company raises NotFoundError."""
        # Given valid params but company doesn't exist
        company_id = str(uuid4())
        connection = _mock_connection(
            mocker,
            path_params={"company_id": company_id},
            headers={"On-Behalf-Of": str(uuid4())},
        )
        mocker.patch(
            "vapi.domain.controllers.campaign.guards.Company.filter",
            return_value=mocker.MagicMock(
                prefetch_related=mocker.MagicMock(
                    return_value=mocker.AsyncMock(first=mocker.AsyncMock(return_value=None))
                )
            ),
        )
        mocker.patch(
            "vapi.domain.controllers.campaign.guards.User.get_or_none",
            new=mocker.AsyncMock(return_value=mocker.MagicMock()),
        )

        # When calling the guard
        # Then it raises NotFoundError
        with pytest.raises(NotFoundError, match=company_id):
            await user_can_manage_campaign(connection, _mock_handler(mocker))

    async def test_user_not_found_raises_client_error(self, mocker: MockerFixture) -> None:
        """Verify non-existent user raises ClientError."""
        # Given valid params but user doesn't exist
        user_id = str(uuid4())
        mock_company = mocker.MagicMock()
        connection = _mock_connection(
            mocker,
            path_params={"company_id": str(uuid4())},
            headers={"On-Behalf-Of": user_id},
        )
        mocker.patch(
            "vapi.domain.controllers.campaign.guards.Company.filter",
            return_value=mocker.MagicMock(
                prefetch_related=mocker.MagicMock(
                    return_value=mocker.AsyncMock(first=mocker.AsyncMock(return_value=mock_company))
                )
            ),
        )
        mocker.patch(
            "vapi.domain.controllers.campaign.guards.User.get_or_none",
            new=mocker.AsyncMock(return_value=None),
        )

        # When calling the guard
        # Then it raises ClientError
        with pytest.raises(ClientError, match=user_id):
            await user_can_manage_campaign(connection, _mock_handler(mocker))


def _setup_db_mocks(
    mocker: MockerFixture,
    *,
    permission: PermissionManageCampaign,
    user_role: UserRole,
) -> tuple[MagicMock, MagicMock]:
    """Patch Company.filter and User.get_or_none, returning (mock_company, mock_user)."""
    mock_settings = mocker.MagicMock()
    mock_settings.permission_manage_campaign = permission

    mock_company = mocker.MagicMock()
    mock_company.settings = mock_settings

    mock_user = mocker.MagicMock()
    mock_user.role = user_role

    mocker.patch(
        "vapi.domain.controllers.campaign.guards.Company.filter",
        return_value=mocker.MagicMock(
            prefetch_related=mocker.MagicMock(
                return_value=mocker.AsyncMock(first=mocker.AsyncMock(return_value=mock_company))
            )
        ),
    )
    mocker.patch(
        "vapi.domain.controllers.campaign.guards.User.get_or_none",
        new=mocker.AsyncMock(return_value=mock_user),
    )
    return mock_company, mock_user


class TestUserCanManageCampaignUnrestricted:
    """Test UNRESTRICTED permission mode."""

    @pytest.mark.parametrize("role", list(UserRole))
    async def test_unrestricted_allows_any_role(
        self, role: UserRole, mocker: MockerFixture
    ) -> None:
        """Verify UNRESTRICTED permission allows all user roles."""
        # Given a company with UNRESTRICTED permission and a user with the given role
        connection = _mock_connection(
            mocker,
            path_params={"company_id": str(uuid4())},
            headers={"On-Behalf-Of": str(uuid4())},
        )
        _setup_db_mocks(mocker, permission=PermissionManageCampaign.UNRESTRICTED, user_role=role)

        # When calling the guard
        # Then it returns without raising
        await user_can_manage_campaign(connection, _mock_handler(mocker))


class TestUserCanManageCampaignStoryteller:
    """Test STORYTELLER permission mode."""

    @pytest.mark.parametrize("role", [UserRole.STORYTELLER, UserRole.ADMIN])
    async def test_storyteller_permission_allows_storyteller_and_admin(
        self, role: UserRole, mocker: MockerFixture
    ) -> None:
        """Verify STORYTELLER permission allows storyteller and admin roles."""
        # Given a company with STORYTELLER permission and a privileged user
        connection = _mock_connection(
            mocker,
            path_params={"company_id": str(uuid4())},
            headers={"On-Behalf-Of": str(uuid4())},
        )
        _setup_db_mocks(mocker, permission=PermissionManageCampaign.STORYTELLER, user_role=role)

        # When calling the guard
        # Then it returns without raising
        await user_can_manage_campaign(connection, _mock_handler(mocker))

    @pytest.mark.parametrize("role", [UserRole.PLAYER, UserRole.UNAPPROVED])
    async def test_storyteller_permission_denies_player_and_unapproved(
        self, role: UserRole, mocker: MockerFixture
    ) -> None:
        """Verify STORYTELLER permission denies player and unapproved roles."""
        # Given a company with STORYTELLER permission and an unprivileged user
        connection = _mock_connection(
            mocker,
            path_params={"company_id": str(uuid4())},
            headers={"On-Behalf-Of": str(uuid4())},
        )
        _setup_db_mocks(mocker, permission=PermissionManageCampaign.STORYTELLER, user_role=role)

        # When calling the guard
        # Then it raises PermissionDeniedError
        with pytest.raises(PermissionDeniedError, match="No rights to access this resource"):
            await user_can_manage_campaign(connection, _mock_handler(mocker))
