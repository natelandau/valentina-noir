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

| Setting        | Behavior                              |
| -------------- | ------------------------------------- |
| `UNRESTRICTED` | Any user grants experience (default)  |
| `PLAYER`       | Users can only grant XP to themselves |
| `STORYTELLER`  | Only storytellers grant experience    |

## Character Autogeneration

### XP Cost

Set the experience cost to use the character autogeneration engine.

- Default: `1 XP`
- Range: Any positive integer (0-100)

### Number of Characters

Set how many characters the autogeneration engine creates for user selection.

- Default: `1`
- Range: 1-10 characters

### Starting Points

Set the starting points to grant to a character when it is created. Players may spend starting points to increase or add traits to the character without spending experience points.

- Default: `0`
- Range: 0-100 starting points per character

## Character Management

### Free Trait Updates

Control when players update traits without spending experience points.

| Setting           | Behavior                                                                 |
| ----------------- | ------------------------------------------------------------------------ |
| `UNRESTRICTED`    | Character owners change trait values at any time without cost (default)  |
| `WITHIN_24_HOURS` | Character owners make free changes within 24 hours of character creation |
| `STORYTELLER`     | Only storytellers make free trait changes                                |

!!! info "Storyteller Privileges"

    Storytellers and admins always modify trait values on any character without spending experience points, regardless of this setting.

### XP Recoup

Control whether players can lower a trait value (which would otherwise refund the XP difference).

| Setting          | Behavior                                                                                                                                    |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `UNRESTRICTED`   | Players may lower any trait using the `XP` currency and recoup the difference                                                               |
| `DENIED`         | Lowering a trait with the `XP` currency is blocked entirely (default)                                                                       |
| `WITHIN_SESSION` | A player may lower a trait with the `XP` currency if they raised it within the past hour, but never below its value at the start of editing |

This setting only applies to trait updates that specify the `XP` currency. Updates using `NO_COST` or `STARTING_POINTS` are never affected.

The `WITHIN_SESSION` window is a sliding 1-hour activity window per (user, character, trait). The "start of editing" anchor is captured the first time the user touches a trait in a fresh window and is not updated by subsequent raises.
