---
icon: lucide/file-stack
---

# Pagination

## Overview

Valentina Noir uses offset-based pagination for all endpoints that return collections. This allows you to retrieve large datasets in manageable chunks by specifying how many items to return and where to start in the result set.

## Query Parameters

| Parameter | Type    | Default | Range | Description                                |
| --------- | ------- | ------- | ----- | ------------------------------------------ |
| `limit`   | integer | 10      | 0-100 | Maximum number of items to return          |
| `offset`  | integer | 0       | 0+    | Number of items to skip from the beginning |

## Response Structure

Paginated responses include metadata alongside the results:

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
| `limit`  | integer | The limit that was applied                       |
| `offset` | integer | The offset that was applied                      |
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

Use the `total` field to calculate the number of pages:

```
total_pages = ceil(total / limit)
current_page = floor(offset / limit) + 1
```

For example, with `total=47` and `limit=10`:

-   Total pages: `ceil(47 / 10) = 5`
-   Page 1: `offset=0` (items 1-10)
-   Page 2: `offset=10` (items 11-20)
-   Page 3: `offset=20` (items 21-30)
-   Page 4: `offset=30` (items 31-40)
-   Page 5: `offset=40` (items 41-47)

## Iterating Through All Results (Python)

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

        # Check if we've retrieved all items
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

1. **Cache the total count** - The `total` field can be used to display pagination UI without additional requests
2. **Handle empty results** - An empty `items` array with `total=0` indicates no matching records
3. **Don't exceed the total** - Requests with `offset >= total` will return an empty `items` array
4. **Consider rate limits** - When iterating through large datasets, be mindful of [rate limits](rate-limiting.md)
