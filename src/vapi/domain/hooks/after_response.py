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

Each named key anywhere in the parsed request JSON, including inside nested
objects and arrays, will have its value replaced with "[REDACTED]" before the
entry is written.

A route without a ``company_id`` path parameter that changes a company's
resources (e.g. a global-admin user edit) names that company so its cached
responses are flushed and its timestamp is bumped:

    request.state.affected_company_id = user.company_id

A mutating endpoint that did not actually change client-visible resources can
suppress the response-cache flush and the company timestamp bump (but not the
audit entry) by setting:

    request.state.resources_unmodified = True
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

from vapi.constants import AUDIT_MAX_BODY_BYTES, REQUEST_ID_STATE_KEY
from vapi.db.sql_models.audit_log import AuditLog
from vapi.db.sql_models.company import Company
from vapi.domain.hooks.audit_helpers import build_audit_entry
from vapi.lib.stores import (
    delete_response_cache_for_api_key,
    delete_response_cache_for_company,
)
from vapi.utils.time import time_now

if TYPE_CHECKING:
    from litestar import Request

# Fields always redacted from persisted request bodies regardless of per-endpoint configuration.
# Endpoints may extend this via ``request.state.audit_redact_fields`` for additional fields.
_DEFAULT_REDACT_FIELDS: frozenset[str] = frozenset({"token", "password", "secret", "api_key"})


async def _parse_request_body(request: Request) -> tuple[str | None, Any]:
    """Extract raw request body and parsed JSON from the request."""
    content_type = request.headers.get("content-type", "")
    is_multipart = "multipart/form-data" in content_type

    if is_multipart:
        return "[file upload]", None

    body_bytes = await request.body()
    if not body_bytes:
        return None, None

    try:
        request_body = body_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return body_bytes.decode("utf-8", errors="replace"), None

    try:
        request_json = json.loads(request_body)
    except ValueError:
        request_json = None

    return request_body, request_json


def _sanitize_value(value: Any, redact_fields: frozenset[str]) -> Any:
    """Return a copy of a parsed JSON value with sensitive keys redacted and NULs replaced.

    PostgreSQL text and jsonb columns reject NUL, so one left in a field the endpoint
    ignores would fail the audit insert and leave the request unlogged.
    """
    if isinstance(value, str):
        return value.replace("\x00", "\ufffd")
    if isinstance(value, dict):
        return {
            _sanitize_value(k, redact_fields): "[REDACTED]"
            if k in redact_fields
            else _sanitize_value(v, redact_fields)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_value(item, redact_fields) for item in value]
    return value


def _sanitize_body(
    request_body: str | None,
    request_json: Any,
    redact_fields: frozenset[str],
) -> tuple[str | None, Any]:
    """Redact sensitive keys and replace NUL characters in the persisted request body.

    Use when a request body contains credentials (e.g. provider tokens) that must
    not be stored in the audit log. Keys are matched at every depth, inside nested
    objects and arrays alike.

    Args:
        request_body: Raw request body string.
        request_json: Parsed request JSON, or None if not JSON.
        redact_fields: Key names whose values to redact.

    Returns:
        Tuple of (sanitized_body, sanitized_json).
    """
    if request_json is None:
        if request_body is None:
            return None, None
        return request_body.replace("\x00", "\ufffd"), None

    sanitized_json = _sanitize_value(request_json, redact_fields)
    if sanitized_json == request_json:
        return request_body, request_json
    # Re-serialize so request_body stays consistent with request_json
    return json.dumps(sanitized_json), sanitized_json


def _cap_request_body(request_body: str | None, request_json: Any) -> tuple[str | None, Any]:
    """Replace a body over the audit size budget with its length and SHA-256 hash.

    Run after redaction so the hash is of the redacted body and cannot confirm a guessed secret.

    Args:
        request_body: Request body text, already redacted.
        request_json: Parsed request JSON, already redacted.

    Returns:
        Tuple of (body, json): unchanged when within budget, else a summary string and None.
    """
    if request_body is None:
        return request_body, request_json

    body_bytes = request_body.encode("utf-8")
    if len(body_bytes) <= AUDIT_MAX_BODY_BYTES:
        return request_body, request_json

    digest = hashlib.sha256(body_bytes).hexdigest()
    return f"[truncated: {len(body_bytes)} bytes, sha256={digest}]", None


async def add_audit_log(request: Request) -> None:
    """Create an audit log entry with both raw request data and structured fields."""
    request_body, request_json = await _parse_request_body(request)

    per_request: list[str] = getattr(request.state, "audit_redact_fields", None) or []
    # Always merge per-request fields with the module-level defaults so sensitive
    # fields are redacted even when a controller doesn't set audit_redact_fields.
    request_body, request_json = _sanitize_body(
        request_body=request_body,
        request_json=request_json,
        redact_fields=_DEFAULT_REDACT_FIELDS | set(per_request),
    )
    request_body, request_json = _cap_request_body(request_body, request_json)

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
        path_params=_sanitize_value(request.path_params, frozenset()),
        query_params=_sanitize_value(dict(request.query_params), frozenset()),
        request_id=request_id,
        **structured,
    )


async def post_data_update_hook(request: Request) -> None:
    """Create an audit log, invalidate response cache, and update company timestamp."""
    # The mutation is already committed, so a failed audit insert must not leave
    # caches and the staleness timestamp out of date.
    try:
        await add_audit_log(request)
    finally:
        await _invalidate_after_mutation(request)


async def _invalidate_after_mutation(request: Request) -> None:
    """Flush cached responses and bump the company timestamp after a mutation."""
    # A mutating endpoint that left client-visible resources unchanged (e.g. a
    # matched login through identify) sets this flag so a routine request does not
    # flush the developer's entire response cache or bump the company timestamp.
    # The audit entry is always written regardless.
    if getattr(request.state, "resources_unmodified", False):
        return

    await delete_response_cache_for_api_key(request)
    company_id = request.path_params.get("company_id") or getattr(
        request.state, "affected_company_id", None
    )
    if company_id:
        await delete_response_cache_for_company(request, str(company_id))
        await Company.filter(id=company_id).update(resources_modified_at=time_now())
