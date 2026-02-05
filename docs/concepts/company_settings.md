---
icon: lucide/settings
---

# Company Settings

Company administrators configure these settings to customize the game experience.

## Campaign Management

Control who creates, updates, and deletes campaigns, books, and chapters.

| Setting | Behavior |
| --- | --- |
| `UNRESTRICTED` | Any user manages campaigns, books, and chapters (default) |
| `STORYTELLER ONLY` | Only storytellers manage campaigns, books, and chapters |

## XP Management

Control who grants experience points to players.

| Setting | Behavior |
| --- | --- |
| `UNRESTRICTED` | Any user grants experience (default) |
| `STORYTELLER ONLY` | Only storytellers grant experience |

## Character Autogeneration

### XP Cost

Set the experience cost to use the character autogeneration engine.

-   Default: `1 XP`
-   Range: Any positive integer (0-100)

### Number of Characters

Set how many characters the autogeneration engine creates for user selection.

-   Default: `1`
-   Range: 1-10 characters

## Character Management

### Free Trait Updates

Control when players update traits without spending experience points.

| Setting | Behavior |
| --- | --- |
| `UNRESTRICTED` | Character owners change trait values at any time without cost (default) |
| `WITHIN 24 HOURS` | Character owners make free changes within 24 hours of character creation |
| `STORYTELLER ONLY` | Only storytellers make free trait changes |

!!! info "Storyteller Privileges"
    Storytellers and admins always modify trait values on any character without spending experience points, regardless of this setting.
