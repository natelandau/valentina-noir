"""System endpoint documentation."""

HEALTH_CHECK_DESCRIPTION = """\
Verify the API and its dependencies are operational. Returns database and cache connectivity \
status, response latency in milliseconds, process uptime, and application version. \
Requires an API key. Use the liveness endpoint for an unauthenticated check.
"""

LIVENESS_DESCRIPTION = """\
Report that the API process is running and accepting requests. Makes no database or cache calls, \
so it stays fast and answers even when dependencies are down. Use it as a hosting healthcheck; use \
the system health endpoint to verify dependencies. No authentication required and not rate limited.
"""
