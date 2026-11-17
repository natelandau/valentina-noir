"""Domain hooks."""

from .post_data_update import add_audit_log, post_data_update_middleware

__all__ = ("add_audit_log", "post_data_update_middleware")
