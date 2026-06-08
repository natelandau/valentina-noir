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

## Verified Identity

The `On-Behalf-Of` header is an *assertion* model: your application authenticates users through its own system, then tells Valentina which user is acting. Valentina trusts your application's claim without verifying the underlying credential itself.

**Assertion** is the right model for bots, server-side automations, and trusted server-side clients that manage their own session state.

**Verified identity** is an alternative model for applications where users sign in directly with a provider (Apple, Google, Discord, or GitHub). Instead of authenticating the user yourself and asserting their identity, you forward the provider credential to Valentina and let the API establish who signed in. Valentina verifies the credential with the provider, then resolves it to a user account. The user ID returned in the response is what you put in `On-Behalf-Of` for every subsequent request.

### Token type by provider

| Provider | Credential type                    |
| -------- | ---------------------------------- |
| Apple    | OIDC ID token (JWT)                |
| Google   | OIDC ID token (JWT)                |
| Discord  | OAuth access token                 |
| GitHub   | OAuth access token                 |

### Endpoint

`POST /companies/{company_id}/auth/identify` requires only your API key. No `On-Behalf-Of` header is sent; the endpoint resolves the user for you.

```bash
curl -X POST "$API/companies/$COMPANY_ID/auth/identify" \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"provider": "google", "token": "<google-id-token>"}'
```

The response always returns `200 OK` with a `resolution` field and a `user` object:

```json
{
    "resolution": "matched",
    "user": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "username": "marcus_player",
        "email": "marcus@example.com",
        "role": "PLAYER",
        "company_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
        "...": "..."
    }
}
```

The `user` object is the full user response; fields are abbreviated here. See [UserResponse](user_management.md) for all fields.

Use `user.id` as the value of `On-Behalf-Of` from that point on.

The `resolution` field tells you how the user was located:

| Value     | Meaning                                                                 |
| --------- | ----------------------------------------------------------------------- |
| `matched` | An existing user was found by their provider ID.                        |
| `linked`  | An existing user was matched by provider-verified email and linked.     |
| `created` | No matching user was found; a new `UNAPPROVED` user was created.        |

A `created` user cannot access game features until an admin approves them. See [user management](user_management.md#user-approval-workflow) for the approval flow.

### Apple and Google audience registration

Every Apple ID token and Google ID token contains an `aud` (audience) claim that names the specific application the token was minted for. An iOS app produces tokens with `aud` set to its bundle ID (e.g. `com.example.myapp`). A web app produces tokens with `aud` set to its Google OAuth client ID (e.g. `1234-abc.apps.googleusercontent.com`).

Checking the `aud` claim is a security requirement. Without it, any valid Google token from any application on the internet would be accepted here, and an attacker who obtains a token issued for a different site could replay it against this API to log in as that user.

A token is accepted when its `aud` value appears in either of two sources:

- **Operator-managed env vars** (global, applies to all developers):

  ```bash
  # One entry per client app (iOS bundle ID, web OAuth client ID, etc.)
  VAPI_OAUTH__APPLE_AUDIENCES='["com.example.iosapp"]'
  VAPI_OAUTH__GOOGLE_AUDIENCES='["1234-abc.apps.googleusercontent.com"]'
  ```

  This is the right choice for first-party deployments where the operator controls the client apps.

- **Self-service per-developer registration** (scoped to your API key): register your own audience values via `PATCH /developers/me` with the `provider_audiences` field. This is the right choice for external developers building their own client apps.

  ```bash
  curl -X PATCH "https://api.valentina-noir.com/api/v1/developers/me" \
    -H "X-API-KEY: $API_KEY" \
    -H "Content-Type: application/json" \
    -d '{
      "provider_audiences": {
        "google": ["1234-abc.apps.googleusercontent.com"],
        "apple": ["com.example.myapp"]
      }
    }'
  ```

  Audience values are not secrets (a bundle ID or OAuth client ID is public by design). At most 20 audiences per provider are allowed, each up to 255 characters. Set `provider_audiences` to `null` to clear your registered audiences.

A provider is disabled (returns `422 TOKEN_VERIFICATION_FAILED`) only when both sources are empty for the calling developer. Discord and GitHub do not use audience claims because their access tokens are scoped by OAuth scope strings rather than by client-app identity, so no registration is needed.

!!! note "Which source takes effect?"

    A token is accepted when its `aud` appears in *either* source. If your operator has already configured a global allowlist that includes your app's audience, you do not need to register it yourself, though registering it again is harmless.

### Error responses

| Status | Code                        | Cause                                                        |
| ------ | --------------------------- | ------------------------------------------------------------ |
| 400    | -                           | Unknown `provider` value (not apple/google/discord/github).  |
| 401    | -                           | Your `X-API-KEY` is missing or invalid.                      |
| 422    | `TOKEN_VERIFICATION_FAILED` | The provider rejected the token or it failed verification.   |
| 422    | `EMAIL_REQUIRED`            | Provider did not supply an email; include `email` in the body. |
| 429    | -                           | Registration rate limit exceeded. See [Rate Limiting](rate_limits.md). |
| 503    | `PROVIDER_UNAVAILABLE`      | The provider's servers could not be reached.                 |

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
