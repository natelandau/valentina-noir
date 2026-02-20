---
icon: lucide/lock
---

# Authentication

## Overview

Secure your API requests with API key authentication. Include your API key in the `X-API-KEY` header with every request to a protected endpoint. The key identifies your developer account and controls which [companies](companies.md) and resources you can access.

## Obtaining an API Key

Request an API key from the Valentina Noir team. Contact [support@valentina-noir.com](mailto:support@valentina-noir.com) to get started.

!!! info "Limited Access"

    API keys are currently available only to approved developers.

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

Each API key associates with a developer account that has permissions assigned per company. Access multiple companies with a single API key, using different permission levels for each.

| Permission | Description                                                      |
| ---------- | ---------------------------------------------------------------- |
| `USER`     | Read access and basic operations within assigned companies       |
| `ADMIN`    | Full management of users and resources within assigned companies |
| `OWNER`    | Complete control including company settings and admin management |

### Permission Inheritance

Higher permissions inherit all capabilities of lower permissions:

- `OWNER` includes all `ADMIN` capabilities
- `ADMIN` includes all `USER` capabilities

### Multi-Company Access

Grant a single API key access to multiple companies, each with its own permission level.

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

This example shows one API key with different access levels:

- `OWNER` permission for company `abc123` (full control)
- `USER` permission for company `def456` (read-only access)
- `ADMIN` permission for company `ghi789` (administrative access)

### Checking Your Permissions

Retrieve your API key's permissions:

```shell
GET /api/v1/developers/me
```

## Common Response Codes

| Status | Description                                           |
| ------ | ----------------------------------------------------- |
| 200    | Request successful                                    |
| 401    | API key missing or invalid                            |
| 403    | API key valid but lacks permission for this operation |

## Error Responses

The API returns specific errors when authentication fails.

### Missing API Key

```json
{
    "status": 401,
    "title": "Unauthorized",
    "detail": "API key not provided",
    "instance": "/api/v1/companies"
}
```

### Invalid API Key

```json
{
    "status": 401,
    "title": "Unauthorized",
    "detail": "Unauthorized API key",
    "instance": "/api/v1/companies"
}
```

### Insufficient Permissions

```json
{
    "status": 403,
    "title": "Forbidden",
    "detail": "No rights to access this resource",
    "instance": "/api/v1/companies/abc123/users"
}
```

## Examples

### Python

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

### JavaScript

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
