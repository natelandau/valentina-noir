---
icon: lucide/file-stack
---

# Pagination

## Overview

Retrieve large datasets in manageable chunks using offset-based pagination. All collection endpoints support pagination through `limit` and `offset` parameters.

## Query Parameters

Control pagination using these query parameters.

| Parameter | Type    | Default | Range | Description                          |
| --------- | ------- | ------- | ----- | ------------------------------------ |
| `limit`   | integer | 10      | 1-100 | Maximum number of items to return    |
| `offset`  | integer | 0       | 0+    | Number of items to skip from the top |

## Response Structure

Paginated responses include metadata to help you navigate through results.

```json
{
    "items": [...],
    "limit": 10,
    "offset": 0,
    "total": 47
}
```

| Field    | Type    | Description                                      |
| -------- | ------- | ------------------------------------------------ |
| `items`  | array   | The requested page of results                    |
| `limit`  | integer | The limit applied to this request                |
| `offset` | integer | The offset applied to this request               |
| `total`  | integer | Total number of items available across all pages |

## Basic Usage

Request the first 10 users:

```shell
GET /api/v1/companies/{company_id}/users?limit=10&offset=0
```

Request the next 10 users:

```shell
GET /api/v1/companies/{company_id}/users?limit=10&offset=10
```

## Calculating Pages

Calculate page counts using the `total` field.

```
total_pages = ceil(total / limit)
current_page = floor(offset / limit) + 1
```

**Example:** With `total=47` and `limit=10`:

| Page | Offset | Items |
| ---- | ------ | ----- |
| 1    | 0      | 1-10  |
| 2    | 10     | 11-20 |
| 3    | 20     | 21-30 |
| 4    | 30     | 31-40 |
| 5    | 40     | 41-47 |

Total pages: `ceil(47 / 10) = 5`

## Iterating Through All Results (Python)

Fetch all items by iterating through pages until you reach the total count.

```python
import requests

def get_all_users(api_key, company_id):
    """Fetch all users by iterating through pages."""
    base_url = f"https://api.valentina-noir.com/api/v1/companies/{company_id}/users"
    headers = {"X-API-KEY": api_key}

    all_users = []
    offset = 0
    limit = 100  # Use maximum limit for efficiency

    while True:
        response = requests.get(
            base_url,
            headers=headers,
            params={"limit": limit, "offset": offset}
        )
        response.raise_for_status()
        data = response.json()

        all_users.extend(data["items"])

        # Stop when we've retrieved all items
        if offset + limit >= data["total"]:
            break

        offset += limit

    return all_users
```

## Iterating Through All Results (JavaScript)

```javascript
async function getAllUsers(apiKey, companyId) {
    const baseUrl = `https://api.valentina-noir.com/api/v1/companies/${companyId}/users`;
    const headers = { "X-API-KEY": apiKey };

    const allUsers = [];
    let offset = 0;
    const limit = 100; // Use maximum limit for efficiency

    while (true) {
        const url = new URL(baseUrl);
        url.searchParams.set("limit", limit);
        url.searchParams.set("offset", offset);

        const response = await fetch(url, { headers });
        if (!response.ok) {
            throw new Error(`HTTP error: ${response.status}`);
        }

        const data = await response.json();
        allUsers.push(...data.items);

        // Check if we've retrieved all items
        if (offset + limit >= data.total) {
            break;
        }

        offset += limit;
    }

    return allUsers;
}
```

## Best Practices

!!! tip "Optimize Your Pagination"

    Use the maximum `limit=100` when fetching large datasets to minimize API calls.

!!! warning "Handle Empty Results"

    An empty `items` array with `total=0` indicates no matching records exist.

**Key recommendations:**

1. **Cache the total count** - Use the `total` field to display pagination UI without additional requests
2. **Stay within bounds** - Requests with `offset >= total` return an empty `items` array
3. **Respect rate limits** - When iterating through large datasets, monitor your [rate limits](rate_limits.md)
4. **Use consistent limit values** - Keep the same `limit` across requests for predictable pagination
