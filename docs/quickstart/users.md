---
icon: lucide/log-in
---

# Authenticate Your Users

Valentina Noir never authenticates your players directly. Your application owns sign-in: a player logs in through your own system (Google, GitHub, Discord, email, or anything else), and your app then tells Valentina which user is acting. This page links a signed-in person to a Valentina user account and gets them approved to play.

!!! warning "Your app authenticates, Valentina authorizes"

    You authenticate users. Valentina enforces what each user's [role](../technical/user_management.md#user-roles) lets them do. The two layers stay separate, and Valentina trusts your app's assertion of who is acting.

## The On-Behalf-Of header

Once a user exists, you act as them by adding the `On-Behalf-Of` header to game-resource requests. Its value is the user's Valentina ID.

```python
headers = {
    "X-API-KEY": API_KEY,
    "On-Behalf-Of": user_id,  # the Valentina user this request acts as
}
```

The API reads this header to apply role-based permissions and record who did what. You'll send it on every campaign, character, and dice-roll request from here on. For format rules and validation, see [Authentication](../technical/authentication.md#the-on-behalf-of-header).

## Register a user

After a player signs in to your app, check whether you've already linked them to a Valentina account. If not, register one. Registration needs only your API key, not `On-Behalf-Of`.

```python
response = requests.post(
    f"{BASE_URL}/companies/{company_id}/users/register",
    headers={"X-API-KEY": API_KEY},
    json={
        "username": "marcus_player",
        "email": "marcus@example.com",
    },
)
response.raise_for_status()
user_id = response.json()["id"]
```

Only `username` and `email` are required. You can also pass `name_first`, `name_last`, or an OAuth profile (`google_profile`, `discord_profile`, `github_profile`) to enrich the account.

New users start with the `UNAPPROVED` role. They exist, but can't create characters, join campaigns, or roll dice until an admin approves them.

!!! info "Link once, reuse forever"

    Store the returned `user_id` in your own database against your app's user. On later logins, reuse it instead of registering again. To catch a returning player who signed in through a different identity provider, search with [`GET /users/lookup`](../technical/user_management.md#cross-company-user-lookup) before creating a duplicate.

## Approve the user

An admin approves a pending user and assigns a role. Use the `admin_user_id` from [step 1](setup.md) as the acting user, and grant `PLAYER` so they can play.

```python
admin_headers = {"X-API-KEY": API_KEY, "On-Behalf-Of": admin_user_id}

response = requests.post(
    f"{BASE_URL}/companies/{company_id}/users/{user_id}/approve",
    headers=admin_headers,
    json={"role": "PLAYER"},
)
response.raise_for_status()
# response.json()["role"] is now "PLAYER"
```

The user can now act on their own behalf. Each role grants more than the last:

| Role          | Can do                                                             |
| ------------- | ------------------------------------------------------------------ |
| `UNAPPROVED`  | Nothing until an admin approves them.                              |
| `PLAYER`      | Manage their own characters, roll dice, and track experience.      |
| `STORYTELLER` | Manage every character and campaign setting, and award experience. |
| `ADMIN`       | Manage users and company settings.                                 |

For vetting members of an open community, denying applicants, or merging duplicate accounts, see the [user approval workflow](../technical/user_management.md#user-approval-workflow).

## What you have now

You have an approved `PLAYER` and you know how to act as them with `On-Behalf-Of`. Next, [create a campaign](campaigns.md) for them to play in.
