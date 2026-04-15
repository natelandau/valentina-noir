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

Each developer API key has permissions assigned per company. These permissions control **company governance** — who can manage the company and grant access to other developers. Any developer with access to a company can use the full API for that company's resources (users, characters, campaigns, etc.).

| Permission | Access Level                                                                       |
| ---------- | ---------------------------------------------------------------------------------- |
| `USER`     | Full access to all company resources (users, characters, campaigns)                |
| `ADMIN`    | All `USER` capabilities, plus manage company settings                              |
| `OWNER`    | All `ADMIN` capabilities, plus grant/revoke developer access and delete the company |

For details on how these differ from end-user roles, see [Developer vs. User Permissions](authentication.md#developer-vs-user-permissions).

!!! tip "Auto-Assignment"

    Creating a company automatically grants you `OWNER` permission for that company. You can then associate additional developers for client development.

## URL Structure

All resource endpoints nest under a company to ensure proper scoping.

```
/api/v1/companies/{company_id}/users
/api/v1/companies/{company_id}/campaigns
/api/v1/companies/{company_id}/characters
/api/v1/companies/{company_id}/dicerolls
```

This flat structure scopes every request to a specific company. The [`On-Behalf-Of` header](authentication.md#the-on-behalf-of-header) identifies which user is performing the action, rather than nesting resources under a user path.

### Child Data Last Updated

The Company model has a `resources_modified_at` field. This field is updated whenever child resources (characters, campaigns, etc.) are updated. This is useful for caching purposes to avoid unnecessary API calls.

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
        "resources_modified_at": "2026-01-28T04:55:35Z",
        "num_campaigns": 0,
        "num_player_characters": 0,
        "num_storyteller_characters": 0,
        "num_npc_characters": 0,
        "num_users": 1,
        "settings": {
            "character_autogen_xp_cost": 10,
            "character_autogen_num_choices": 3,
            "permission_manage_campaign": "UNRESTRICTED",
            "permission_grant_xp": "UNRESTRICTED",
            "permission_free_trait_changes": "UNRESTRICTED",
            "permission_recoup_xp": "DENIED"
        }
    },
    "admin_user": {
        "id": "697996c7659f4e107e3bc81b",
        "date_created": "2026-01-28T04:55:35Z",
        "date_modified": "2026-01-28T04:55:35Z",
        "name": "test developer",
        "email": "test@test.com",
        "role": "ADMIN",
        "company_id": "697996c7659f4e107e3bc81a",
        "campaign_experience": [],
        "asset_ids": []
    }
}
```

!!! info "Automatic User Creation"

    Creating a company also creates a user account with `ADMIN` permissions using your developer username and email. You can update this account later via PATCH requests.

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
            "date_created": "2025-01-15T10:30:00Z",
            "num_campaigns": 3,
            "num_player_characters": 12,
            "num_storyteller_characters": 2,
            "num_npc_characters": 8,
            "num_users": 5
        },
        {
            "id": "def456",
            "name": "Partner Organization",
            "date_created": "2025-02-20T14:45:00Z",
            "num_campaigns": 1,
            "num_player_characters": 4,
            "num_storyteller_characters": 1,
            "num_npc_characters": 3,
            "num_users": 2
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
