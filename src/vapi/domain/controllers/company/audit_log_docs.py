"""Company audit log endpoint documentation."""

LIST_AUDIT_LOGS_DESCRIPTION = """\
Retrieve a paginated list of audit log entries for this company.

Returns all API mutations recorded within the company, sorted by most recent first. \
Use query parameters to filter by user, campaign, character, entity type, operation, \
or date range.

Pass `include=request_details` to embed raw request forensics (URL, request body, \
path/query params) in each entry.
"""
