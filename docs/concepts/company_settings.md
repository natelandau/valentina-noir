---
icon: lucide/settings
---

# Company Settings

Company settings let administrators tailor gameplay rules and permissions for their gaming group. Your client application needs to respect these settings — they determine which actions are available to each user role, how much autogeneration costs, and when free trait changes are allowed.

Retrieve the current settings from the company object:

```shell
GET /api/v1/companies/{company_id}
```

The `settings` field in the response contains all configurable values.

## Campaign Management

Control who creates, updates, and deletes campaigns, books, and chapters.

| Setting        | Behavior                                                  |
| -------------- | --------------------------------------------------------- |
| `UNRESTRICTED` | Any user manages campaigns, books, and chapters (default) |
| `STORYTELLER`  | Only storytellers manage campaigns, books, and chapters   |

## XP Management

Control who grants experience points to players.

| Setting        | Behavior                             |
| -------------- | ------------------------------------ |
| `UNRESTRICTED` | Any user grants experience (default) |
| `PLAYER`       | Users can only grant XP to themselves |
| `STORYTELLER`  | Only storytellers grant experience   |

## Character Autogeneration

### XP Cost

Set the experience cost to use the character autogeneration engine.

- Default: `1 XP`
- Range: Any positive integer (0-100)

### Number of Characters

Set how many characters the autogeneration engine creates for user selection.

- Default: `1`
- Range: 1-10 characters

## Character Management

### Free Trait Updates

Control when players update traits without spending experience points.

| Setting            | Behavior                                                                 |
| ------------------ | ------------------------------------------------------------------------ |
| `UNRESTRICTED`     | Character owners change trait values at any time without cost (default)  |
| `WITHIN_24_HOURS`  | Character owners make free changes within 24 hours of character creation |
| `STORYTELLER`      | Only storytellers make free trait changes                                |

!!! info "Storyteller Privileges"

    Storytellers and admins always modify trait values on any character without spending experience points, regardless of this setting.
