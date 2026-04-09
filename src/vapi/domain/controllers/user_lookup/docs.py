"""User lookup documentation."""

LOOKUP_DESCRIPTION = """\
Look up a person across all companies you have access to. Returns one result per company \
where a matching user record exists.

Provide **exactly one** query parameter:

| Parameter    | Matches against              |
|-------------|------------------------------|
| `email`      | User email (exact match)    |
| `discord_id` | Discord profile ID          |
| `google_id`  | Google profile ID           |
| `github_id`  | GitHub profile ID           |

**Intended for login/registration flows** — discover which companies a person already \
belongs to so your client can offer "log in to Company X" or detect existing accounts.

Archived users are excluded. Unapproved and deactivated users are included so your \
client can display appropriate messaging.

Results are scoped to companies where you have USER, ADMIN, or OWNER permission.
"""
