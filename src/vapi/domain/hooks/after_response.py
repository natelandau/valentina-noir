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

Every key in ``SENSITIVE_BODY_KEYS``, anywhere in the request JSON, path params,
or query params, has its value replaced with "[REDACTED]" before the entry is
written. A body that does not parse as JSON is not stored, since redaction
cannot see into it.

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
from typing import TYPE_CHECKING, Any

import msgspec

from vapi.constants import AUDIT_MAX_BODY_BYTES, REQUEST_ID_STATE_KEY
from vapi.db.sql_models.audit_log import AuditLog
from vapi.db.sql_models.company import Company
from vapi.domain.hooks.audit_helpers import build_audit_entry
from vapi.lib.redaction import sanitize_json
from vapi.lib.stores import (
    delete_response_cache_for_api_key,
    delete_response_cache_for_company,
)
from vapi.utils.time import time_now

if TYPE_CHECKING:
    from litestar import Request


async def _sanitized_request_body(request: Request) -> tuple[str | None, Any]:
    """Return the request body text and parsed JSON with credentials redacted.

    Parse with msgspec, as the handler did. A body that does not parse, or that nests
    deeper than the redaction walk can follow, is dropped rather than stored raw, where
    credentials would bypass redaction.

    Returns:
        Tuple of (body_text, parsed_json); both None when there is nothing safe to store.
    """
    if "multipart/form-data" in request.headers.get("content-type", ""):
        return "[file upload]", None

    body_bytes = await request.body()
    if not body_bytes:
        return None, None

    try:
        request_json = msgspec.json.decode(body_bytes)
        sanitized_json = sanitize_json(request_json, placeholder="[REDACTED]")
        if sanitized_json == request_json:
            return body_bytes.decode("utf-8"), request_json
        # Re-serialize so request_body stays consistent with request_json
        return msgspec.json.encode(sanitized_json).decode("utf-8"), sanitized_json
    # msgspec raises UnicodeDecodeError, not DecodeError, for invalid UTF-8 inside a string
    except (msgspec.DecodeError, UnicodeDecodeError, RecursionError):
        return None, None


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
    request_body, request_json = _cap_request_body(*await _sanitized_request_body(request))

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
        path_params=sanitize_json(request.path_params, placeholder="[REDACTED]"),
        query_params=sanitize_json(dict(request.query_params), placeholder="[REDACTED]"),
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
