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


async def add_audit_log(request: Request) -> None:
    """Create an audit log entry with both raw request data and structured fields."""
    request_body, request_json = await _parse_request_body(request)
    request_id = request.scope["state"].get(REQUEST_ID_STATE_KEY)

    structured = build_audit_entry(request, request_json)

    await AuditLog.create(
        developer_id=request.user.id,
        handler=request.route_handler.__str__(),
        handler_name=request.route_handler.handler_name,
        name=request.route_handler.name,
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
