"""After-response hooks for audit logging, cache invalidation, and timestamp updates.

The post_data_update_hook is the primary hook wired to all mutating endpoints via
Litestar's after_response parameter. It:

1. Parses the request body
2. Calls build_audit_entry() to derive structured fields (entity_type, operation,
   FK columns, description, changes) from the request context
3. Creates the AuditLog row with both raw request data and structured fields
4. Invalidates the response cache for the developer's API key
5. Updates the company's resources_modified_at timestamp

Controllers do NOT need to pass any extra arguments — the hook derives everything
from path_params, HTTP method, and operation_id automatically.

To add custom descriptions or change tracking, set these in the controller before
the response returns:

    request.state.audit_description = "Sofia updated trait 'Strength' from 2 to 3"
    request.state.audit_changes = {"value": {"old": 2, "new": 3}}

To redact sensitive fields from the persisted request body, set this before
the response returns:

    request.state.audit_redact_fields = ["token", "password"]

Each named key at the top level of the parsed request JSON will have its value
replaced with "[REDACTED]" before the entry is written. Only top-level keys
are redacted; nested values are not traversed.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from vapi.constants import REQUEST_ID_STATE_KEY
from vapi.db.sql_models.audit_log import AuditLog
from vapi.db.sql_models.company import Company
from vapi.domain.hooks.audit_helpers import build_audit_entry
from vapi.lib.stores import delete_response_cache_for_api_key
from vapi.utils.time import time_now

if TYPE_CHECKING:
    from litestar import Request

# Fields always redacted from persisted request bodies regardless of per-endpoint configuration.
# Endpoints may extend this via ``request.state.audit_redact_fields`` for additional fields.
_DEFAULT_REDACT_FIELDS: frozenset[str] = frozenset({"token", "password", "secret", "api_key"})


async def _parse_request_body(request: Request) -> tuple[str | None, dict | None]:
    """Extract raw request body and parsed JSON from the request."""
    content_type = request.headers.get("content-type", "")
    is_multipart = "multipart/form-data" in content_type

    if is_multipart:
        return "[file upload]", None

    body_bytes = await request.body()
    if not body_bytes:
        return None, None

    request_body = body_bytes.decode("utf-8")
    try:
        request_json = json.loads(request_body)
    except (ValueError, UnicodeDecodeError):
        request_json = None

    return request_body, request_json


def _apply_redactions(
    request_body: str | None,
    request_json: dict | None,
    redact_fields: list[str],
) -> tuple[str | None, dict | None]:
    """Replace sensitive top-level keys in the persisted request body with [REDACTED].

    Use when a request body contains credentials (e.g. provider tokens) that must
    not be stored in the audit log. Only top-level keys are redacted; nested values
    are not traversed.

    Args:
        request_body: Raw request body string.
        request_json: Parsed request JSON dict, or None if not JSON.
        redact_fields: List of top-level key names whose values to redact.

    Returns:
        Tuple of (redacted_body, redacted_json).
    """
    # json.loads can yield non-dict bodies (e.g. bulk endpoints post arrays); only
    # dict bodies have top-level keys to redact
    if not redact_fields or not isinstance(request_json, dict):
        return request_body, request_json

    redacted_json = {k: "[REDACTED]" if k in redact_fields else v for k, v in request_json.items()}
    # Re-serialize so request_body stays consistent with request_json
    redacted_body = json.dumps(redacted_json)
    return redacted_body, redacted_json


async def add_audit_log(request: Request) -> None:
    """Create an audit log entry with both raw request data and structured fields."""
    request_body, request_json = await _parse_request_body(request)

    per_request: list[str] = getattr(request.state, "audit_redact_fields", None) or []
    # Always merge per-request fields with the module-level defaults so sensitive
    # fields are redacted even when a controller doesn't set audit_redact_fields.
    redact_fields: list[str] = list(_DEFAULT_REDACT_FIELDS | set(per_request))
    if redact_fields:
        request_body, request_json = _apply_redactions(
            request_body=request_body,
            request_json=request_json,
            redact_fields=redact_fields,
        )

    request_id = request.scope["state"].get(REQUEST_ID_STATE_KEY)

    structured = build_audit_entry(request)

    await AuditLog.create(
        developer_id=request.user.id,
        handler=request.route_handler.__str__(),
        handler_name=request.route_handler.handler_name,
        summary=request.route_handler.summary,
        operation_id=request.route_handler.operation_id,
        method=request.method,
        url=str(request.url),
        request_json=request_json,
        request_body=request_body,
        path_params=request.path_params,
        query_params=dict(request.query_params),
        request_id=request_id,
        **structured,
    )


async def post_data_update_hook(request: Request) -> None:
    """Create an audit log, invalidate response cache, and update company timestamp."""
    await add_audit_log(request)
    await delete_response_cache_for_api_key(request)
    if "company_id" in request.path_params:
        await Company.filter(id=request.path_params["company_id"]).update(
            resources_modified_at=time_now()
        )
