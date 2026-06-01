"""Unit tests for route guards."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from vapi.constants import PermissionManageCampaign, UserRole
from vapi.lib.exceptions import (
    ClientError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from vapi.lib.guards import (
    developer_company_user_guard,
    user_active_guard,
    user_can_manage_campaign,
    user_character_player_or_storyteller_guard,
)

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from pytest_mock import MockerFixture

pytestmark = pytest.mark.anyio


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------


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


def _mock_handler(mocker: MockerFixture, opt: dict[str, object] | None = None) -> MagicMock:
    """Create a mock route handler with the given opt dict."""
    handler = mocker.MagicMock()
    handler.opt = opt or {}
    return handler


def _patch_user(mocker: MockerFixture, user: MagicMock | None) -> None:
    """Patch User.filter(...).first() to return the given user."""
    mocker.patch(
        "vapi.lib.guards.User.filter",
        return_value=mocker.MagicMock(first=mocker.AsyncMock(return_value=user)),
    )


class TestUserActiveGuard:
    """Test user_active_guard role checks."""

    async def test_rejects_deactivated(self, mocker: MockerFixture) -> None:
        """Verify DEACTIVATED user is rejected with deactivated message."""
        # Given a deactivated user
        user_id = str(uuid4())
        user = mocker.MagicMock(role=UserRole.DEACTIVATED)
        _patch_user(mocker, user)
        connection = _mock_connection(mocker, {}, headers={"On-Behalf-Of": user_id})

        # When/Then the guard raises
        with pytest.raises(PermissionDeniedError, match="deactivated"):
            await user_active_guard(connection, _mock_handler(mocker))

    async def test_rejects_unapproved(self, mocker: MockerFixture) -> None:
        """Verify UNAPPROVED user is rejected with not been approved message."""
        # Given an unapproved user
        user_id = str(uuid4())
        user = mocker.MagicMock(role=UserRole.UNAPPROVED)
        _patch_user(mocker, user)
        connection = _mock_connection(mocker, {}, headers={"On-Behalf-Of": user_id})

        # When/Then the guard raises
        with pytest.raises(PermissionDeniedError, match="not been approved"):
            await user_active_guard(connection, _mock_handler(mocker))

    async def test_allows_unapproved_with_opt_flag(self, mocker: MockerFixture) -> None:
        """Verify handlers with allow_unapproved_user opt flag can act on UNAPPROVED users."""
        # Given an unapproved user and a handler that opts in to UNAPPROVED access
        user_id = str(uuid4())
        user = mocker.MagicMock(role=UserRole.UNAPPROVED)
        _patch_user(mocker, user)
        connection = _mock_connection(mocker, {}, headers={"On-Behalf-Of": user_id})
        handler = _mock_handler(mocker, {"allow_unapproved_user": True})

        # When calling the guard / Then no exception
        await user_active_guard(connection, handler)

    async def test_still_rejects_deactivated_with_opt_flag(self, mocker: MockerFixture) -> None:
        """Verify allow_unapproved_user opt flag does not bypass the DEACTIVATED check."""
        # Given a deactivated user and a handler that opts in to UNAPPROVED access
        user_id = str(uuid4())
        user = mocker.MagicMock(role=UserRole.DEACTIVATED)
        _patch_user(mocker, user)
        connection = _mock_connection(mocker, {}, headers={"On-Behalf-Of": user_id})
        handler = _mock_handler(mocker, {"allow_unapproved_user": True})

        # When/Then the guard still rejects
        with pytest.raises(PermissionDeniedError, match="deactivated"):
            await user_active_guard(connection, handler)

    async def test_allows_player(self, mocker: MockerFixture) -> None:
        """Verify PLAYER user passes the guard."""
        # Given a player user
        user_id = str(uuid4())
        user = mocker.MagicMock(role=UserRole.PLAYER)
        _patch_user(mocker, user)
        connection = _mock_connection(mocker, {}, headers={"On-Behalf-Of": user_id})

        # When calling the guard / Then no exception
        await user_active_guard(connection, _mock_handler(mocker))

    async def test_noop_when_no_header(self, mocker: MockerFixture) -> None:
        """Verify guard silently returns when On-Behalf-Of header is absent."""
        # Given a connection without On-Behalf-Of header
        connection = _mock_connection(mocker, {})

        # When calling the guard / Then no exception
        await user_active_guard(connection, _mock_handler(mocker))


class TestCharacterPlayerOrStorytellerGuard:
    """Test user_character_player_or_storyteller_guard role checks."""

    async def test_rejects_deactivated_owner(self, mocker: MockerFixture) -> None:
        """Verify deactivated owner cannot access their own character."""
        # Given a deactivated user who owns the character
        user_id = uuid4()
        character_id = uuid4()
        user = mocker.MagicMock(role=UserRole.DEACTIVATED, id=user_id)
        character = mocker.MagicMock(user_player_id=user_id)

        mocker.patch(
            "vapi.db.sql_models.character.Character.filter",
            return_value=mocker.MagicMock(first=mocker.AsyncMock(return_value=character)),
        )
        _patch_user(mocker, user)
        connection = _mock_connection(
            mocker,
            {"character_id": str(character_id)},
            headers={"On-Behalf-Of": str(user_id)},
        )

        # When/Then the guard raises
        with pytest.raises(PermissionDeniedError, match="No rights"):
            await user_character_player_or_storyteller_guard(connection, _mock_handler(mocker))

    async def test_missing_character_id_raises_validation_error(
        self, mocker: MockerFixture
    ) -> None:
        """Verify a missing character_id path param raises ValidationError."""
        # Given a connection without a character_id
        connection = _mock_connection(mocker, {}, headers={"On-Behalf-Of": str(uuid4())})

        # When/Then the guard raises
        with pytest.raises(ValidationError, match="Character ID is required"):
            await user_character_player_or_storyteller_guard(connection, _mock_handler(mocker))

    async def test_character_not_found_raises_not_found(self, mocker: MockerFixture) -> None:
        """Verify a non-existent character raises NotFoundError."""
        # Given a valid acting user but no matching character
        user_id = uuid4()
        character_id = uuid4()
        user = mocker.MagicMock(role=UserRole.PLAYER, id=user_id)
        mocker.patch(
            "vapi.db.sql_models.character.Character.filter",
            return_value=mocker.MagicMock(first=mocker.AsyncMock(return_value=None)),
        )
        _patch_user(mocker, user)
        connection = _mock_connection(
            mocker,
            {"character_id": str(character_id)},
            headers={"On-Behalf-Of": str(user_id)},
        )

        # When/Then the guard raises
        with pytest.raises(NotFoundError, match=str(character_id)):
            await user_character_player_or_storyteller_guard(connection, _mock_handler(mocker))

    async def test_player_who_is_not_owner_is_denied(self, mocker: MockerFixture) -> None:
        """Verify a player who does not own the character and lacks privilege is denied."""
        # Given a player acting on a character owned by someone else
        user_id = uuid4()
        owner_id = uuid4()
        character_id = uuid4()
        user = mocker.MagicMock(role=UserRole.PLAYER, id=user_id)
        character = mocker.MagicMock(user_player_id=owner_id)
        mocker.patch(
            "vapi.db.sql_models.character.Character.filter",
            return_value=mocker.MagicMock(first=mocker.AsyncMock(return_value=character)),
        )
        _patch_user(mocker, user)
        connection = _mock_connection(
            mocker,
            {"character_id": str(character_id)},
            headers={"On-Behalf-Of": str(user_id)},
        )

        # When/Then the guard raises
        with pytest.raises(PermissionDeniedError, match="No rights"):
            await user_character_player_or_storyteller_guard(connection, _mock_handler(mocker))

    async def test_player_who_owns_character_is_allowed(self, mocker: MockerFixture) -> None:
        """Verify a player who owns the character passes the guard."""
        # Given a player acting on their own character
        user_id = uuid4()
        character_id = uuid4()
        user = mocker.MagicMock(role=UserRole.PLAYER, id=user_id)
        character = mocker.MagicMock(user_player_id=user_id)
        mocker.patch(
            "vapi.db.sql_models.character.Character.filter",
            return_value=mocker.MagicMock(first=mocker.AsyncMock(return_value=character)),
        )
        _patch_user(mocker, user)
        connection = _mock_connection(
            mocker,
            {"character_id": str(character_id)},
            headers={"On-Behalf-Of": str(user_id)},
        )

        # When calling the guard / Then no exception is raised
        await user_character_player_or_storyteller_guard(connection, _mock_handler(mocker))

    async def test_player_less_character_denied_to_regular_player(
        self, mocker: MockerFixture
    ) -> None:
        """Verify a player-less character is denied to a non-storyteller user."""
        # Given a regular player acting on a character with no player (NPC/STORYTELLER type)
        user_id = uuid4()
        character_id = uuid4()
        user = mocker.MagicMock(role=UserRole.PLAYER, id=user_id)
        character = mocker.MagicMock(user_player_id=None)
        mocker.patch(
            "vapi.db.sql_models.character.Character.filter",
            return_value=mocker.MagicMock(first=mocker.AsyncMock(return_value=character)),
        )
        _patch_user(mocker, user)
        connection = _mock_connection(
            mocker,
            {"character_id": str(character_id)},
            headers={"On-Behalf-Of": str(user_id)},
        )

        # When/Then the guard raises because None != user.id and PLAYER is not a privileged role
        with pytest.raises(PermissionDeniedError, match="No rights"):
            await user_character_player_or_storyteller_guard(connection, _mock_handler(mocker))

    async def test_player_less_character_allowed_to_storyteller(
        self, mocker: MockerFixture
    ) -> None:
        """Verify a player-less character is accessible to a storyteller."""
        # Given a storyteller acting on a character with no player (NPC/STORYTELLER type)
        user_id = uuid4()
        character_id = uuid4()
        user = mocker.MagicMock(role=UserRole.STORYTELLER, id=user_id)
        character = mocker.MagicMock(user_player_id=None)
        mocker.patch(
            "vapi.db.sql_models.character.Character.filter",
            return_value=mocker.MagicMock(first=mocker.AsyncMock(return_value=character)),
        )
        _patch_user(mocker, user)
        connection = _mock_connection(
            mocker,
            {"character_id": str(character_id)},
            headers={"On-Behalf-Of": str(user_id)},
        )

        # When/Then the guard returns without raising because STORYTELLER bypasses the player check
        await user_character_player_or_storyteller_guard(connection, _mock_handler(mocker))


class TestDeveloperCompanyPermission:
    """Test developer company permission denial branches."""

    async def test_global_admin_bypasses_permission_check(self, mocker: MockerFixture) -> None:
        """Verify a global admin developer is allowed without a company permission lookup."""
        # Given a global-admin developer
        connection = _mock_connection(mocker, {"company_id": str(uuid4())})
        connection.user = mocker.MagicMock(is_global_admin=True, id=uuid4())

        # When calling the guard / Then no exception is raised
        await developer_company_user_guard(connection, _mock_handler(mocker))

    @pytest.mark.parametrize("company_id", ["not-a-uuid", None], ids=["malformed", "missing"])
    async def test_unparsable_company_id_is_denied(
        self, company_id: str | None, mocker: MockerFixture
    ) -> None:
        """Verify a malformed or missing company_id denies a non-admin developer."""
        # Given a non-admin developer and an unparsable company_id
        path_params = {"company_id": company_id} if company_id is not None else {}
        connection = _mock_connection(mocker, path_params)
        connection.user = mocker.MagicMock(is_global_admin=False, id=uuid4())

        # When/Then the guard raises
        with pytest.raises(PermissionDeniedError, match="No rights"):
            await developer_company_user_guard(connection, _mock_handler(mocker))


def _setup_campaign_db_mocks(
    mocker: MockerFixture,
    *,
    permission: PermissionManageCampaign,
    user_role: UserRole,
) -> tuple[MagicMock, MagicMock]:
    """Patch Company.filter and User.filter, returning (mock_company, mock_user)."""
    mock_settings = mocker.MagicMock()
    mock_settings.permission_manage_campaign = permission

    mock_company = mocker.MagicMock()
    mock_company.settings = mock_settings

    mock_user = mocker.MagicMock()
    mock_user.role = user_role

    mocker.patch(
        "vapi.lib.guards.Company.filter",
        return_value=mocker.MagicMock(
            prefetch_related=mocker.MagicMock(
                return_value=mocker.AsyncMock(first=mocker.AsyncMock(return_value=mock_company))
            )
        ),
    )
    _patch_user(mocker, mock_user)
    return mock_company, mock_user


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

    async def test_missing_on_behalf_of_header_raises_permission_denied(
        self, mocker: MockerFixture
    ) -> None:
        """Verify missing On-Behalf-Of header raises PermissionDeniedError."""
        # Given a connection without On-Behalf-Of header
        connection = _mock_connection(mocker, path_params={"company_id": str(uuid4())})

        # When calling the guard
        # Then it raises PermissionDeniedError
        with pytest.raises(PermissionDeniedError, match="On-Behalf-Of header is required"):
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
            "vapi.lib.guards.Company.filter",
            return_value=mocker.MagicMock(
                prefetch_related=mocker.MagicMock(
                    return_value=mocker.AsyncMock(first=mocker.AsyncMock(return_value=None))
                )
            ),
        )
        _patch_user(mocker, mocker.MagicMock())

        # When calling the guard
        # Then it raises NotFoundError
        with pytest.raises(NotFoundError, match=company_id):
            await user_can_manage_campaign(connection, _mock_handler(mocker))

    async def test_user_not_found_raises_not_found_error(self, mocker: MockerFixture) -> None:
        """Verify non-existent user raises NotFoundError."""
        # Given valid params but user doesn't exist
        user_id = str(uuid4())
        mock_company = mocker.MagicMock()
        connection = _mock_connection(
            mocker,
            path_params={"company_id": str(uuid4())},
            headers={"On-Behalf-Of": user_id},
        )
        mocker.patch(
            "vapi.lib.guards.Company.filter",
            return_value=mocker.MagicMock(
                prefetch_related=mocker.MagicMock(
                    return_value=mocker.AsyncMock(first=mocker.AsyncMock(return_value=mock_company))
                )
            ),
        )
        _patch_user(mocker, None)

        # When calling the guard
        # Then it raises NotFoundError
        with pytest.raises(NotFoundError, match=user_id):
            await user_can_manage_campaign(connection, _mock_handler(mocker))


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
        _setup_campaign_db_mocks(
            mocker, permission=PermissionManageCampaign.UNRESTRICTED, user_role=role
        )

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
        _setup_campaign_db_mocks(
            mocker, permission=PermissionManageCampaign.STORYTELLER, user_role=role
        )

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
        _setup_campaign_db_mocks(
            mocker, permission=PermissionManageCampaign.STORYTELLER, user_role=role
        )

        # When calling the guard
        # Then it raises PermissionDeniedError
        with pytest.raises(PermissionDeniedError, match="No rights to access this resource"):
            await user_can_manage_campaign(connection, _mock_handler(mocker))
