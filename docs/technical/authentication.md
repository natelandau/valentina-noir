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

## The On-Behalf-Of Header

Most endpoints operate in the context of a specific end-user. The `On-Behalf-Of` header tells the API which user is performing the action.

### When It's Required

Include the `On-Behalf-Of` header on all user-scoped endpoints under `/companies/{company_id}/` that involve game resources (campaigns, characters, dice rolls, experience, notes, etc.). The API uses this header to enforce role-based permissions and track audit history.

You don't need this header for:

- Company CRUD (`/companies`, `/companies/{company_id}`)
- Developer endpoints (`/developers/me`)
- System endpoints (`/system/*`, `/health`, `/metadata`)
- OAuth endpoints (`/oauth/*`)
- User registration (`/companies/{company_id}/users/register`)

### Format and Validation

The header value must be a valid UUID string identifying an existing user within the target company.

```yaml
GET /api/v1/companies/{company_id}/campaigns HTTP/1.1
---
Host: api.valentina-noir.com
X-API-KEY: your-api-key-here
On-Behalf-Of: 550e8400-e29b-41d4-a716-446655440000
```

The API validates the header in this order:

1. **Present** — returns `400 Bad Request` if missing
2. **Valid UUID** — returns `400 Bad Request` if malformed
3. **User exists** — returns `404 Not Found` if no user matches in the company
4. **Active user** — returns `400 Bad Request` if the user is archived or deactivated

### Error Responses

Missing or invalid header:

```json
{
    "status": 400,
    "title": "Bad Request",
    "detail": "On-Behalf-Of header is required"
}
```

User not found:

```json
{
    "status": 404,
    "title": "Not Found",
    "detail": "User not found in this company"
}
```

### Code Examples

**Python:**

```python
import requests

API_KEY = "your-api-key-here"
BASE_URL = "https://api.valentina-noir.com"
USER_ID = "550e8400-e29b-41d4-a716-446655440000"

def list_campaigns(company_id):
    response = requests.get(
        f"{BASE_URL}/api/v1/companies/{company_id}/campaigns",
        headers={
            "X-API-KEY": API_KEY,
            "On-Behalf-Of": USER_ID,
        },
    )
    response.raise_for_status()
    return response.json()
```

**JavaScript:**

```javascript
const API_KEY = "your-api-key-here";
const BASE_URL = "https://api.valentina-noir.com";
const USER_ID = "550e8400-e29b-41d4-a716-446655440000";

async function listCampaigns(companyId) {
    const response = await fetch(
        `${BASE_URL}/api/v1/companies/${companyId}/campaigns`,
        {
            headers: {
                "X-API-KEY": API_KEY,
                "On-Behalf-Of": USER_ID,
            },
        },
    );

    if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`);
    }

    return response.json();
}
```

## Developer Permissions

Each API key associates with a developer account that has permissions assigned per company. Access multiple companies with a single API key, using different permission levels for each.

Developer permissions control **company governance** — who can manage the company itself and grant access to other developers. They don't restrict access to game resources like users, characters, or campaigns. Any developer with access to a company can use the full API for that company's resources.

| Permission | Description                                                            |
| ---------- | ---------------------------------------------------------------------- |
| `USER`     | Full access to all company resources (users, characters, campaigns)    |
| `ADMIN`    | All `USER` capabilities, plus manage company settings                  |
| `OWNER`    | All `ADMIN` capabilities, plus grant/revoke developer access and delete the company |

### Permission Inheritance

Higher permissions inherit all capabilities of lower permissions:

- `OWNER` includes all `ADMIN` capabilities
- `ADMIN` includes all `USER` capabilities

### Developer vs. User Permissions

The API uses two separate permission layers:

- **Developer permissions** (described above) control company governance — managing the company, its settings, and which developers can access it.
- **[User roles](user_management.md)** control in-game actions — what end-users can do within a company (e.g., who can grant XP, manage campaigns, or edit characters).

Your application authenticates its own users, then makes API calls on their behalf using the [`On-Behalf-Of` header](#the-on-behalf-of-header). The API enforces game rules based on the user's role, regardless of which developer is making the request.

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

- `OWNER` permission for company `abc123` (full control including company governance)
- `USER` permission for company `def456` (full resource access)
- `ADMIN` permission for company `ghi789` (resource access plus company settings management)

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
USER_ID = "550e8400-e29b-41d4-a716-446655440000"

def get_companies():
    """List companies (no On-Behalf-Of header needed)."""
    response = requests.get(
        f"{BASE_URL}/api/v1/companies",
        headers={"X-API-KEY": API_KEY},
    )
    response.raise_for_status()
    return response.json()

def get_campaigns(company_id):
    """List campaigns (On-Behalf-Of header required)."""
    response = requests.get(
        f"{BASE_URL}/api/v1/companies/{company_id}/campaigns",
        headers={
            "X-API-KEY": API_KEY,
            "On-Behalf-Of": USER_ID,
        },
    )
    response.raise_for_status()
    return response.json()
```

### JavaScript

```javascript
const API_KEY = "your-api-key-here";
const BASE_URL = "https://api.valentina-noir.com";
const USER_ID = "550e8400-e29b-41d4-a716-446655440000";

// List companies (no On-Behalf-Of header needed)
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

// List campaigns (On-Behalf-Of header required)
async function getCampaigns(companyId) {
    const response = await fetch(
        `${BASE_URL}/api/v1/companies/${companyId}/campaigns`,
        {
            headers: {
                "X-API-KEY": API_KEY,
                "On-Behalf-Of": USER_ID,
            },
        },
    );

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
