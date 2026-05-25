"""Global admin documentation."""

LIST_DEVELOPERS_DESCRIPTION = """\
Retrieve a paginated list of all developer accounts in the system. Requires global admin privileges.
"""

GET_DEVELOPER_DESCRIPTION = """\
Retrieve detailed information about a specific developer account. Requires global admin privileges.
"""

CREATE_DEVELOPER_DESCRIPTION = """\
Create a new developer account. This creates the account but does not create an API key or grant access to any companies.

**Be certain to generate an API key after account creation.**

Requires global admin privileges.
"""

UPDATE_DEVELOPER_DESCRIPTION = """\
Modify a developer account's properties. Only include fields that need to be changed. Requires global admin privileges.
"""

DELETE_DEVELOPER_DESCRIPTION = """\
Remove a developer account from the system. The developer's API key will be invalidated immediately. Requires global admin privileges.
"""

CREATE_API_KEY_DESCRIPTION = """\
Generate a new API key for a developer. Their current key will be immediately invalidated.

**Be certain to save the API key as it will not be displayed again.**

Requires global admin privileges.
"""

LIST_DEVELOPER_AUDIT_LOGS_DESCRIPTION = """\
Retrieve a paginated list of audit log entries for a specific developer.

Returns all API mutations performed by the developer's API key, sorted by most \
recent first. Use query parameters to filter by company, user, campaign, character, \
entity type, operation, or date range.

Pass `include=request_details` to embed raw request forensics (URL, request body, \
path/query params) in each entry.

Requires global admin privileges.
"""


TAIL_LOGS_DESCRIPTION = """\
Return the most recent application log entries, filtered by minimum level.

Reads the active log file and returns the newest matching entries whose level is at \
or above `level`. When `level` is omitted it defaults to the server's configured log \
level. `limit` bounds the number of level-matched entries; unparsable lines and \
entries whose level is unrecognized are surfaced in addition (newest first) so \
corruption and unranked levels are never hidden.

Returns an empty array when file logging is enabled but the log file holds no \
matching entries yet. Returns 409 if file logging is not enabled. Requires global \
admin privileges.
"""

DOWNLOAD_LOGS_DESCRIPTION = """\
Download a zip archive of the application's log files.

Bundles the active log file together with any rotated backups into a single zip \
download.

Returns 409 if file logging is not enabled or no log files exist on disk. \
Requires global admin privileges.
"""
