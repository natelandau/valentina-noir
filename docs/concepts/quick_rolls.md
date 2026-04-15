---
icon: lucide/zap
---

# Quick Rolls

Quick rolls let users save trait combinations for one-click dice rolling. Instead of selecting traits manually each time, a user creates a named quick roll (like "Shoot" combining `Firearms` and `Dexterity`) and reuses it across any of their characters.

Quick rolls belong to the user, not to a specific character. When executing a quick roll, the user picks a character, and the API sums that character's values for the referenced traits to determine the dice pool.

## How Quick Rolls Work

A quick roll stores a name and a list of trait IDs. When executed against a character:

1. The API looks up the character's assigned values for each trait in the quick roll
2. The trait values are summed to determine the total dice pool
3. The dice are rolled using the [dice rolling system](./dice.md)
4. The result is saved as a dice roll record

If the character doesn't have one or more of the referenced traits, the roll fails with a validation error.

## Quick Roll Fields

| Field | Type | Description |
|---|---|---|
| `name` | string | Display name for the quick roll. 3-50 characters, unique per user. |
| `description` | string or null | Optional description. 3+ characters if provided. |
| `trait_ids` | list of strings | Trait IDs that make up the dice pool. At least one required. |
| `user_id` | string | The owning user's ID. Set automatically by the API. |

## Managing Quick Rolls

Quick roll endpoints are nested under a user:

```
/api/v1/companies/{company_id}/users/{user_id}/quickrolls
```

Any company member can **read** quick rolls (list and detail). **Creating, updating, and deleting** quick rolls requires the [`On-Behalf-Of`](../technical/authentication.md#the-on-behalf-of-header) header, and the acting user must be the owner of the quick rolls or a company admin.

### Creating a Quick Roll

Use trait IDs from the [character blueprint](./character_blueprint.md) to define the dice pool. The API validates that all trait IDs reference existing traits.

```json
{
    "name": "Shoot",
    "description": "Firearms + Dexterity",
    "trait_ids": [
        "69679d6b92e8772cd93d8185",
        "69679d6b92e8772cd93d8186"
    ]
}
```

Quick roll names must be unique per user. Creating a quick roll with a name that already exists returns a validation error.

### Listing Quick Rolls

```shell
GET /api/v1/companies/{company_id}/users/{user_id}/quickrolls?limit=10&offset=0
```

Returns the user's quick rolls sorted alphabetically by name. Supports standard [pagination](../technical/pagination.md).

### Updating a Quick Roll

```shell
PATCH /api/v1/companies/{company_id}/users/{user_id}/quickrolls/{quickroll_id}
```

Partial updates are supported — send only the fields you want to change. The same validation rules apply (name uniqueness, at least one trait).

### Deleting a Quick Roll

```shell
DELETE /api/v1/companies/{company_id}/users/{user_id}/quickrolls/{quickroll_id}
```

Quick rolls are soft-deleted (archived) and no longer appear in listings.

## Executing a Quick Roll

Execute a saved quick roll against a character to roll dice:

```shell
POST /api/v1/companies/{company_id}/dicerolls/quickroll
```

```json
{
    "quickroll_id": "69679d6b92e8772cd93d8185",
    "character_id": "69679d6b92e8772cd93d8186",
    "difficulty": 6,
    "comment": "Shooting at the fleeing suspect"
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `quickroll_id` | string | required | ID of the saved quick roll |
| `character_id` | string | required | Character whose trait values determine the dice pool |
| `difficulty` | integer | 6 | Target number for each die (see [dice rolling](./dice.md)) |
| `comment` | string or null | null | Optional note saved with the roll result. Defaults to "Quick roll: {name}" if omitted. |

The API sums the character's values for all traits in the quick roll to determine how many D10s to roll. For example, if the character has `Firearms: 3` and `Dexterity: 4`, the quick roll produces a pool of 7 dice.

The response is a dice roll object containing the full result (individual die values, successes, outcome). See the [API documentation](https://api.valentina-noir.com/docs) for the complete response schema.

!!! warning "Character Must Have the Traits"

    The character must have all traits referenced by the quick roll. If any trait is missing from the character, the API returns a validation error. Build your UI to warn users when a quick roll references traits their selected character doesn't have.
