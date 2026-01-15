---
icon: lucide/lock
---

# Authentication

## Overview

Valentina Noir uses API key authentication to secure all API requests. Every request to a protected endpoint must include your API key in the `X-API-KEY` header. Your API key identifies your developer account and determines what [companies](companies.md) and resources you can access.

## Obtaining an API Key

At this time, API keys are only available to developers who have been granted access by the Valentina Noir team. Please contact us at [support@valentina-noir.com](mailto:support@valentina-noir.com) to request an API key.

!!! warning "Key Security"

    Your API key grants access to all companies assigned to your developer account. Never share it publicly, commit it to version control, or expose it in client-side code.

## Using the API Key

Include the `X-API-KEY` header with every request:

```yaml
GET /api/v1/companies HTTP/1.1
---
Host: api.valentina-noir.com
X-API-KEY: your-api-key-here
```

## Developer Permissions

Your API key is associated with a developer account that has permissions assigned per company. A single API key can access multiple companies with different permission levels for each.

| Permission | Description                                                      |
| ---------- | ---------------------------------------------------------------- |
| `USER`     | Read access and basic operations within assigned companies       |
| `ADMIN`    | Full management of users and resources within assigned companies |
| `OWNER`    | Complete control including company settings and admin management |

### Permission Inheritance

Higher permissions inherit all capabilities of lower permissions:

-   `OWNER` includes all `ADMIN` capabilities
-   `ADMIN` includes all `USER` capabilities

### Multi-Company Access

A single API key can be granted access to multiple companies, each with its own permission level:

```json
{
    "id": "68c1f7152cae3787a09a74fa",
    "name": "My Application",
    "companies": [
        { "company_id": "abc123", "permission": "OWNER", ... },
        { "company_id": "def456", "permission": "USER", ... },
        { "company_id": "ghi789", "permission": "ADMIN", ... }
    ],
    "is_global_admin": false
}
```

In this example, the same API key has:

-   Full ownership control over company `abc123`
-   Read-only access to company `def456`
-   Administrative access to company `ghi789`

### Checking Your Permissions

Retrieve your API key's permissions:

```shell
GET /api/v1/developers/me
```

## Response Codes

| Status | Description                                                 |
| ------ | ----------------------------------------------------------- |
| 200    | Request successful                                          |
| 401    | API key missing or invalid                                  |
| 403    | API key valid but lacks permission for the requested action |

## Error Responses

When authentication fails, the API returns a `401 Unauthorized` response:

**Missing API Key:**

```json
{
    "status": 401,
    "title": "Unauthorized",
    "detail": "API key not provided",
    "instance": "/api/v1/companies"
}
```

**Invalid API Key:**

```json
{
    "status": 401,
    "title": "Unauthorized",
    "detail": "Unauthorized API key",
    "instance": "/api/v1/companies"
}
```

**Insufficient Permissions (403):**

```json
{
    "status": 403,
    "title": "Forbidden",
    "detail": "No rights to access this resource",
    "instance": "/api/v1/companies/abc123/users"
}
```

## Example (Python)

```python
import requests

API_KEY = "your-api-key-here"
BASE_URL = "https://api.valentina-noir.com"

def get_companies():
    response = requests.get(
        f"{BASE_URL}/api/v1/companies",
        headers={"X-API-KEY": API_KEY}
    )
    response.raise_for_status()
    return response.json()
```

## Example (JavaScript)

```javascript
const API_KEY = "your-api-key-here";
const BASE_URL = "https://api.valentina-noir.com";

async function getCompanies() {
    const response = await fetch(`${BASE_URL}/api/v1/companies`, {
        headers: {
            "X-API-KEY": API_KEY,
        },
    });

    if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`);
    }

    return response.json();
}
```

## Best Practices

1. **Use environment variables** - Store your API key in environment variables, not in code
2. **Rotate keys periodically** - Generate new keys regularly and revoke old ones
3. **Use separate keys per environment** - Create different keys for development, staging, and production
4. **Request minimal permissions** - Only request the permission level your application needs
5. **Monitor usage** - Review your API usage for unexpected activity
6. **Implement proper error handling** - Handle 401 and 403 errors gracefully in your application
