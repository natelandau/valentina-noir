"""Unit tests for guard functions."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from beanie import PydanticObjectId
from litestar.serialization import encode_json

from vapi.constants import CompanyPermission, UserRole
from vapi.db.models.developer import CompanyPermissions
from vapi.lib.exceptions import ClientError, NotFoundError, PermissionDeniedError, ValidationError
from vapi.lib.guards import (
    _is_valid_character,
    _is_valid_company,
    developer_company_admin_guard,
    developer_company_owner_guard,
    developer_company_user_guard,
    global_admin_guard,
    user_admin_guard,
    user_character_player_or_storyteller_guard,
    user_json_from_store,
    user_storyteller_guard,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from vapi.db.models import Character, Company, Developer, User

pytestmark = pytest.mark.anyio


class TestGlobalAdminGuard:
    """Test global_admin_guard function."""

    async def test_passes_for_global_admin(
        self,
        base_developer_global_admin: Developer,
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify guard passes when user is a global admin."""
        # Given a connection with a global admin user
        mock_connection = mocker.MagicMock()
        mock_connection.user = base_developer_global_admin

        # When we call the guard
        # Then no exception is raised
        global_admin_guard(mock_connection, mocker.MagicMock())

    async def test_raises_permission_denied_for_non_admin(
        self,
        base_developer_company_owner: Developer,
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify guard raises PermissionDeniedError when user is not global admin."""
        # Given a connection with a non-global-admin user
        mock_connection = mocker.MagicMock()
        mock_connection.user = base_developer_company_owner

        # When/Then we expect a PermissionDeniedError
        with pytest.raises(PermissionDeniedError, match="No rights to access this resource"):
            global_admin_guard(mock_connection, mocker.MagicMock())


class TestIsValidCompany:
    """Test _is_valid_company helper function."""

    async def test_returns_company_when_valid(self, base_company: Company) -> None:
        """Verify returning company when it exists and is not archived."""
        # Given a valid company ID
        company_id = str(base_company.id)

        # When we validate the company
        result = await _is_valid_company(company_id)

        # Then the company is returned
        assert result.id == base_company.id

    async def test_raises_validation_error_when_empty_id(self) -> None:
        """Verify raising ValidationError when company ID is empty."""
        # Given an empty company ID
        company_id = ""

        # When/Then we expect a ValidationError
        with pytest.raises(ValidationError, match="Company ID is required"):
            await _is_valid_company(company_id)

    async def test_raises_not_found_when_company_not_exists(self) -> None:
        """Verify raising NotFoundError when company does not exist."""
        # Given a non-existent company ID
        company_id = str(PydanticObjectId())

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="not found"):
            await _is_valid_company(company_id)

    async def test_raises_not_found_when_company_archived(
        self, company_factory: Callable[..., Company]
    ) -> None:
        """Verify raising NotFoundError when company is archived."""
        # Given an archived company
        archived_company = await company_factory(is_archived=True)

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="not found"):
            await _is_valid_company(str(archived_company.id))


class TestIsValidCharacter:
    """Test _is_valid_character helper function."""

    async def test_returns_character_when_valid(self, base_character: Character) -> None:
        """Verify returning character when it exists and is not archived."""
        # Given a valid character ID
        character_id = str(base_character.id)

        # When we validate the character
        result = await _is_valid_character(character_id)

        # Then the character is returned
        assert result.id == base_character.id

    async def test_raises_validation_error_when_empty_id(self) -> None:
        """Verify raising ValidationError when character ID is empty."""
        # Given an empty character ID
        character_id = ""

        # When/Then we expect a ValidationError
        with pytest.raises(ValidationError, match="Character ID is required"):
            await _is_valid_character(character_id)

    async def test_raises_not_found_when_character_not_exists(self) -> None:
        """Verify raising NotFoundError when character does not exist."""
        # Given a non-existent character ID
        character_id = str(PydanticObjectId())

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="not found"):
            await _is_valid_character(character_id)

    async def test_raises_not_found_when_character_archived(
        self, character_factory: Callable[..., Character]
    ) -> None:
        """Verify raising NotFoundError when character is archived."""
        # Given an archived character
        archived_character = await character_factory(is_archived=True)

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="not found"):
            await _is_valid_character(str(archived_character.id))


class TestUserJsonFromStore:
    """Test user_json_from_store function."""

    async def test_returns_user_from_cache(
        self,
        base_user: User,
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify returning user from cache when available."""
        # Given a connection with user_id in path params
        mock_connection = mocker.MagicMock()
        mock_connection.path_params.get.return_value = str(base_user.id)

        # Given a mock store with cached user data
        mock_store = mocker.MagicMock()
        cached_user_data = encode_json(base_user.model_dump(mode="json"))
        mock_store.get = mocker.AsyncMock(return_value=cached_user_data)
        mock_connection.app.stores.get.return_value = mock_store

        # When we get the user from store
        result = await user_json_from_store(mock_connection)

        # Then the user is returned from cache
        assert result.id == base_user.id

    async def test_returns_user_from_db_when_not_cached(
        self,
        base_user: User,
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify returning user from database and caching when not in cache."""
        # Given a connection with user_id in path params
        mock_connection = mocker.MagicMock()
        mock_connection.path_params.get.return_value = str(base_user.id)

        # Given a mock store without cached data
        mock_store = mocker.MagicMock()
        mock_store.get = mocker.AsyncMock(return_value=None)
        mock_store.set = mocker.AsyncMock()
        mock_connection.app.stores.get.return_value = mock_store

        # When we get the user from store
        result = await user_json_from_store(mock_connection)

        # Then the user is returned from db and cached
        assert result.id == base_user.id
        mock_store.set.assert_called_once()

    async def test_raises_client_error_when_no_user_id(
        self,
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify raising ClientError when user_id is not in path params."""
        # Given a connection without user_id in path params
        mock_connection = mocker.MagicMock()
        mock_connection.path_params.get.return_value = None

        # When/Then we expect a ClientError
        with pytest.raises(ClientError, match="User ID is required"):
            await user_json_from_store(mock_connection)

    async def test_raises_client_error_when_user_not_found(
        self,
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify raising ClientError when user does not exist in database."""
        # Given a connection with non-existent user_id
        non_existent_id = PydanticObjectId()
        mock_connection = mocker.MagicMock()
        mock_connection.path_params.get.return_value = str(non_existent_id)

        # Given a mock store without cached data
        mock_store = mocker.MagicMock()
        mock_store.get = mocker.AsyncMock(return_value=None)
        mock_connection.app.stores.get.return_value = mock_store

        # When/Then we expect a ClientError
        with pytest.raises(ClientError, match="not found"):
            await user_json_from_store(mock_connection)


class TestDeveloperCompanyUserGuard:
    """Test developer_company_user_guard function."""

    async def test_passes_for_global_admin(
        self,
        base_company: Company,
        base_developer_global_admin: Developer,
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify guard passes for global admin regardless of company membership."""
        # Given a connection with global admin user
        mock_connection = mocker.MagicMock()
        mock_connection.user = base_developer_global_admin
        mock_connection.path_params.get.return_value = str(base_company.id)

        # When we call the guard
        # Then no exception is raised
        await developer_company_user_guard(mock_connection, mocker.MagicMock())

    async def test_passes_for_company_member(
        self,
        base_company: Company,
        base_developer_company_user: Developer,
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify guard passes for developer who is member of the company."""
        # Given a connection with company member user
        mock_connection = mocker.MagicMock()
        mock_connection.user = base_developer_company_user
        mock_connection.path_params.get.return_value = str(base_company.id)

        # When we call the guard
        # Then no exception is raised
        await developer_company_user_guard(mock_connection, mocker.MagicMock())

    async def test_raises_permission_denied_for_non_member(
        self,
        base_company: Company,
        developer_factory: Callable[..., Developer],
        company_factory: Callable[..., Company],
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify guard raises PermissionDeniedError for developer not in company."""
        # Given a developer belonging to a different company
        other_company = await company_factory()
        developer = await developer_factory(
            companies=[
                CompanyPermissions(
                    company_id=other_company.id,
                    name=other_company.name,
                    permission=CompanyPermission.USER,
                )
            ]
        )

        # Given a connection to base_company
        mock_connection = mocker.MagicMock()
        mock_connection.user = developer
        mock_connection.path_params.get.return_value = str(base_company.id)

        # When/Then we expect a PermissionDeniedError
        with pytest.raises(PermissionDeniedError, match="No rights to access this resource"):
            await developer_company_user_guard(mock_connection, mocker.MagicMock())


class TestDeveloperCompanyAdminGuard:
    """Test developer_company_admin_guard function."""

    async def test_passes_for_global_admin(
        self,
        base_company: Company,
        base_developer_global_admin: Developer,
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify guard passes for global admin."""
        # Given a connection with global admin user
        mock_connection = mocker.MagicMock()
        mock_connection.user = base_developer_global_admin
        mock_connection.path_params.get.return_value = str(base_company.id)

        # When we call the guard
        # Then no exception is raised
        await developer_company_admin_guard(mock_connection, mocker.MagicMock())

    async def test_passes_for_company_owner(
        self,
        base_company: Company,
        base_developer_company_owner: Developer,
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify guard passes for company owner."""
        # Given a connection with company owner
        mock_connection = mocker.MagicMock()
        mock_connection.user = base_developer_company_owner
        mock_connection.path_params.get.return_value = str(base_company.id)

        # When we call the guard
        # Then no exception is raised
        await developer_company_admin_guard(mock_connection, mocker.MagicMock())

    async def test_passes_for_company_admin(
        self,
        base_company: Company,
        base_developer_company_admin: Developer,
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify guard passes for company admin."""
        # Given a connection with company admin
        mock_connection = mocker.MagicMock()
        mock_connection.user = base_developer_company_admin
        mock_connection.path_params.get.return_value = str(base_company.id)

        # When we call the guard
        # Then no exception is raised
        await developer_company_admin_guard(mock_connection, mocker.MagicMock())

    async def test_raises_permission_denied_for_company_user(
        self,
        base_company: Company,
        base_developer_company_user: Developer,
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify guard raises PermissionDeniedError for company user (not admin)."""
        # Given a connection with company user (not admin)
        mock_connection = mocker.MagicMock()
        mock_connection.user = base_developer_company_user
        mock_connection.path_params.get.return_value = str(base_company.id)

        # When/Then we expect a PermissionDeniedError
        with pytest.raises(PermissionDeniedError, match="No rights to access this resource"):
            await developer_company_admin_guard(mock_connection, mocker.MagicMock())


class TestDeveloperCompanyOwnerGuard:
    """Test developer_company_owner_guard function."""

    async def test_passes_for_global_admin(
        self,
        base_company: Company,
        base_developer_global_admin: Developer,
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify guard passes for global admin."""
        # Given a connection with global admin user
        mock_connection = mocker.MagicMock()
        mock_connection.user = base_developer_global_admin
        mock_connection.path_params.get.return_value = str(base_company.id)

        # When we call the guard
        # Then no exception is raised
        await developer_company_owner_guard(mock_connection, mocker.MagicMock())

    async def test_passes_for_company_owner(
        self,
        base_company: Company,
        base_developer_company_owner: Developer,
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify guard passes for company owner."""
        # Given a connection with company owner
        mock_connection = mocker.MagicMock()
        mock_connection.user = base_developer_company_owner
        mock_connection.path_params.get.return_value = str(base_company.id)

        # When we call the guard
        # Then no exception is raised
        await developer_company_owner_guard(mock_connection, mocker.MagicMock())

    async def test_raises_permission_denied_for_company_admin(
        self,
        base_company: Company,
        base_developer_company_admin: Developer,
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify guard raises PermissionDeniedError for company admin (not owner)."""
        # Given a connection with company admin (not owner)
        mock_connection = mocker.MagicMock()
        mock_connection.user = base_developer_company_admin
        mock_connection.path_params.get.return_value = str(base_company.id)

        # When/Then we expect a PermissionDeniedError
        with pytest.raises(PermissionDeniedError, match="No rights to access this resource"):
            await developer_company_owner_guard(mock_connection, mocker.MagicMock())

    async def test_raises_permission_denied_for_company_user(
        self,
        base_company: Company,
        base_developer_company_user: Developer,
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify guard raises PermissionDeniedError for company user."""
        # Given a connection with company user
        mock_connection = mocker.MagicMock()
        mock_connection.user = base_developer_company_user
        mock_connection.path_params.get.return_value = str(base_company.id)

        # When/Then we expect a PermissionDeniedError
        with pytest.raises(PermissionDeniedError, match="No rights to access this resource"):
            await developer_company_owner_guard(mock_connection, mocker.MagicMock())


class TestUserStorytellerGuard:
    """Test user_storyteller_guard function."""

    async def test_passes_for_storyteller(
        self,
        base_company: Company,
        base_user_storyteller: User,
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify guard passes for user with storyteller role."""
        # Given a connection with storyteller user
        mock_connection = mocker.MagicMock()
        mock_connection.path_params.get.side_effect = lambda key: {
            "company_id": str(base_company.id),
            "user_id": str(base_user_storyteller.id),
        }.get(key)

        # Given a mock store with cached user data
        mock_store = mocker.MagicMock()
        cached_user_data = encode_json(base_user_storyteller.model_dump(mode="json"))
        mock_store.get = mocker.AsyncMock(return_value=cached_user_data)
        mock_connection.app.stores.get.return_value = mock_store

        # When we call the guard
        # Then no exception is raised
        await user_storyteller_guard(mock_connection, mocker.MagicMock())

    async def test_passes_for_admin(
        self,
        base_company: Company,
        base_user_admin: User,
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify guard passes for user with admin role."""
        # Given a connection with admin user
        mock_connection = mocker.MagicMock()
        mock_connection.path_params.get.side_effect = lambda key: {
            "company_id": str(base_company.id),
            "user_id": str(base_user_admin.id),
        }.get(key)

        # Given a mock store with cached user data
        mock_store = mocker.MagicMock()
        cached_user_data = encode_json(base_user_admin.model_dump(mode="json"))
        mock_store.get = mocker.AsyncMock(return_value=cached_user_data)
        mock_connection.app.stores.get.return_value = mock_store

        # When we call the guard
        # Then no exception is raised
        await user_storyteller_guard(mock_connection, mocker.MagicMock())

    async def test_raises_permission_denied_for_player(
        self,
        base_company: Company,
        base_user_player: User,
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify guard raises PermissionDeniedError for player role."""
        # Given a connection with player user
        mock_connection = mocker.MagicMock()
        mock_connection.path_params.get.side_effect = lambda key: {
            "company_id": str(base_company.id),
            "user_id": str(base_user_player.id),
        }.get(key)

        # Given a mock store with cached user data
        mock_store = mocker.MagicMock()
        cached_user_data = encode_json(base_user_player.model_dump(mode="json"))
        mock_store.get = mocker.AsyncMock(return_value=cached_user_data)
        mock_connection.app.stores.get.return_value = mock_store

        # When/Then we expect a PermissionDeniedError
        with pytest.raises(PermissionDeniedError):
            await user_storyteller_guard(mock_connection, mocker.MagicMock())

    async def test_raises_permission_denied_for_wrong_company(
        self,
        base_user_storyteller: User,
        company_factory: Callable[..., Company],
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify guard raises PermissionDeniedError when user belongs to different company."""
        # Given a different company
        other_company = await company_factory()

        # Given a connection with storyteller but for wrong company
        mock_connection = mocker.MagicMock()
        mock_connection.path_params.get.side_effect = lambda key: {
            "company_id": str(other_company.id),
            "user_id": str(base_user_storyteller.id),
        }.get(key)

        # Given a mock store with cached user data
        mock_store = mocker.MagicMock()
        cached_user_data = encode_json(base_user_storyteller.model_dump(mode="json"))
        mock_store.get = mocker.AsyncMock(return_value=cached_user_data)
        mock_connection.app.stores.get.return_value = mock_store

        # When/Then we expect a PermissionDeniedError
        with pytest.raises(PermissionDeniedError):
            await user_storyteller_guard(mock_connection, mocker.MagicMock())


class TestUserAdminGuard:
    """Test user_admin_guard function."""

    async def test_passes_for_admin(
        self,
        base_company: Company,
        base_user_admin: User,
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify guard passes for user with admin role."""
        # Given a connection with admin user
        mock_connection = mocker.MagicMock()
        mock_connection.path_params.get.side_effect = lambda key: {
            "company_id": str(base_company.id),
            "user_id": str(base_user_admin.id),
        }.get(key)

        # Given a mock store with cached user data
        mock_store = mocker.MagicMock()
        cached_user_data = encode_json(base_user_admin.model_dump(mode="json"))
        mock_store.get = mocker.AsyncMock(return_value=cached_user_data)
        mock_connection.app.stores.get.return_value = mock_store

        # When we call the guard
        # Then no exception is raised
        await user_admin_guard(mock_connection, mocker.MagicMock())

    async def test_raises_permission_denied_for_storyteller(
        self,
        base_company: Company,
        base_user_storyteller: User,
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify guard raises PermissionDeniedError for storyteller role."""
        # Given a connection with storyteller user
        mock_connection = mocker.MagicMock()
        mock_connection.path_params.get.side_effect = lambda key: {
            "company_id": str(base_company.id),
            "user_id": str(base_user_storyteller.id),
        }.get(key)

        # Given a mock store with cached user data
        mock_store = mocker.MagicMock()
        cached_user_data = encode_json(base_user_storyteller.model_dump(mode="json"))
        mock_store.get = mocker.AsyncMock(return_value=cached_user_data)
        mock_connection.app.stores.get.return_value = mock_store

        # When/Then we expect a PermissionDeniedError
        with pytest.raises(PermissionDeniedError):
            await user_admin_guard(mock_connection, mocker.MagicMock())

    async def test_raises_permission_denied_for_player(
        self,
        base_company: Company,
        base_user_player: User,
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify guard raises PermissionDeniedError for player role."""
        # Given a connection with player user
        mock_connection = mocker.MagicMock()
        mock_connection.path_params.get.side_effect = lambda key: {
            "company_id": str(base_company.id),
            "user_id": str(base_user_player.id),
        }.get(key)

        # Given a mock store with cached user data
        mock_store = mocker.MagicMock()
        cached_user_data = encode_json(base_user_player.model_dump(mode="json"))
        mock_store.get = mocker.AsyncMock(return_value=cached_user_data)
        mock_connection.app.stores.get.return_value = mock_store

        # When/Then we expect a PermissionDeniedError
        with pytest.raises(PermissionDeniedError):
            await user_admin_guard(mock_connection, mocker.MagicMock())


class TestUserCharacterPlayerOrStorytellerGuard:
    """Test user_character_player_or_storyteller_guard function."""

    async def test_passes_for_character_owner(
        self,
        base_company: Company,
        base_user: User,
        base_character: Character,
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify guard passes when user owns the character."""
        # Given a connection with character owner
        mock_connection = mocker.MagicMock()
        mock_connection.path_params.get.side_effect = lambda key: {
            "company_id": str(base_company.id),
            "user_id": str(base_user.id),
            "character_id": str(base_character.id),
        }.get(key)

        # Given a mock store with cached user data
        mock_store = mocker.MagicMock()
        cached_user_data = encode_json(base_user.model_dump(mode="json"))
        mock_store.get = mocker.AsyncMock(return_value=cached_user_data)
        mock_connection.app.stores.get.return_value = mock_store

        # When we call the guard
        # Then no exception is raised
        await user_character_player_or_storyteller_guard(mock_connection, mocker.MagicMock())

    async def test_passes_for_storyteller(
        self,
        base_company: Company,
        base_user_storyteller: User,
        base_character: Character,
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify guard passes for storyteller even if not character owner."""
        # Given a connection with storyteller (not character owner)
        mock_connection = mocker.MagicMock()
        mock_connection.path_params.get.side_effect = lambda key: {
            "company_id": str(base_company.id),
            "user_id": str(base_user_storyteller.id),
            "character_id": str(base_character.id),
        }.get(key)

        # Given a mock store with cached user data
        mock_store = mocker.MagicMock()
        cached_user_data = encode_json(base_user_storyteller.model_dump(mode="json"))
        mock_store.get = mocker.AsyncMock(return_value=cached_user_data)
        mock_connection.app.stores.get.return_value = mock_store

        # When we call the guard
        # Then no exception is raised
        await user_character_player_or_storyteller_guard(mock_connection, mocker.MagicMock())

    async def test_passes_for_admin(
        self,
        base_company: Company,
        base_user_admin: User,
        base_character: Character,
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify guard passes for admin even if not character owner."""
        # Given a connection with admin (not character owner)
        mock_connection = mocker.MagicMock()
        mock_connection.path_params.get.side_effect = lambda key: {
            "company_id": str(base_company.id),
            "user_id": str(base_user_admin.id),
            "character_id": str(base_character.id),
        }.get(key)

        # Given a mock store with cached user data
        mock_store = mocker.MagicMock()
        cached_user_data = encode_json(base_user_admin.model_dump(mode="json"))
        mock_store.get = mocker.AsyncMock(return_value=cached_user_data)
        mock_connection.app.stores.get.return_value = mock_store

        # When we call the guard
        # Then no exception is raised
        await user_character_player_or_storyteller_guard(mock_connection, mocker.MagicMock())

    async def test_raises_permission_denied_for_other_player(
        self,
        base_company: Company,
        base_character: Character,
        user_factory: Callable[..., User],
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify guard raises PermissionDeniedError for player who does not own character."""
        # Given a different player user who does not own the character
        other_player = await user_factory(role=UserRole.PLAYER)

        # Given a connection with other player
        mock_connection = mocker.MagicMock()
        mock_connection.path_params.get.side_effect = lambda key: {
            "company_id": str(base_company.id),
            "user_id": str(other_player.id),
            "character_id": str(base_character.id),
        }.get(key)

        # Given a mock store with cached user data
        mock_store = mocker.MagicMock()
        cached_user_data = encode_json(other_player.model_dump(mode="json"))
        mock_store.get = mocker.AsyncMock(return_value=cached_user_data)
        mock_connection.app.stores.get.return_value = mock_store

        # When/Then we expect a PermissionDeniedError
        with pytest.raises(PermissionDeniedError):
            await user_character_player_or_storyteller_guard(mock_connection, mocker.MagicMock())

    async def test_raises_client_error_when_no_character_id(
        self,
        base_company: Company,
        base_user: User,
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify guard raises ClientError when character_id is not in path params."""
        # Given a connection without character_id
        mock_connection = mocker.MagicMock()
        mock_connection.path_params.get.side_effect = lambda key: {
            "company_id": str(base_company.id),
            "user_id": str(base_user.id),
        }.get(key)

        # When/Then we expect a ClientError
        with pytest.raises(ClientError, match="Character ID is required"):
            await user_character_player_or_storyteller_guard(mock_connection, mocker.MagicMock())

    async def test_raises_not_found_when_character_not_exists(
        self,
        base_company: Company,
        base_user: User,
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify guard raises NotFoundError when character does not exist."""
        # Given a non-existent character ID
        non_existent_id = PydanticObjectId()

        # Given a connection with non-existent character
        mock_connection = mocker.MagicMock()
        mock_connection.path_params.get.side_effect = lambda key: {
            "company_id": str(base_company.id),
            "user_id": str(base_user.id),
            "character_id": str(non_existent_id),
        }.get(key)

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="not found"):
            await user_character_player_or_storyteller_guard(mock_connection, mocker.MagicMock())

    async def test_raises_not_found_when_character_archived(
        self,
        base_company: Company,
        base_user: User,
        character_factory: Callable[..., Character],
        mocker: pytest.MockerFixture,
    ) -> None:
        """Verify guard raises NotFoundError when character is archived."""
        # Given an archived character
        archived_character = await character_factory(is_archived=True)

        # Given a connection with archived character
        mock_connection = mocker.MagicMock()
        mock_connection.path_params.get.side_effect = lambda key: {
            "company_id": str(base_company.id),
            "user_id": str(base_user.id),
            "character_id": str(archived_character.id),
        }.get(key)

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="not found"):
            await user_character_player_or_storyteller_guard(mock_connection, mocker.MagicMock())
