"""Audit log model."""

from beanie import PydanticObjectId

from .base import BaseDocument


class AuditLog(BaseDocument):
    """Audit log model."""

    developer_id: PydanticObjectId
    name: str | None = None
    summary: str | None = None
    description: str | None = None
    operation_id: str | None = None
    handler_name: str | None = None
    handler: str | None = None
    method: str
    url: str
    request_json: dict | None = None
    request_body: str | None = None
    path_params: dict | None = None
    query_params: dict | None = None
