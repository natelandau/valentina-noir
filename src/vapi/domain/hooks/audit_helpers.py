"""Audit log entry builder — derives structured fields from request context.

This module contains the core logic for populating structured audit log fields
(entity_type, operation, FK columns, description, changes) from Litestar request
objects. It is designed to be testable independently of the HTTP lifecycle.

Architecture:
    build_audit_entry(request) -> dict
        Inspects path_params, HTTP method, and operation_id to produce a dict of
        field values ready for AuditLog.create(). Called by post_data_update_hook.

Populating custom descriptions and change tracking:
    Controllers can optionally enrich audit entries by setting attributes on
    request.state before the response returns:

        request.state.audit_description = "Sofia updated trait 'Strength' from 2 to 3"
        request.state.audit_changes = {"value": {"old": 2, "new": 3}}

    - audit_description (str): Overrides the auto-generated human-readable description.
    - audit_changes (dict): Saved to the `changes` JSONB column. Format:
      {"field_name": {"old": old_value, "new": new_value}}

    Both are optional and independent. Endpoints that set neither still get a useful
    auto-generated description and null changes.

Adding new entity types:
    1. Add the value to AuditEntityType in constants.py.
    2. If the entity has its own path param (e.g., "widget_id"), add an entry to
       PARAM_ENTITY_MAP in this module.
    3. If the entity is only created via POST to a parent URL (no ID in path), add
       an entry to OPERATION_ID_ENTITY_MAP.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from vapi.constants import AuditEntityType, AuditOperation

if TYPE_CHECKING:
    from litestar import Request

# Ordered from most specific (deepest) to least specific.
# The first match in path_params determines entity_type and target_entity_id.
# (path_param_key, entity_type, fk_field_name or None for generic-only)
PARAM_ENTITY_MAP: list[tuple[str, AuditEntityType, str | None]] = [
    ("inventory_item_id", AuditEntityType.CHARACTER_INVENTORY, None),
    ("character_trait_id", AuditEntityType.CHARACTER_TRAIT, None),
    ("quickroll_id", AuditEntityType.QUICKROLL, None),
    ("note_id", AuditEntityType.NOTE, None),
    ("asset_id", AuditEntityType.ASSET, None),
    ("session_id", AuditEntityType.CHARGEN_SESSION, None),
    ("dictionary_term_id", AuditEntityType.DICTIONARY_TERM, None),
    ("character_id", AuditEntityType.CHARACTER, "character_id"),
    ("chapter_id", AuditEntityType.CHAPTER, "chapter_id"),
    ("book_id", AuditEntityType.BOOK, "book_id"),
    ("campaign_id", AuditEntityType.CAMPAIGN, "campaign_id"),
    ("user_id", AuditEntityType.USER, "user_id"),
    ("company_id", AuditEntityType.COMPANY, "company_id"),
    ("developer_id", AuditEntityType.DEVELOPER, None),
]

# Derived from PARAM_ENTITY_MAP: path param keys that have a direct FK on AuditLog
_FK_PARAM_KEYS: dict[str, str] = {pk: fk for pk, _, fk in PARAM_ENTITY_MAP if fk is not None}

# Maps operation_id to entity type for POST (create) requests where the deepest
# path param is a parent, not the target being created.
OPERATION_ID_ENTITY_MAP: dict[str, AuditEntityType] = {
    "createUser": AuditEntityType.USER,
    "registerUser": AuditEntityType.USER,
    "mergeUsers": AuditEntityType.USER,
    "approveUser": AuditEntityType.USER,
    "denyUser": AuditEntityType.USER,
    "createCampaign": AuditEntityType.CAMPAIGN,
    "createCampaignBook": AuditEntityType.BOOK,
    "createCampaignChapter": AuditEntityType.CHAPTER,
    "createCharacter": AuditEntityType.CHARACTER,
    "autogenerateCharacter": AuditEntityType.CHARACTER,
    "startChargenSession": AuditEntityType.CHARGEN_SESSION,
    "finalizeChargenSession": AuditEntityType.CHARACTER,
    "createCustomTrait": AuditEntityType.CHARACTER_TRAIT,
    "assignTraitToCharacter": AuditEntityType.CHARACTER_TRAIT,
    "bulkAssignTraitsToCharacter": AuditEntityType.CHARACTER_TRAIT,
    "createCharacterInventoryItem": AuditEntityType.CHARACTER_INVENTORY,
    "createDictionaryTerm": AuditEntityType.DICTIONARY_TERM,
    "createCampaignNote": AuditEntityType.NOTE,
    "createUserNote": AuditEntityType.NOTE,
    "createBookNote": AuditEntityType.NOTE,
    "createChapterNote": AuditEntityType.NOTE,
    "createCharacterNote": AuditEntityType.NOTE,
    "createUserQuickroll": AuditEntityType.QUICKROLL,
    "addXp": AuditEntityType.EXPERIENCE,
    "removeXp": AuditEntityType.EXPERIENCE,
    "addCpToCampaignExperience": AuditEntityType.EXPERIENCE,
    "createCompany": AuditEntityType.COMPANY,
    "globalAdminCreateDeveloper": AuditEntityType.DEVELOPER,
}

# operation_ids that are POST but semantically UPDATE
_POST_AS_UPDATE: frozenset[str] = frozenset(
    {
        "addXp",
        "removeXp",
        "addCp",
        "approveUser",
        "denyUser",
        "mergeUsers",
        "bulkAssignCharacterTraits",
    }
)

_METHOD_TO_OPERATION: dict[str, AuditOperation] = {
    "POST": AuditOperation.CREATE,
    "PUT": AuditOperation.UPDATE,
    "PATCH": AuditOperation.UPDATE,
    "DELETE": AuditOperation.DELETE,
}


def _resolve_operation(method: str, operation_id: str | None) -> AuditOperation | None:
    """Derive audit operation from HTTP method, with operation_id overrides."""
    if operation_id and operation_id in _POST_AS_UPDATE:
        return AuditOperation.UPDATE
    return _METHOD_TO_OPERATION.get(method)


def _resolve_entity_and_fks(
    path_params: dict[str, str],
    method: str,
    operation_id: str | None,
) -> tuple[AuditEntityType | None, str | None, dict[str, str]]:
    """Derive entity_type, target_entity_id, and FK values from path params.

    Returns:
        (entity_type, target_entity_id, fk_dict) where fk_dict maps FK column
        names to their values from path_params.
    """
    fk_values: dict[str, str] = {}
    for param_key, fk_col in _FK_PARAM_KEYS.items():
        if param_key in path_params:
            fk_values[fk_col] = path_params[param_key]

    # Find the deepest (most specific) entity in path_params
    entity_type: AuditEntityType | None = None
    target_entity_id: str | None = None

    for param_key, etype, _fk_field in PARAM_ENTITY_MAP:
        if param_key in path_params:
            entity_type = etype
            target_entity_id = path_params[param_key]
            break

    # For POST requests, the deepest param may be a parent — disambiguate via operation_id
    if method == "POST" and operation_id and operation_id in OPERATION_ID_ENTITY_MAP:
        entity_type = OPERATION_ID_ENTITY_MAP[operation_id]
        # target_entity_id stays as the deepest path param (the parent's ID);
        # the created entity's ID isn't in the path for POST requests

    return entity_type, target_entity_id, fk_values


def _resolve_acting_user(
    request: Request,
    path_params: dict[str, str],
) -> str | None:
    """Derive the acting user ID from request state, header, or path params.

    Priority:
    1. request.state.acting_user (stashed by guards/provider)
    2. On-Behalf-Of header
    3. user_id path param (fallback for user-domain endpoints)
    """
    from vapi.constants import ON_BEHALF_OF_HEADER_KEY

    acting_user = getattr(request.state, "acting_user", None)
    if acting_user is not None:
        return str(acting_user.id)

    header_value = request.headers.get(ON_BEHALF_OF_HEADER_KEY)
    if header_value:
        return header_value

    if "user_id" in path_params:
        return path_params["user_id"]

    return None


def _jsonable(value: object) -> object:
    """Convert a value to a JSON-serializable type."""
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    return str(value)


def _serialize_changes(changes: dict[str, Any]) -> dict[str, Any]:
    """Ensure all values in a changes dict are JSON-serializable.

    Converts UUIDs to strings and enums to their values so the dict
    can be stored in a JSONField without serialization errors.
    """
    return {
        key: {"old": _jsonable(diff["old"]), "new": _jsonable(diff["new"])}
        for key, diff in changes.items()
    }


def build_audit_entry(
    request: Request,
) -> dict[str, Any]:
    """Build a dict of structured audit log field values from a request.

    Inspects path_params, HTTP method, and operation_id to populate entity_type,
    operation, FK columns, and description. Checks request.state for optional
    overrides (audit_description, audit_changes).

    Args:
        request: The Litestar request object.

    Returns:
        Dict of field name to value, ready to be unpacked into AuditLog.create().
    """
    path_params: dict[str, str] = request.path_params
    method: str = request.method
    # Litestar allows operation_id to be a callable; resolve to str if needed
    raw_op_id = request.route_handler.operation_id
    operation_id: str | None = raw_op_id if isinstance(raw_op_id, str) else None

    operation = _resolve_operation(method, operation_id)
    entity_type, target_entity_id, fk_values = _resolve_entity_and_fks(
        path_params, method, operation_id
    )
    acting_user_id = _resolve_acting_user(request, path_params)

    description: str | None = getattr(request.state, "audit_description", None)
    if description is None:
        parts: list[str] = []
        if operation:
            parts.append(operation.value.lower())
        if entity_type:
            parts.append(entity_type.value.lower().replace("_", " "))
        description = " ".join(parts) if parts else None

    changes: dict[str, Any] | None = getattr(request.state, "audit_changes", None)
    if changes is not None:
        changes = _serialize_changes(changes)

    return {
        "entity_type": entity_type,
        "operation": operation,
        "target_entity_id": target_entity_id,
        "description": description,
        "changes": changes,
        "acting_user_id": acting_user_id,
        **fk_values,
    }
