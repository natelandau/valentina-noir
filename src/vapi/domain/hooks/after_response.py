"""After hooks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vapi.constants import REQUEST_ID_STATE_KEY
from vapi.db.sql_models.audit_log import AuditLog
from vapi.db.sql_models.company import Company
from vapi.lib.stores import delete_response_cache_for_api_key
from vapi.utils.time import time_now

if TYPE_CHECKING:
    from litestar import Request


async def add_audit_log(request: Request) -> None:
    """Add an audit log."""
    content_type = request.headers.get("content-type", "")
    is_multipart = "multipart/form-data" in content_type

    if is_multipart:
        request_body = "[file upload]"
        request_json = None
    else:
        body_bytes = await request.body()
        if body_bytes:
            request_body = body_bytes.decode("utf-8")
            try:
                import json

                request_json = json.loads(request_body)
            except (ValueError, UnicodeDecodeError):
                request_json = None
        else:
            request_body = None
            request_json = None

    request_id = request.scope["state"].get(REQUEST_ID_STATE_KEY)

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
    )


async def post_data_update_hook(request: Request) -> None:
    """Add an audit log and delete the response cache."""
    await add_audit_log(request)
    await delete_response_cache_for_api_key(request)
    if "company_id" in request.path_params:
        company = await Company.filter(id=request.path_params["company_id"]).first()
        if company:
            company.resources_modified_at = time_now()
            await company.save()
