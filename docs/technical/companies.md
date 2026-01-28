---
icon: lucide/building
---

# Companies

Companies are the foundational entity in Valentina Noir. Each company is a distinct entity with its own set of users, campaigns, and characters, etc.

Companies provide complete data isolation:

- Users in one company cannot see or access users in another company
- Characters, campaigns, and all other resources are scoped to their parent company
- API keys are granted permissions on a per-company basis

This isolation enables multiple independent gaming groups or organizations to use Valentina without data leakage.

## Company Permissions

Developer API keys are granted permissions on a per-company basis. There are three levels of permissions on a company that can be granted to a developer:

- `USER` - Read access and basic operations within assigned companies
- `ADMIN` - Full management of users and resources within assigned companies
- `OWNER` - Complete control including company settings and admin management

!!! note

    The developer who creates a company automatically receives `OWNER` permission for that company and can associate additional developers with their company for client development.

## Multi-Company Access

A single developer API key can access multiple companies with different permission levels. This enables scenarios like:

- A platform provider managing multiple gaming communities
- A developer with admin access to their company but read-only access to a partner's company
- A global admin supporting multiple gaming groups

## URL Structure

All resource endpoints are nested under a company:

```
/api/v1/companies/{company_id}/users
/api/v1/companies/{company_id}/users/{user_id}/campaigns
/api/v1/companies/{company_id}/users/{user_id}/campaigns/{campaign_id}/characters
...
```

This hierarchical structure ensures every request is scoped to a specific company.

## Creating a Company

Create a new company to establish a separate namespace for a gaming group.

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

The response will include the company and the admin user account:

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

!!! note

    The developer who creates a company automatically receives `OWNER` permission for that company and can associate additional developers with their company for client development.

!!! note

    Creating a company will also create a user account with `ADMIN` permissions for the company with your developer username and email (you can patch this later).

## Multi-Company Access

A single developer API key can access multiple companies with different permission levels. This enables scenarios like:

- A platform provider managing multiple gaming communities
- A developer with admin access to their company but read-only access to a partner's company
- A global admin supporting multiple gaming groups

See [Authentication](authentication.md#multi-company-access) for details on permission levels.

## Listing Your Companies

Retrieve all companies accessible to your API key:

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

1. **Grant minimal permissions** - Only grant the permission level developers need for each company
2. **Consider company structure early** - Moving resources between companies is not supported
3. **Use company IDs in your database** - Store the `company_id` alongside user mappings for multi-tenant applications
