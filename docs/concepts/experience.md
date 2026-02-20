---
icon: lucide/star
---

# Experience

In Valentina Noir, experience belongs to the player, not individual characters, and is tracked at the campaign level. Players may run multiple characters and distribute their experience between them.

## Key Principles

Experience in Valentina Noir differs from traditional World of Darkness in several important ways:

- **Player-based, not character-based** - All experience earned belongs to the player, regardless of which character earned it
- **Campaign-scoped** - Experience is tracked separately for each campaign a player participates in
- **Shareable** - Players can spend their experience pool on any of their characters within a campaign

## Experience Types

| Type                   | Value | Description                                  |
| ---------------------- | ----- | -------------------------------------------- |
| Experience Points (XP) | 1 XP  | The basic currency for character advancement |
| Cool Points (CP)       | 10 XP | Bonus rewards for exceptional roleplay       |

### Experience Points (XP)

Experience points are the standard currency for character advancement. Players earn XP through gameplay and spend it to improve their characters' attributes, skills, and other traits.

### Cool Points (CP)

Cool Points are a special reward that Storytellers can grant to players who demonstrate exceptional roleplay. Each Cool Point is worth 10 experience points and represents memorable moments that enhance the story.

## Experience Tracking

Experience is stored in a `CampaignExperience` record for each user-campaign combination:

| Field         | Description                                         |
| ------------- | --------------------------------------------------- |
| `xp_current`  | Available experience points to spend                |
| `xp_total`    | Lifetime experience points earned (never decreases) |
| `cool_points` | Number of Cool Points earned                        |

!!! info "Tracking Total vs Current XP"

    The `xp_total` field tracks all XP ever earned and never decreases, even when XP is spent. This provides a record of player progression over time. The `xp_current` field reflects spendable XP.

## Spending Experience

Players can spend their experience on:

- **Character Advancement** - Upgrade a character's attributes, abilities, backgrounds, disciplines, and other traits
- **Character Autogeneration** - Use the character autogeneration feature to create a new character for the campaign

## API Endpoints

The Experience API provides endpoints for managing player experience:

| Operation       | Endpoint                                        | Description                                          |
| --------------- | ----------------------------------------------- | ---------------------------------------------------- |
| Get Experience  | `GET /users/{user_id}/experience/{campaign_id}` | Retrieve current experience for a user in a campaign |
| Add XP          | `POST /users/{user_id}/experience/xp/add`       | Award experience points to a player                  |
| Remove XP       | `POST /users/{user_id}/experience/xp/remove`    | Deduct experience points (when spending)             |
| Add Cool Points | `POST /users/{user_id}/experience/cp/add`       | Award Cool Points to a player                        |

## Permission Controls

Who can grant or spend experience is controlled by company settings. See [Company Settings](./company_settings.md) for details on the `permission_grant_xp` setting.

| Permission Level   | Who Can Grant XP                          |
| ------------------ | ----------------------------------------- |
| `UNRESTRICTED`     | Any user can grant XP to any user         |
| `PLAYER`           | Users can only grant XP to themselves     |
| `STORYTELLER_ONLY` | Only Storytellers and Admins can grant XP |
