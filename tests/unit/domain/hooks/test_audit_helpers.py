"""Tests for the audit log entry builder."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

from vapi.constants import AuditEntityType, AuditOperation
from vapi.domain.hooks.audit_helpers import build_audit_entry


def _make_request(
    method: str = "POST",
    path_params: dict[str, str] | None = None,
    request_json: dict[str, Any] | None = None,
    operation_id: str | None = None,
    audit_description: str | None = None,
    audit_changes: dict[str, Any] | None = None,
) -> MagicMock:
    """Build a mock Litestar Request with the fields build_audit_entry reads."""
    request = MagicMock()
    request.method = method
    request.path_params = path_params or {}
    request.route_handler.operation_id = operation_id

    state = MagicMock()
    state.audit_description = audit_description
    state.audit_changes = audit_changes
    # getattr returns a Mock object instead of None for deleted attrs
    if audit_description is None:
        del state.audit_description
    if audit_changes is None:
        del state.audit_changes
    request.state = state

    request._parsed_json = request_json
    return request


class TestResolveOperation:
    """Test operation resolution from HTTP method."""

    def test_post_maps_to_create(self) -> None:
        """Verify POST method resolves to CREATE operation."""
        # Given a POST request to create a company
        company_id = str(uuid4())
        request = _make_request(
            method="POST",
            path_params={"company_id": company_id},
            operation_id="createCompany",
        )

        # When building the audit entry
        result = build_audit_entry(request, request_json=None)

        # Then the operation is CREATE
        assert result["operation"] == AuditOperation.CREATE

    def test_put_maps_to_update(self) -> None:
        """Verify PUT method resolves to UPDATE operation."""
        # Given a PUT request to update a company
        company_id = str(uuid4())
        request = _make_request(
            method="PUT",
            path_params={"company_id": company_id},
            operation_id="updateCompany",
        )

        # When building the audit entry
        result = build_audit_entry(request, request_json=None)

        # Then the operation is UPDATE
        assert result["operation"] == AuditOperation.UPDATE

    def test_patch_maps_to_update(self) -> None:
        """Verify PATCH method resolves to UPDATE operation."""
        # Given a PATCH request to update a company
        company_id = str(uuid4())
        request = _make_request(
            method="PATCH",
            path_params={"company_id": company_id},
            operation_id="updateCompany",
        )

        # When building the audit entry
        result = build_audit_entry(request, request_json=None)

        # Then the operation is UPDATE
        assert result["operation"] == AuditOperation.UPDATE

    def test_delete_maps_to_delete(self) -> None:
        """Verify DELETE method resolves to DELETE operation."""
        # Given a DELETE request to delete a company
        company_id = str(uuid4())
        request = _make_request(
            method="DELETE",
            path_params={"company_id": company_id},
            operation_id="deleteCompany",
        )

        # When building the audit entry
        result = build_audit_entry(request, request_json=None)

        # Then the operation is DELETE
        assert result["operation"] == AuditOperation.DELETE


class TestResolveEntityType:
    """Test entity type resolution from path params."""

    def test_company_endpoint(self) -> None:
        """Verify company_id path param resolves to COMPANY entity type."""
        # Given a PUT request targeting a company
        company_id = str(uuid4())
        request = _make_request(
            method="PUT",
            path_params={"company_id": company_id},
            operation_id="updateCompany",
        )

        # When building the audit entry
        result = build_audit_entry(request, request_json=None)

        # Then the entity type is COMPANY and FKs are populated
        assert result["entity_type"] == AuditEntityType.COMPANY
        assert result["company_id"] == company_id
        assert result["target_entity_id"] == company_id

    def test_character_trait_endpoint(self) -> None:
        """Verify deepest path param wins for entity type resolution."""
        # Given a PUT request with a full path hierarchy down to a character trait
        company_id = str(uuid4())
        user_id = str(uuid4())
        campaign_id = str(uuid4())
        character_id = str(uuid4())
        trait_id = str(uuid4())
        request = _make_request(
            method="PUT",
            path_params={
                "company_id": company_id,
                "user_id": user_id,
                "campaign_id": campaign_id,
                "character_id": character_id,
                "character_trait_id": trait_id,
            },
            operation_id="updateCharacterTrait",
        )

        # When building the audit entry
        result = build_audit_entry(request, request_json=None)

        # Then the entity type is CHARACTER_TRAIT and all ancestor FKs are populated
        assert result["entity_type"] == AuditEntityType.CHARACTER_TRAIT
        assert result["target_entity_id"] == trait_id
        assert result["company_id"] == company_id
        assert result["user_id"] == user_id
        assert result["campaign_id"] == campaign_id
        assert result["character_id"] == character_id

    def test_create_user_disambiguates_via_operation_id(self) -> None:
        """Verify POST to parent path uses operation_id to resolve entity type."""
        # Given a POST request to a company path with operation_id "createUser"
        company_id = str(uuid4())
        request = _make_request(
            method="POST",
            path_params={"company_id": company_id},
            operation_id="createUser",
        )

        # When building the audit entry
        result = build_audit_entry(request, request_json=None)

        # Then the entity type is USER, not COMPANY
        assert result["entity_type"] == AuditEntityType.USER


class TestActingUserResolution:
    """Test acting user ID resolution."""

    def test_requesting_user_id_from_body(self) -> None:
        """Verify requesting_user_id in body takes precedence over path user_id."""
        # Given a request with user_id in the path and requesting_user_id in the body
        company_id = str(uuid4())
        target_user_id = str(uuid4())
        acting_user_id = str(uuid4())
        request = _make_request(
            method="POST",
            path_params={"company_id": company_id, "user_id": target_user_id},
            operation_id="createUser",
        )

        # When building the audit entry with the body containing requesting_user_id
        result = build_audit_entry(request, request_json={"requesting_user_id": acting_user_id})

        # Then the acting_user_id comes from the body, not the path
        assert result["acting_user_id"] == acting_user_id

    def test_fallback_to_path_user_id(self) -> None:
        """Verify path user_id used as acting_user when no requesting_user_id in body."""
        # Given a request with user_id in the path and no requesting_user_id in the body
        company_id = str(uuid4())
        user_id = str(uuid4())
        campaign_id = str(uuid4())
        request = _make_request(
            method="POST",
            path_params={
                "company_id": company_id,
                "user_id": user_id,
                "campaign_id": campaign_id,
            },
            operation_id="createCampaign",
        )

        # When building the audit entry
        result = build_audit_entry(request, request_json=None)

        # Then the acting_user_id falls back to the path user_id
        assert result["acting_user_id"] == user_id

    def test_no_acting_user_for_developer_ops(self) -> None:
        """Verify acting_user_id is None for developer-level operations."""
        # Given a developer-level request with no user_id in path or body
        company_id = str(uuid4())
        request = _make_request(
            method="POST",
            path_params={"company_id": company_id},
            operation_id="createCompany",
        )

        # When building the audit entry
        result = build_audit_entry(request, request_json=None)

        # Then there is no acting user
        assert result["acting_user_id"] is None


class TestRequestStateOverrides:
    """Test request.state overrides for description and changes."""

    def test_audit_description_override(self) -> None:
        """Verify request.state.audit_description overrides auto-generated description."""
        # Given a request with a custom audit_description on request.state
        company_id = str(uuid4())
        request = _make_request(
            method="PUT",
            path_params={"company_id": company_id},
            operation_id="updateCompany",
            audit_description="Custom description for this update",
        )

        # When building the audit entry
        result = build_audit_entry(request, request_json=None)

        # Then the custom description is used instead of auto-generated
        assert result["description"] == "Custom description for this update"

    def test_audit_changes_passthrough(self) -> None:
        """Verify request.state.audit_changes is passed through to result."""
        # Given a request with structured change data on request.state
        company_id = str(uuid4())
        changes = {"name": {"old": "Old Corp", "new": "New Corp"}}
        request = _make_request(
            method="PUT",
            path_params={"company_id": company_id},
            operation_id="updateCompany",
            audit_changes=changes,
        )

        # When building the audit entry
        result = build_audit_entry(request, request_json=None)

        # Then the changes dict is passed through
        assert result["changes"] == changes

    def test_no_overrides_defaults_to_none(self) -> None:
        """Verify changes is None when no override is set."""
        # Given a request with no audit overrides on request.state
        company_id = str(uuid4())
        request = _make_request(
            method="PUT",
            path_params={"company_id": company_id},
            operation_id="updateCompany",
        )

        # When building the audit entry
        result = build_audit_entry(request, request_json=None)

        # Then changes is None
        assert result["changes"] is None


class TestAncestorFKPopulation:
    """Test that all ancestor FKs in the URL hierarchy are populated."""

    def test_character_populates_all_ancestors(self) -> None:
        """Verify character endpoint populates company, user, campaign FKs."""
        # Given a PUT request targeting a character with full ancestor path
        company_id = str(uuid4())
        user_id = str(uuid4())
        campaign_id = str(uuid4())
        character_id = str(uuid4())
        request = _make_request(
            method="PUT",
            path_params={
                "company_id": company_id,
                "user_id": user_id,
                "campaign_id": campaign_id,
                "character_id": character_id,
            },
            operation_id="updateCharacter",
        )

        # When building the audit entry
        result = build_audit_entry(request, request_json=None)

        # Then all ancestor FK columns are populated
        assert result["company_id"] == company_id
        assert result["user_id"] == user_id
        assert result["campaign_id"] == campaign_id
        assert result["character_id"] == character_id
        assert result["target_entity_id"] == character_id

    def test_note_on_chapter_populates_full_chain(self) -> None:
        """Verify note on chapter populates company, user, campaign, book, chapter FKs."""
        # Given a PUT request targeting a note nested under a chapter
        company_id = str(uuid4())
        user_id = str(uuid4())
        campaign_id = str(uuid4())
        book_id = str(uuid4())
        chapter_id = str(uuid4())
        note_id = str(uuid4())
        request = _make_request(
            method="PUT",
            path_params={
                "company_id": company_id,
                "user_id": user_id,
                "campaign_id": campaign_id,
                "book_id": book_id,
                "chapter_id": chapter_id,
                "note_id": note_id,
            },
            operation_id="updateChapterNote",
        )

        # When building the audit entry
        result = build_audit_entry(request, request_json=None)

        # Then the entity type is NOTE and the full ancestor chain is populated
        assert result["company_id"] == company_id
        assert result["user_id"] == user_id
        assert result["campaign_id"] == campaign_id
        assert result["book_id"] == book_id
        assert result["chapter_id"] == chapter_id
        assert result["entity_type"] == AuditEntityType.NOTE
        assert result["target_entity_id"] == note_id
