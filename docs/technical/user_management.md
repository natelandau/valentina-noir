---
icon: lucide/users
---

# User Management

## Overview

Control what actions end-users can perform within your application through user roles. [Developer permissions](authentication.md#developer-permissions) control company governance (managing the company, its settings, and developer access). User roles control **in-game actions** — what each end-user can do within a company.

The API enforces game rules based on user roles. For example, only storytellers can grant XP, and players can only edit their own characters. Your application assigns users to the correct roles, and the API enforces what each role can do.

!!! warning "Your Responsibility"

    **Valentina Noir doesn't authenticate end-users directly.** Your application authenticates users through your own system (OAuth, passwords, etc.), then makes API calls on their behalf using the `user_id` in the request path. The API trusts your application's assertion of which user is making the request.

## Cross-Client Access

Users maintain the same identity and permissions across all clients that access Valentina.

```mermaid
flowchart LR
    subgraph clients [Your Clients]
        Web[Web App]
        Mobile[Mobile App]
        Bot[Discord Bot]
    end

    subgraph valentina [Valentina API]
        User[User Account<br/>role: STORYTELLER]
    end

    Web --> User
    Mobile --> User
    Bot --> User
```

**What this means:**

- A storyteller on your web app has storyteller permissions on your mobile app
- Character data, dice rolls, and campaign progress sync across all clients
- Role changes take effect immediately across all clients

### Linking Users

Link your authenticated users to Valentina user accounts.

**Workflow:**

1. Check if you have a stored Valentina `user_id` for this user
2. If not, create a new user via `POST /api/v1/companies/{company_id}/users`
3. Store the returned `user_id` in your database
4. Use this `user_id` in subsequent API calls

```python
import requests

def get_or_create_valentina_user(local_user, company_id, api_key):
    """Link a local user to a Valentina user account."""
    # Return existing user_id if already linked
    if local_user.valentina_user_id:
        return local_user.valentina_user_id

    # Create a new user in Valentina
    response = requests.post(
        f"https://api.valentina-noir.com/api/v1/companies/{company_id}/users",
        headers={"X-API-KEY": api_key},
        json={
            "name_first": local_user.name_first,
            "name_last": local_user.name_last,
            "username": local_user.username,
            "email": local_user.email,
            "role": "PLAYER"
        }
    )
    response.raise_for_status()

    # Store and return the Valentina user_id
    valentina_user = response.json()
    local_user.valentina_user_id = valentina_user["id"]
    local_user.save()

    return valentina_user["id"]
```

### SSO Registration

For automated SSO onboarding flows where no authenticated Valentina user is available to act as the requester, use the dedicated registration endpoint. This creates a user with the `UNAPPROVED` role — no `requesting_user_id` is required.

```shell
POST /api/v1/companies/{company_id}/users/register
```

```json
{
    "username": "newplayer",
    "email": "newplayer@example.com",
    "google_profile": {
        "email": "newplayer@gmail.com",
        "username": "New Player"
    }
}
```

The registered user must be [approved by an admin](#approve-a-user) before they can access features.

#### Checking for Existing Users

Before registering a new user, check if one already exists with the same email to avoid duplicates:

```shell
GET /api/v1/companies/{company_id}/users?email=newplayer@example.com
```

If the email matches an existing user, link to that account instead of creating a duplicate. If a duplicate `UNAPPROVED` user was already created, use the [merge endpoint](#merging-users) to combine the accounts.

### Merging Users

When a user authenticates via a new identity provider and a duplicate `UNAPPROVED` account is created, merge it into the existing primary account. The merge copies OAuth profile fields (Google, GitHub, Discord) from the secondary user to the primary user, filling in only empty fields. The secondary user is then deleted.

```shell
POST /api/v1/companies/{company_id}/users/merge
```

```json
{
    "primary_user_id": "existing_user_id",
    "secondary_user_id": "unapproved_user_id",
    "requesting_user_id": "admin_user_id"
}
```

**Requirements:**

- The secondary user must have the `UNAPPROVED` role
- The requesting user must be an `ADMIN`
- Both users must belong to the same company

The response returns the updated primary user with any new profile fields absorbed from the secondary.

## User Roles

Each user belongs to a [company](companies.md) and has a role that determines their permissions. Roles remain consistent across all clients (web, mobile, Discord bot).

| Role          | Description                                    |
| ------------- | ---------------------------------------------- |
| `UNAPPROVED`  | Pending admin approval - no access to features |
| `PLAYER`      | Basic gameplay access - manage own characters  |
| `STORYTELLER` | Campaign management - manage all characters    |
| `ADMIN`       | Full user management and administrative access |

### The UNAPPROVED Role

New users can be created with the `UNAPPROVED` role. These users exist in the system but can't access any features until an admin approves them. This is useful when your application requires an approval step before granting access — for example, a gaming community that vets new members before they can join campaigns.

Unapproved users:

- Can't create or manage characters
- Can't join campaigns or roll dice
- Can't access experience points or quick rolls
- Remain in this state until an admin approves or denies them

See [User Approval Workflow](#user-approval-workflow) for how to manage unapproved users.

### Role Capabilities

Each role builds on the capabilities of the previous role.

??? info "Player Capabilities"

    -   Create and manage their own characters
    -   Roll dice and track experience
    -   View campaign information
    -   Cannot modify other players' characters

??? info "Storyteller Capabilities"

    -   All player capabilities
    -   Manage any character in their campaigns
    -   Modify campaign settings (danger, desperation)
    -   Create and manage NPCs
    -   Award experience points

??? info "Admin Capabilities"

    -   All storyteller capabilities
    -   Manage other users within the company
    -   Change user roles
    -   Access administrative endpoints

## Checking User Roles

Retrieve a user's role when fetching their details:

```shell
GET /api/v1/companies/{company_id}/users/{user_id}
```

Response:

```json
{
    "id": "user123",
    "name_first": "John",
    "name_last": "Doe",
    "username": "johndoe123",
    "role": "STORYTELLER",
    "company_id": "abc123"
}
```

## Authorization Errors

The API returns a `403 Forbidden` response when a user attempts an action beyond their role's permissions.

```json
{
    "status": 403,
    "title": "Forbidden",
    "detail": "No rights to access this resource",
    "instance": "/api/v1/companies/abc123/users/user456/campaigns/camp789/characters/char012"
}
```

### Common Causes

| Scenario                           | Required Role |
| ---------------------------------- | ------------- |
| Unapproved user accessing features | `PLAYER`+     |
| Player editing another's character | `STORYTELLER` |
| Player modifying campaign settings | `STORYTELLER` |
| Storyteller managing other users   | `ADMIN`       |
| Approving or denying users         | `ADMIN`       |

## User Approval Workflow

When you create users with the `UNAPPROVED` role, admins can review and approve or deny them through dedicated endpoints. This gives you control over who joins your company.

```mermaid
flowchart LR
    Create["Create user<br/>role: UNAPPROVED"] --> Pending["Pending Approval"]
    Pending --> Approve["Admin approves<br/>assigns role"]
    Pending --> Deny["Admin denies<br/>user archived"]
    Approve --> Active["Active User<br/>PLAYER / STORYTELLER / ADMIN"]
```

### List Pending Users

Retrieve all users awaiting approval within a company. Only admins can access this endpoint.

```shell
GET /api/v1/companies/{company_id}/users/unapproved?requesting_user_id={admin_user_id}
```

The `requesting_user_id` query parameter identifies the admin making the request. The response uses standard [pagination](pagination.md):

```json
{
    "items": [
        {
            "id": "user456",
            "username": "newplayer",
            "email": "newplayer@example.com",
            "role": "UNAPPROVED",
            "company_id": "abc123"
        }
    ],
    "total": 1,
    "limit": 10,
    "offset": 0
}
```

### Approve a User

Approve a pending user and assign them a role. The role must be `PLAYER`, `STORYTELLER`, or `ADMIN` — you can't approve a user back to `UNAPPROVED`.

```shell
POST /api/v1/companies/{company_id}/users/{user_id}/approve
```

```json
{
    "role": "PLAYER",
    "requesting_user_id": "admin_user_id"
}
```

The response returns the updated user object with the new role.

### Deny a User

Deny a pending user to remove them from the company. The user is archived (soft-deleted) and no longer appears in user listings.

```shell
POST /api/v1/companies/{company_id}/users/{user_id}/deny
```

```json
{
    "requesting_user_id": "admin_user_id"
}
```

> **Note:** Denied users are archived, not permanently deleted. They won't appear in queries but their data is preserved.

### Example: Approval Flow

Here's a complete example of registering a user via SSO and then approving them:

```python
import requests

API_URL = "https://api.valentina-noir.com/api/v1"
HEADERS = {"X-API-KEY": "your-api-key"}

# Step 1: Check if user already exists by email
response = requests.get(
    f"{API_URL}/companies/{company_id}/users",
    headers=HEADERS,
    params={"email": "newplayer@example.com"},
)
existing_users = response.json()["items"]

if existing_users:
    # User already exists — link to their account
    valentina_user_id = existing_users[0]["id"]
else:
    # Step 2: Register the user (no requesting_user_id needed)
    response = requests.post(
        f"{API_URL}/companies/{company_id}/users/register",
        headers=HEADERS,
        json={
            "username": "newplayer",
            "email": "newplayer@example.com",
            "google_profile": {
                "email": "newplayer@gmail.com",
                "username": "New Player",
            },
        },
    )
    new_user = response.json()
    valentina_user_id = new_user["id"]

# Step 3: List pending users (admin reviews)
response = requests.get(
    f"{API_URL}/companies/{company_id}/users/unapproved",
    headers=HEADERS,
    params={"requesting_user_id": admin_user_id},
)
pending_users = response.json()["items"]

# Step 4: Approve the user with a role
response = requests.post(
    f"{API_URL}/companies/{company_id}/users/{valentina_user_id}/approve",
    headers=HEADERS,
    json={
        "role": "PLAYER",
        "requesting_user_id": admin_user_id,
    },
)
approved_user = response.json()
# approved_user["role"] is now "PLAYER"
```

## Best Practices

!!! tip "Cache User Roles"

    Avoid fetching user details on every request by caching role information locally.

!!! warning "Role Changes Take Effect Immediately"

    Changing a user's role affects all their access across all clients instantly.

**Key recommendations:**

1. **Authenticate in your system first** - Use your own authentication before making Valentina API calls
2. **Store the user_id mapping** - Persist the relationship between your users and Valentina accounts
3. **Handle 403 errors gracefully** - Provide clear feedback when users attempt unauthorized actions
4. **Respect role boundaries in your UI** - Hide or disable features users cannot access
5. **Consider role escalation carefully** - Role changes affect access immediately across all clients
6. **Use the approval workflow for open communities** - Create users as `UNAPPROVED` when you want admin vetting before granting access
