"""Audit log domain package.

Colocates the audit-log query service and its response DTOs. The audit *hook*
plumbing (which writes entries) lives in `vapi.domain.hooks`; this package owns
the read side consumed by the company and global-admin audit-log controllers.
"""

from .dto import AuditLogDetailResponse, AuditLogInclude, AuditLogResponse
from .service import build_audit_log_filters, list_audit_logs

__all__ = (
    "AuditLogDetailResponse",
    "AuditLogInclude",
    "AuditLogResponse",
    "build_audit_log_filters",
    "list_audit_logs",
)
