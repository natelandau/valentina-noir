---
icon: lucide/scroll-text
---

# Audit Logs

## Overview

Track all changes made through the API with audit logs. Every mutation (create, update, delete) is automatically recorded with structured metadata, so you can review what happened, who did it, and when.

Audit logs are scoped to a company and cover all resources within it: users, campaigns, characters, books, chapters, and more.

## Endpoint

Retrieve audit log entries for a company:

```shell
GET /api/v1/companies/{company_id}/audit-logs
```

The endpoint returns a [paginated](pagination.md) list of entries sorted by most recent first. Requires at least `USER`-level [developer access](authentication.md#developer-permissions) to the company.

## Filtering

Narrow results with optional query parameters. All filters are combined with AND logic.

### By Entity

Filter by the type of resource that was changed and the operation performed:

| Parameter     | Type              | Description                |
| ------------- | ----------------- | -------------------------- |
| `entity_type` | `AuditEntityType` | Type of resource (see below) |
| `operation`   | `AuditOperation`  | `CREATE`, `UPDATE`, or `DELETE` |

**Entity types:** `ASSET`, `BOOK`, `CAMPAIGN`, `CHAPTER`, `CHARACTER`, `CHARACTER_INVENTORY`, `CHARACTER_TRAIT`, `CHARGEN_SESSION`, `COMPANY`, `DEVELOPER`, `DICTIONARY_TERM`, `EXPERIENCE`, `NOTE`, `QUICKROLL`, `USER`

### By Related Resource

Filter entries that reference a specific resource:

| Parameter        | Type   | Description              |
| ---------------- | ------ | ------------------------ |
| `acting_user_id` | `UUID` | User who performed the action |
| `user_id`        | `UUID` | User the action targeted |
| `campaign_id`    | `UUID` | Related campaign         |
| `book_id`        | `UUID` | Related book             |
| `chapter_id`     | `UUID` | Related chapter          |
| `character_id`   | `UUID` | Related character        |

### By Date Range

Restrict results to a time window using ISO 8601 timestamps:

| Parameter   | Type       | Description                        |
| ----------- | ---------- | ---------------------------------- |
| `date_from` | `datetime` | Entries on or after this timestamp  |
| `date_to`   | `datetime` | Entries on or before this timestamp |

```shell
GET /api/v1/companies/{company_id}/audit-logs?date_from=2026-04-01T00:00:00Z&date_to=2026-04-12T23:59:59Z
```

## Response Format

Each audit log entry contains structured fields describing the change:

```json
{
    "items": [
        {
            "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "date_created": "2026-04-12T14:30:00Z",
            "entity_type": "CHARACTER",
            "operation": "UPDATE",
            "target_entity_id": "f9e8d7c6-b5a4-3210-fedc-ba0987654321",
            "description": "update character",
            "changes": {
                "name": {"old": "Marcus", "new": "Marcus Vane"}
            },
            "company_id": "11111111-2222-3333-4444-555555555555",
            "acting_user_id": "aaaa-bbbb-cccc-dddd",
            "user_id": null,
            "campaign_id": "eeee-ffff-0000-1111",
            "book_id": null,
            "chapter_id": null,
            "character_id": "f9e8d7c6-b5a4-3210-fedc-ba0987654321",
            "request_id": "req-abc123"
        }
    ],
    "limit": 10,
    "offset": 0,
    "total": 142
}
```

| Field              | Type          | Description                                     |
| ------------------ | ------------- | ----------------------------------------------- |
| `id`               | `UUID`        | Unique identifier for this log entry            |
| `date_created`     | `datetime`    | When the action occurred                        |
| `entity_type`      | `string|null` | Type of resource that was changed               |
| `operation`        | `string|null` | `CREATE`, `UPDATE`, or `DELETE`                 |
| `target_entity_id` | `UUID|null`   | ID of the primary resource acted upon           |
| `description`      | `string|null` | Human-readable summary of the action            |
| `changes`          | `object|null` | Field-level diff: `{"field": {"old": x, "new": y}}` |
| `company_id`       | `UUID|null`   | Company where the action occurred               |
| `acting_user_id`   | `UUID|null`   | User who performed the action                   |
| `user_id`          | `UUID|null`   | User the action targeted                        |
| `campaign_id`      | `UUID|null`   | Related campaign                                |
| `book_id`          | `UUID|null`   | Related book                                    |
| `chapter_id`       | `UUID|null`   | Related chapter                                 |
| `character_id`     | `UUID|null`   | Related character                               |
| `request_id`       | `string|null` | Request tracking ID for correlation             |
| `summary`          | `string|null` | Endpoint summary                                |

## Request Details

For debugging or forensic analysis, pass `include=request_details` to embed the raw HTTP request data in each entry:

```shell
GET /api/v1/companies/{company_id}/audit-logs?include=request_details
```

This adds the following fields to each entry:

| Field          | Type          | Description                   |
| -------------- | ------------- | ----------------------------- |
| `method`       | `string`      | HTTP method (GET, POST, etc.) |
| `url`          | `string`      | Full request URL              |
| `request_json` | `object|null` | Parsed request body           |
| `request_body` | `string|null` | Raw request body text         |
| `path_params`  | `object|null` | URL path parameters           |
| `query_params` | `object|null` | URL query parameters          |
| `operation_id` | `string|null` | OpenAPI operation identifier  |
| `handler_name` | `string|null` | Internal handler name         |

## Examples

### Python

Fetch recent character changes for a campaign:

```python
import requests

API_KEY = "your-api-key-here"
BASE_URL = "https://api.valentina-noir.com"

response = requests.get(
    f"{BASE_URL}/api/v1/companies/{COMPANY_ID}/audit-logs",
    headers={"X-API-KEY": API_KEY},
    params={
        "campaign_id": CAMPAIGN_ID,
        "entity_type": "CHARACTER",
        "limit": 25,
    },
)
response.raise_for_status()

for entry in response.json()["items"]:
    print(f"{entry['date_created']} - {entry['description']}")
    if entry["changes"]:
        for field, diff in entry["changes"].items():
            print(f"  {field}: {diff['old']} -> {diff['new']}")
```

### JavaScript

```javascript
const API_KEY = "your-api-key-here";
const BASE_URL = "https://api.valentina-noir.com";

const url = new URL(`${BASE_URL}/api/v1/companies/${companyId}/audit-logs`);
url.searchParams.set("entity_type", "CHARACTER");
url.searchParams.set("campaign_id", campaignId);
url.searchParams.set("limit", "25");

const response = await fetch(url, {
    headers: { "X-API-KEY": API_KEY },
});

const data = await response.json();
for (const entry of data.items) {
    console.log(`${entry.date_created} - ${entry.description}`);
}
```
