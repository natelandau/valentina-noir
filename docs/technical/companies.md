---
icon: lucide/building
---

# Companies

## Overview

Companies serve as the foundational entity in Valentina Noir. Each company operates as a distinct entity with its own users, campaigns, characters, and resources.

### Data Isolation

Companies provide complete data isolation between gaming groups:

- Users in one company cannot see or access users in another company
- Characters, campaigns, and all other resources are scoped to their parent company
- API keys are granted permissions on a per-company basis

This isolation enables multiple independent gaming groups to use Valentina Noir without data leakage.

## Company Permissions

Each developer API key has permissions assigned per company. Three permission levels control access:

| Permission | Access Level                                                     |
| ---------- | ---------------------------------------------------------------- |
| `USER`     | Read access and basic operations within assigned companies       |
| `ADMIN`    | Full management of users and resources within assigned companies |
| `OWNER`    | Complete control including company settings and admin management |

!!! tip "Auto-Assignment"

    Creating a company automatically grants you `OWNER` permission for that company. You can then associate additional developers for client development.

### Multi-Company Access

Access multiple companies with a single developer API key, each with different permission levels. Common scenarios include:

- Platform providers managing multiple gaming communities
- Developers with admin access to their company and read-only access to a partner's company
- Global admins supporting multiple gaming groups

## URL Structure

All resource endpoints nest under a company to ensure proper scoping.

```
/api/v1/companies/{company_id}/users
/api/v1/companies/{company_id}/users/{user_id}/campaigns
/api/v1/companies/{company_id}/users/{user_id}/campaigns/{campaign_id}/characters
```

This hierarchical structure scopes every request to a specific company.

## Creating a Company

Create a company to establish a separate namespace for your gaming group.

```yaml
POST /api/v1/companies HTTP/1.1
---
Host: api.valentina-noir.com
X-API-KEY: your-api-key-here
Content-Type: application/json
{
    "name": "My Gaming Group"
    ...
}
```

The response includes both the company and an admin user account:

```json
{
    "company": {
        "id": "697996c7659f4e107e3bc81a",
        "date_created": "2026-01-28T04:55:35Z",
        "date_modified": "2026-01-28T04:55:35Z",
        "name": "Test Company",
        "description": "Test Description",
        "email": "test@test.com",
        "user_ids": ["697996c7659f4e107e3bc81b"], // (1)!
        "settings": {
            "character_autogen_xp_cost": 10,
            "character_autogen_num_choices": 3,
            "permission_manage_campaign": "UNRESTRICTED",
            "permission_grant_xp": "UNRESTRICTED",
            "permission_free_trait_changes": "UNRESTRICTED"
        }
    },
    "admin_user": {
        "id": "697996c7659f4e107e3bc81b",
        "date_created": "2026-01-28T04:55:35Z",
        "date_modified": "2026-01-28T04:55:35Z",
        "name": "test developer", // (2)!
        "email": "test@test.com", // (3)!
        "role": "ADMIN",
        "company_id": "697996c7659f4e107e3bc81a",
        "campaign_experience": [],
        "asset_ids": []
    }
}
```

1. The created user account ID
2. Your developer username
3. Your developer email

!!! info "Automatic User Creation"

    Creating a company also creates a user account with `ADMIN` permissions using your developer username and email. You can update this account later via PATCH requests.

### Multi-Company Access

Access multiple companies with a single developer API key, each with different permission levels. Common scenarios include:

- Platform providers managing multiple gaming communities
- Developers with admin access to their company and read-only access to a partner's company
- Global admins supporting multiple gaming groups

Learn more about permission levels in [Authentication](authentication.md#developer-permissions).

## Listing Companies

Retrieve all companies your API key can access:

```shell
GET /api/v1/companies
```

Response:

```json
{
    "items": [
        {
            "id": "abc123",
            "name": "My Gaming Group",
            "date_created": "2025-01-15T10:30:00Z"
            ...
        },
        {
            "id": "def456",
            "name": "Partner Organization",
            "date_created": "2025-02-20T14:45:00Z"
            ...
        }
    ],
    "limit": 10,
    "offset": 0,
    "total": 2
}
```

## Best Practices

1. **Grant minimal permissions** - Assign only the permission level developers need for each company
2. **Plan company structure early** - Resources cannot be moved between companies
3. **Store company IDs** - Keep the `company_id` in your database alongside user mappings for multi-tenant applications
