---
icon: lucide/shield-alert
---

# Global Admin

## Overview

Global admin endpoints provide platform-level management capabilities. They are only accessible to developer accounts with `is_global_admin: true` and are not scoped to any individual company.

Global admin endpoints live under `/api/v1/admin/`.

!!! warning "Restricted Access"

    All endpoints on this page require a developer API key with global admin privileges. Requests from non-admin keys receive `403 Forbidden`.

## Developer Management

Manage developer accounts across the entire platform.

### List developers

```shell
GET /api/v1/admin/developers
```

Returns a [paginated](pagination.md) list of all developer accounts.

**Query parameters:**

| Parameter        | Type      | Description |
| ---------------- | --------- | ----------- |
| `is_global_admin` | `boolean` | Filter by global admin status |
| `limit`          | `integer` | Page size (0-100, default 10) |
| `offset`         | `integer` | Pagination offset (default 0) |

### Get developer

```shell
GET /api/v1/admin/developers/{developer_id}
```

Retrieve a single developer account by ID.

### Create developer

```shell
POST /api/v1/admin/developers
```

Create a new developer account. The account is created without an API key. Generate a key immediately after creation using the API key endpoint.

### Update developer

```shell
PATCH /api/v1/admin/developers/{developer_id}
```

Modify a developer account's properties. Include only the fields that need to change.

### Delete developer

```shell
DELETE /api/v1/admin/developers/{developer_id}
```

Soft-delete a developer account. Their API key is invalidated immediately.

### Generate API key

```shell
POST /api/v1/admin/developers/{developer_id}/new-key
```

Generate a new API key for a developer. Their current key is invalidated immediately. Save the returned key, as it will not be displayed again.

### Developer audit logs

```shell
GET /api/v1/admin/developers/{developer_id}/audit-logs
```

Retrieve a [paginated](pagination.md) list of audit log entries for a specific developer. This covers all API mutations performed by that developer's API key, sorted by most recent first.

Accepts the same filtering query parameters as the [company audit log endpoint](audit_logs.md#filtering): `company_id`, `acting_user_id`, `user_id`, `campaign_id`, `book_id`, `chapter_id`, `character_id`, `entity_type`, `operation`, `date_from`, and `date_to`.

Pass `include=request_details` to embed raw request forensics in each entry. See [Audit Logs](audit_logs.md) for the full response format.

---

## User Management

Manage end-user accounts across all companies. Unlike the company-scoped [user management](user_management.md) endpoints, these are not bound to a single company and require no `On-Behalf-Of` header. The global-admin API key is the sole authorization.

### List users

```shell
GET /api/v1/admin/users
```

Returns a [paginated](pagination.md) list of users across all companies.

**Query parameters:**

| Parameter      | Type      | Description |
| -------------- | --------- | ----------- |
| `company_id`   | `uuid`    | Filter by company |
| `role`         | `string`  | Filter by role. One of `ADMIN`, `STORYTELLER`, `PLAYER`, `UNAPPROVED`, `DEACTIVATED` |
| `email`        | `string`  | Filter by exact email match |
| `is_archived`  | `boolean` | Filter by archived (soft-deleted) status |
| `limit`        | `integer` | Page size (0-100, default 10) |
| `offset`       | `integer` | Pagination offset (default 0) |

### Get user

```shell
GET /api/v1/admin/users/{user_id}
```

Retrieve a single user by ID. Archived (soft-deleted) users are returned. The response includes an `is_archived` boolean field indicating whether the user has been soft-deleted; this field is not present on the tenant-scoped user endpoints.

### Create user

```shell
POST /api/v1/admin/users
```

Create a user. Supply the target `company_id` in the request body along with `username`, `email`, and `role`, plus the optional `name_first`, `name_last`, `discord_profile`, `google_profile`, `github_profile`, and `apple_profile`. A user cannot be created with the `UNAPPROVED` or `DEACTIVATED` role.

### Update user

```shell
PATCH /api/v1/admin/users/{user_id}
```

Update any user by ID. Include only the fields that need to change. The role-assignment matrix does not apply, so a global admin may set any role. Setting `is_archived: false` restores a soft-deleted user, reversing the archive cascade so the data archived with them is restored as well. Restoring is refused (409 Conflict) while the user's company is archived; restore the company first.

### Delete user

```shell
DELETE /api/v1/admin/users/{user_id}
```

Soft-delete a user. Archival cascades to their quickrolls, assets, notes, and played characters; dice rolls are kept as historical records. Restore the user with `PATCH /api/v1/admin/users/{user_id}` and `is_archived: false`, which reverses the cascade and restores the data archived with them as a unit.

---

## Server Logs

Inspect and download the application's on-disk log files. Both endpoints return `409 Conflict` when file logging is not enabled on the server (`settings.log.file_path` is unset).

### Tail server logs

```shell
GET /api/v1/admin/logs
```

Return the most recent application log entries, newest first. Reads only the active log file.

**Query parameters:**

| Parameter | Type     | Description |
| --------- | -------- | ----------- |
| `level`   | `string` | Minimum log level to include. One of `TRACE`, `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Defaults to the server's configured log level. |
| `limit`   | `integer` | Maximum number of level-matched entries to return (1-500, default 100). |

Unparsable lines and entries whose level is not one of the recognized levels are surfaced in addition to the matched entries (on a separate `limit`-sized budget), so corruption and unranked levels are never silently dropped. An empty array is returned when file logging is enabled but no matching entries exist yet.

**Response:** `200 OK`, `application/json`, a JSON array of log entry objects.

```json
[
    {
        "timestamp": "2026-05-25T12:00:00Z",
        "level": "INFO",
        "name": "vapi.server",
        "message": "Request completed",
        "exception": null,
        "extra": {"status_code": 200, "path": "/api/v1/companies"},
        "raw": null
    }
]
```

| Field       | Type           | Description |
| ----------- | -------------- | ----------- |
| `timestamp` | `string\|null` | ISO 8601 timestamp from the log line |
| `level`     | `string\|null` | Log level (e.g. `INFO`, `ERROR`) |
| `name`      | `string\|null` | Logger name |
| `message`   | `string\|null` | Log message text |
| `exception` | `string\|null` | Exception traceback, if present |
| `extra`     | `object`       | Structured fields not mapped to the named properties above |
| `raw`       | `string\|null` | Original unparsed line, set only when the line is not valid JSON |

**Error responses:**

| Status | Description |
| ------ | ----------- |
| 403    | API key does not have global admin privileges |
| 409    | File logging is not enabled on the server |

### Download server logs

```shell
GET /api/v1/admin/logs/download
```

Download a zip archive of the application's log files. The archive bundles the active log file and any rotated backups (`app.log`, `app.log.1`, `app.log.2`).

**No query parameters.**

**Response:** `200 OK`, `application/zip` attachment. The filename follows the pattern `vapi-logs-<UTC-timestamp>.zip` (e.g. `vapi-logs-20260525T120000Z.zip`).

**Error responses:**

| Status | Description |
| ------ | ----------- |
| 403    | API key does not have global admin privileges |
| 409    | File logging is not enabled, or no log files exist on disk |

### Example

Fetch the last 50 `WARNING`-or-above entries:

```python
import requests

API_KEY = "your-global-admin-key"
BASE_URL = "https://api.valentina-noir.com"

response = requests.get(
    f"{BASE_URL}/api/v1/admin/logs",
    headers={"X-API-KEY": API_KEY},
    params={"level": "WARNING", "limit": 50},
)
response.raise_for_status()

for entry in response.json():
    print(f"[{entry['level']}] {entry['timestamp']} - {entry['message']}")
    if entry["exception"]:
        print(entry["exception"])
```

Download all log files as a zip:

```python
import requests

API_KEY = "your-global-admin-key"
BASE_URL = "https://api.valentina-noir.com"

response = requests.get(
    f"{BASE_URL}/api/v1/admin/logs/download",
    headers={"X-API-KEY": API_KEY},
)
response.raise_for_status()

filename = response.headers["Content-Disposition"].split("filename=")[1].strip('"')
with open(filename, "wb") as f:
    f.write(response.content)
print(f"Saved {filename}")
```
