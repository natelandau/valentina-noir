---
icon: lucide/play
---

# Make Your First Request

Confirm your API key works, then create a company to develop against. A company is the top-level container for everything else you build: users, campaigns, and characters all live inside one. By the end of this page you'll have a `company_id` and an admin user ID to carry into every later step.

## Verify your API key

Start with a request that needs nothing but your key. The `/developers/me` endpoint returns your developer account and the companies it can already access.

```python
import os
import requests

BASE_URL = "https://api.valentina-noir.com/api/v1"
API_KEY = os.environ["VALENTINA_API_KEY"]

response = requests.get(
    f"{BASE_URL}/developers/me",
    headers={"X-API-KEY": API_KEY},
)
response.raise_for_status()
print(response.json())
```

A successful response confirms your key is valid:

```json
{
    "id": "68c1f7152cae3787a09a74fa",
    "name": "My Application",
    "companies": [],
    "is_global_admin": false
}
```

A `401 Unauthorized` means the key is missing or wrong. Check the `X-API-KEY` header value and see [Authentication](../technical/authentication.md#error-responses).

## Create a development company

Your developer account may not have access to a company yet, and you don't want to build against live game data. Create a throwaway company to develop in.

```python
response = requests.post(
    f"{BASE_URL}/companies",
    headers={"X-API-KEY": API_KEY},
    json={
        "name": "Friday Night Games (dev)",
        "email": "you@example.com",
    },
)
response.raise_for_status()
data = response.json()

company_id = data["company"]["id"]
admin_user_id = data["admin_user"]["id"]
```

Creating a company does two things automatically:

- Grants your API key `OWNER` permission for the new company.
- Creates an `ADMIN` user from your developer username and email.

The response returns both objects:

```json
{
    "company": {
        "id": "697996c7659f4e107e3bc81a",
        "name": "Friday Night Games (dev)",
        "num_users": 1,
        "settings": { "...": "..." }
    },
    "admin_user": {
        "id": "697996c7659f4e107e3bc81b",
        "role": "ADMIN",
        "company_id": "697996c7659f4e107e3bc81a"
    }
}
```

!!! warning "Save both IDs"

    Store `company_id` and `admin_user_id` now. Every endpoint from here nests under `/companies/{company_id}`, and the admin user is the only account that can approve other users before anyone else exists.

For the full company model, settings, and lifecycle, see [Companies](../technical/companies.md).

## What you have now

Your key works, and you have a company with one admin user. Next, [authenticate your users](users.md) so real players can act inside this company.
