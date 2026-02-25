"""Domain hooks."""

from .after_response import add_audit_log, post_data_update_hook

__all__ = ("add_audit_log", "post_data_update_hook")
