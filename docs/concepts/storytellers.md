---
icon: lucide/user-circle
---

# Storytellers

Storytellers (game masters) have elevated permissions to manage campaigns, characters, and player experience in Valentina Noir. This guide covers the tools and capabilities available to storytellers.

## User Roles

Valentina Noir supports three user roles with different permission levels:

| Role | Description |
|------|-------------|
| `PLAYER` | Standard player with access to their own characters and data |
| `STORYTELLER` | Game master with elevated permissions to manage campaigns and characters |
| `ADMIN` | Full administrative access to all company resources |

## Character Types

Characters in Valentina Noir have different visibility and ownership rules based on their type:

| Type | Visibility | Use Case |
|------|------------|----------|
| `PLAYER` | Visible to all campaign members | Player-controlled characters |
| `NPC` | Visible to all campaign members | Non-player characters everyone can see |
| `STORYTELLER` | Visible only to Storytellers and Admins | Secret NPCs, antagonists, hidden characters |
| `DEVELOPER` | Internal use only | Testing and development characters |

### Storyteller Characters

Storyteller characters provide a way to manage NPCs that players shouldn't see. This lets you:

- Track NPC statistics, traits, and abilities privately
- Use quick dice rolling for secret NPC actions
- Prepare antagonists and surprise characters without spoiling the story
- Maintain the full character sheet workflow for important NPCs

!!! tip "When to Use Storyteller vs NPC Type"
    Use `STORYTELLER` type for characters whose abilities should remain secret (antagonists, mystery characters, surprise allies). Use `NPC` type for characters that players can openly interact with and whose capabilities aren't secret.

## Storyteller Permissions

Storytellers have access to actions that regular players don't, controlled by company settings:

### Campaign Management

When `permission_manage_campaign` is set to `STORYTELLER`:

- Only Storytellers and Admins can create, edit, and delete campaigns
- Players can view and participate in campaigns but not modify them

### Experience Grants

When `permission_grant_xp` is set to `STORYTELLER`:

- Only Storytellers and Admins can award experience points and Cool Points
- Players cannot grant experience to themselves or others

### Trait Changes

When `permission_free_trait_changes` is set to `STORYTELLER`:

- Only Storytellers and Admins can make free (non-XP-cost) changes to character traits
- Players must spend XP to modify their characters

See [Company Settings](./company_settings.md) for full details on permission configuration.

## Managing Characters

Storytellers can manage any character in their campaigns:

- **View** - See all characters, including Storyteller-type characters
- **Edit** - Modify any character's properties, traits, and status
- **Delete** - Remove characters from campaigns
- **Archive** - Archive characters that are no longer active

### Character Lifecycle

Characters can have different statuses managed by Storytellers:

| Status | Description |
|--------|-------------|
| `ALIVE` | Active character in the campaign |
| `DEAD` | Character has died in-game |
| `ARCHIVED` | Character removed from active play |

## Experience and Rewards

Storytellers can manage player experience through the Experience API:

- **Add XP** - Award experience points for session participation, completing objectives, good roleplay
- **Remove XP** - Deduct experience when players spend it on advancement
- **Award Cool Points** - Grant special rewards for exceptional roleplay moments

Each Cool Point is worth 10 experience points and is a way to recognize outstanding player contributions.

## API Access

Storyteller actions are verified through role-based guards. When making API requests as a storyteller:

1. Ensure the requesting user has `STORYTELLER` or `ADMIN` role
2. Include the `requesting_user_id` field in requests that modify data
3. The API validates permissions before executing restricted actions

!!! warning "Permission Denied Errors"
    If you receive a `403 Forbidden` error, verify that:

    - The requesting user has the appropriate role
    - The company permission settings allow the requested action
    - The `requesting_user_id` in the request body matches a valid Storyteller or Admin
