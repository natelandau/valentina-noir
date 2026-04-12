"""Global admin audit log endpoint documentation."""

LIST_DEVELOPER_AUDIT_LOGS_DESCRIPTION = """\
Retrieve a paginated list of audit log entries for a specific developer.

Returns all API mutations performed by the developer's API key, sorted by most \
recent first. Use query parameters to filter by company, user, campaign, character, \
entity type, operation, or date range.

Pass `include=request_details` to embed raw request forensics (URL, request body, \
path/query params) in each entry.

Requires global admin privileges.
"""
