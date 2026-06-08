---
icon: lucide/log-in
---

# Authenticate Your Users

Valentina Noir never authenticates your players directly. Your application owns sign-in: a player logs in through your own system (Google, GitHub, Discord, Apple, email, or anything else), and your app then tells Valentina which user is acting. This page links a signed-in person to a Valentina user account and gets them approved to play.

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

## Sign in a user with a provider

If your users sign in with Apple, Google, Discord, or GitHub, forward the credential to the `identify` endpoint. Valentina verifies it with the provider and returns the Valentina user, creating one if needed. One call handles lookup, linking, and first-time creation.

```bash
curl -X POST "$API/companies/$COMPANY_ID/auth/identify" \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"provider": "google", "token": "<google-id-token>"}'
```

| Provider | Send as `provider` | `token` type            |
| -------- | ------------------- | ----------------------- |
| Apple    | `apple`             | OIDC ID token (JWT)     |
| Google   | `google`            | OIDC ID token (JWT)     |
| Discord  | `discord`           | OAuth access token      |
| GitHub   | `github`            | OAuth access token      |

The response is always `200 OK`:

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

The `user` object is the full user response; fields are abbreviated here.

Store `user.id` and use it as `On-Behalf-Of` from that point on. The `resolution` field tells you whether Valentina matched an existing user, linked a user by email, or created a new one. A `created` user starts as `UNAPPROVED` and needs admin approval before they can play.

!!! info "Link once, reuse forever"

    Store the returned `user.id` in your own database against your app's user record. On later logins you already have the ID and don't need to call `identify` again unless the session expired or the user switched providers.

For full details on resolution order, error codes, and Apple/Google audience configuration, see [Verified Identity](../technical/authentication.md#verified-identity) and the [identify endpoint reference](../technical/user_management.md#identify-resolve-a-provider-login).

A newly created user starts with the `UNAPPROVED` role. They exist, but can't create characters, join campaigns, or roll dice until an admin approves them.

## Provision a user without a supported provider

If a player signs in through your app some other way (email and password, or a provider Valentina doesn't verify), an admin creates the account directly. This needs an admin acting user, supplied with `On-Behalf-Of`.

```python
admin_headers = {"X-API-KEY": API_KEY, "On-Behalf-Of": admin_user_id}

response = requests.post(
    f"{BASE_URL}/companies/{company_id}/users",
    headers=admin_headers,
    json={
        "username": "marcus_player",
        "email": "marcus@example.com",
        "role": "PLAYER",
    },
)
response.raise_for_status()
user_id = response.json()["id"]
```

An admin-created user is assigned its role at creation, so it skips the approval step below. Provider-identity profiles are never set here; they are written only when a verified credential reaches `identify` or the [link endpoint](../technical/user_management.md#link-attach-a-second-provider-identity).

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
