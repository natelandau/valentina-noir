"""Global admin server log endpoint documentation."""

TAIL_LOGS_DESCRIPTION = """\
Return the most recent application log entries, filtered by minimum level.

Reads the active log file and returns up to `limit` entries (newest first) whose \
level is at or above `level`. When `level` is omitted it defaults to the server's \
configured log level. Each entry is parsed from its JSON line into structured \
fields; lines that cannot be parsed are returned with their raw text.

Returns 409 if file logging is not enabled. Requires global admin privileges.
"""

DOWNLOAD_LOGS_DESCRIPTION = """\
Download a zip archive of the application's log files.

Bundles the active log file together with any rotated backups into a single zip \
download.

Returns 409 if file logging is not enabled or no log files exist on disk. \
Requires global admin privileges.
"""
