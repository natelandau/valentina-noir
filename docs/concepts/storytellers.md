---
icon: lucide/user-circle
---

# Storytellers

Storytellers (game masters) have elevated permissions that affect how your client application presents options to different users. This page covers what storytellers can do that players can't and how to build your UI around those differences.

For the full list of user roles, see [User Management](../technical/user_management.md#user-roles).

## What Storytellers Can Do

Storyteller and admin users have access to actions that players don't. The exact scope depends on [company settings](./company_settings.md):

| Action | Player | Storyteller | Controlled By |
| --- | --- | --- | --- |
| Create/edit/delete campaigns | Depends | Always | `permission_manage_campaign` |
| Grant experience points | Depends | Always | `permission_grant_xp` |
| Make free trait changes | Depends | Always | `permission_free_trait_changes` |
| View storyteller-type characters | No | Yes | — |
| Edit any character | No | Yes | — |
| Archive or kill characters | No | Yes | — |
| Autogenerate characters (single) | No | Yes | — |

When a company setting is `UNRESTRICTED`, players gain that capability too. When set to `STORYTELLER`, only storytellers and admins can perform the action. Check the company settings to determine which UI elements to show each user.

## Hidden Characters

Storytellers can create characters with `type: STORYTELLER`. These characters are only visible to storyteller and admin users — players can't see them in character listings or campaign views.

Use storyteller-type characters for:

- Antagonists whose abilities are secret
- Surprise allies or mystery characters
- Important NPCs that need full character sheets and dice rolling but aren't player-facing

For characters that players can openly interact with, use the `NPC` type instead. See [Character Types](./characters.md#character-types) for the full list.

## Building a Storyteller UI

When designing your application, check the requesting user's role to determine what to display:

- **Show/hide management controls** — Campaign creation, XP granting, and free trait editing buttons depend on both the user's role and the company's permission settings
- **Filter character lists** — Storyteller-type characters only appear for storyteller and admin users
- **Enable bulk actions** — Storytellers can edit any character in their campaigns, not just their own

!!! warning "Permission Denied Errors"

    If you receive a `403 Forbidden` error, verify that the requesting user has the appropriate role and that the company permission settings allow the requested action. See [Authorization Errors](../technical/user_management.md#authorization-errors) for common causes.
