"""After hooks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vapi.lib.stores import delete_response_cache_for_api_key

if TYPE_CHECKING:
    from litestar import Request


async def add_audit_log(request: Request) -> None:
    """Add an audit log."""
    from vapi.db.models import AuditLog

    content_type = request.headers.get("content-type", "")
    is_multipart = "multipart/form-data" in content_type

    # Skip body logging for file uploads - just note that it was a file upload
    if is_multipart:
        request_body = "[file upload]"
        request_json = None
    else:
        body_bytes = await request.body()
        request_body = body_bytes.decode("utf-8") if body_bytes else None
        request_json = await request.json()

    await AuditLog(
        developer_id=request.user.id,
        handler=request.route_handler.__str__(),
        handler_name=request.route_handler.handler_name,
        name=request.route_handler.name,
        summary=request.route_handler.summary,
        description=request.route_handler.description,
        operation_id=request.route_handler.operation_id,
        method=request.method,
        url=str(request.url),
        request_json=request_json,
        request_body=request_body,
        path_params=request.path_params,
        query_params=request.query_params,
    ).insert()


async def audit_log_and_delete_api_key_cache(request: Request) -> None:
    """Add an audit log and delete the response cache."""
    await add_audit_log(request)
    await delete_response_cache_for_api_key(request)
