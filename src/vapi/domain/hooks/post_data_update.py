"""Post-write hook for audit logging, cache invalidation, and timestamp updates.

The app-level post_data_update_middleware runs post_data_update_hook for every
successful POST, PUT, PATCH, or DELETE, after the handler and before the response
starts, so a client that reads right after a write never gets a cached response the
write made stale. A route opts out with ``opt={SKIP_POST_DATA_UPDATE_OPT_KEY: True}``.
The hook:

1. Parses the request body
2. Calls build_audit_entry() to derive structured fields (entity_type, operation,
   FK columns, description, changes) from the request context
3. Creates the AuditLog row with both raw request data and structured fields
4. Invalidates the response cache for the developer's API key and the affected company
5. Updates the company's resources_modified_at timestamp after that flush

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

import asyncio
import hashlib
import logging
from typing import TYPE_CHECKING, Any

import msgspec
from litestar import Request
from litestar.enums import ScopeType
from litestar.handlers import HTTPRouteHandler
from litestar.middleware import ASGIMiddleware
from litestar.status_codes import HTTP_400_BAD_REQUEST

from vapi.constants import (
    AUDIT_MAX_BODY_BYTES,
    REQUEST_ID_STATE_KEY,
    SKIP_POST_DATA_UPDATE_OPT_KEY,
)
from vapi.db.sql_models.audit_log import AuditLog
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.developer import Developer
from vapi.domain.hooks.audit_helpers import build_audit_entry
from vapi.lib.redaction import sanitize_json
from vapi.lib.stores import (
    delete_response_cache_for_api_key,
    delete_response_cache_for_company,
)
from vapi.middleware.api_key_auth import CachedDeveloper
from vapi.utils.time import time_now

if TYPE_CHECKING:
    from litestar.types import ASGIApp, Message, Receive, Scope, Send

__all__ = ("add_audit_log", "post_data_update_middleware")

logger = logging.getLogger("vapi")


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
    # caches and the staleness timestamp out of date. The insert finishes before the
    # flush so a read between the two cannot cache an audit list missing this entry.
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

    company_id = request.path_params.get("company_id") or getattr(
        request.state, "affected_company_id", None
    )
    if not company_id:
        await delete_response_cache_for_api_key(request)
        return

    await asyncio.gather(
        delete_response_cache_for_api_key(request),
        delete_response_cache_for_company(request, str(company_id)),
    )
    # Bump only after the flush: a client that sees the new timestamp and refetches
    # must not be served a cached response this write made stale.
    await Company.filter(id=company_id).update(resources_modified_at=time_now())


_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class PostDataUpdateMiddleware(ASGIMiddleware):
    """Run post_data_update_hook on a successful write before its response starts."""

    scopes = (ScopeType.HTTP,)
    exclude_opt_key = SKIP_POST_DATA_UPDATE_OPT_KEY

    async def handle(self, scope: Scope, receive: Receive, send: Send, next_app: ASGIApp) -> None:
        """Hold the response start until the hook has run for a response below 400.

        Args:
            scope (Scope): The ASGI connection scope.
            receive (Receive): The ASGI receive function.
            send (Send): The ASGI send function.
            next_app (ASGIApp): The next ASGI application in the middleware stack to call.
        """
        # Only API-key callers are audited; basic-auth admin tools such as the SAQ UI are not.
        if (
            scope.get("method") not in _WRITE_METHODS
            or not isinstance(scope.get("route_handler"), HTTPRouteHandler)
            or not isinstance(scope.get("user"), Developer | CachedDeveloper)
        ):
            await next_app(scope, receive, send)
            return

        async def send_after_hook(message: Message) -> None:
            if (
                message["type"] == "http.response.start"
                and message["status"] < HTTP_400_BAD_REQUEST
            ):
                try:
                    await post_data_update_hook(Request(scope, receive))
                except Exception:
                    # The write is committed. An error response would invite a retry
                    # that repeats it, so log the failure and send the response.
                    logger.exception("Post-update hook failed")
            await send(message)

        await next_app(scope, receive, send_after_hook)


post_data_update_middleware = PostDataUpdateMiddleware()
