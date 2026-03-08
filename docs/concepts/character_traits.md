---
icon: lucide/sliders-horizontal
---

# Character Traits

Character traits represent attributes, skills, disciplines, and other abilities on a character sheet. Each trait has a numeric value (measured in dots) that you can modify through gameplay.

This page covers how to add, modify, and remove traits from a character. For information on the traits themselves (what's available per class and game version), see the [character blueprint](./character_blueprint.md) documentation.

## Adding Traits

Add traits to a character using one of two approaches.

### Assigning Constant Traits

Assign an existing system trait to a character by providing the `trait_id`, starting `value`, and `currency`.

```json
{
    "trait_id": "69679d6b92e8772cd93d8185",
    "value": 2,
    "currency": "NO_COST" // (1)!
}
```

1. NO_COST is only available if the company settings allow it or for storytellers and admins.

The system validates that the trait exists, the value falls within the trait's min/max bounds, and the trait isn't already assigned to the character.

### Creating Custom Traits

Create a trait unique to a single character. Custom traits share the same fields as core traits but remain unavailable to other characters. They're useful for representing unique abilities that don't exist in the standard trait list.

Provide the trait name, parent category, and optional cost overrides. If you omit `initial_cost` or `upgrade_cost`, the trait inherits costs from its parent category.

```json
{
    "name": "Cryptography",
    "description": "Skill at deciphering encoded messages",
    "parent_category_id": "69679d6b92e8772cd93d8185",
    "max_value": 5,
    "value": 1
}
```

!!! info "Custom Trait Naming"

    Custom trait names must be unique on the character (case-insensitive) and can't match any existing system trait name.

## Modifying Trait Values

Modify trait values using one of three currencies.

### Starting Points

Starting points are granted to a character at creation. Spend them to purchase initial trait values and receive refunds when decreasing traits. Starting points are tracked per character.

### Experience Points (XP)

Earn experience points through gameplay to upgrade traits. XP is tracked at the campaign level per user and shared across all characters that user owns in the campaign.

- Spent when increasing traits
- Refunded when decreasing traits (refunds don't increase total XP earned)

### No Cost

Storytellers and administrators can modify traits without spending points at any time. Players can also make free modifications if [company settings](./company_settings.md) allow it.

Use no-cost modifications to:

- Add traits to a newly created character
- Correct character creation mistakes
- Grant abilities as story rewards
- Adjust characters for game balance

## Cost Calculations

Calculate upgrade or refund costs using two trait properties:

- **Initial Cost** - Cost to purchase the first dot (0 to 1)
- **Upgrade Cost** - Multiplier for subsequent dots

### Upgrade Formula

The cost for each dot is calculated as follows:

- First dot (0 to 1): `initial_cost`
- Subsequent dots: `new_value × upgrade_cost`

!!! example "Upgrade Example"

    A trait with `initial_cost=1` and `upgrade_cost=2` going from value 2 to 4:

    -   Dot 3: `3 × 2 = 6`
    -   Dot 4: `4 × 2 = 8`
    -   **Total: 14 points**

### Downgrade Formula

Refunds use the same calculation in reverse.

!!! example "Downgrade Example"

    Decreasing from value 4 to 2 refunds 14 points.

## Flaw Traits

Traits linked to the "Flaws" advantage category have a reversed currency economy. When a player adds or increases a flaw, they **receive** XP or starting points instead of spending them. When a player decreases or removes a flaw, they **spend** XP or starting points instead of receiving a refund.

The cost formulas remain the same — only the direction of currency flow is inverted. `NO_COST` modifications are unaffected and work the same as for any other trait.

The `value-options` endpoint reflects this reversal: increase options for flaws are always affordable (since they grant currency), while decrease options check affordability against the user's available balance.

## Derived Traits

Certain traits are automatically recalculated when their source traits change. Examples:

- **Willpower** — Computed as `Composure + Resolve`. Updated whenever either source trait changes. If the Willpower trait doesn't exist on the character, the system creates it.
- **Total Renown** (werewolves only) — Computed as `Honor + Wisdom + Glory`. Stored on the character's werewolf attributes.

## Deleting Traits

Delete a trait from a character with an optional refund. Specify a `currency` to receive a refund based on the trait's current value, or use `NO_COST` to delete without a refund.

## Company Settings

The **Free Trait Updates** setting controls when players can modify traits without spending points.

| Setting            | Behavior                                                       |
| ------------------ | -------------------------------------------------------------- |
| `UNRESTRICTED`     | Players modify traits freely without spending points (default) |
| `WITHIN 24 HOURS`  | Free modifications only within 24 hours of character creation  |
| `STORYTELLER ONLY` | Players must spend XP; only storytellers make free changes     |

!!! info "Currency Availability"

    This setting only affects the `NO_COST` currency. XP and starting points remain available to character owners and storytellers regardless of this setting.

## API Endpoints

The trait API provides endpoints for listing, adding, modifying, and removing traits.

### GET `/traits`

List all traits assigned to a character. Supports pagination and optional filtering by `parent_category_id` to return only traits within a specific category.

### GET `/traits/{character_trait_id}`

Retrieve a single character trait with its full details.

### POST `/traits/assign`

Assign an existing system trait to the character. See [Assigning Constant Traits](#assigning-constant-traits) above.

### POST `/traits/create`

Create a custom trait for the character. See [Creating Custom Traits](#creating-custom-traits) above.

### GET `/traits/{character_trait_id}/value-options`

Retrieve all possible target values with costs and affordability calculations. Use this endpoint to display upgrade and downgrade options before users commit to changes.

The response includes:

- Current trait value and min/max bounds
- Current XP and starting points available
- For each possible target value:
    - Direction (increase or decrease)
    - Point cost or refund amount
    - Affordability with XP and starting points
    - Balance after transaction
- A `DELETE` option showing the refund for removing the trait entirely

```json
{
    "name": "Intelligence",
    "trait": {
        "id": "69679d6b92e8772cd93d8185",
        "name": "Intelligence",
        "description": "Your character's intelligence score.",
        "max_value": 5,
        "min_value": 0,
        "show_when_zero": true,
        "parent_category_id": "69679d6b92e8772cd93d8186"
        ...
    },
    "current_value": 2,
    "xp_current": 0,
    "starting_points_current": 0,
    "options": {
        "1": {
            "direction": "decrease",
            "point_change": 10,
            "can_use_xp": true,
            "xp_after": 10,
            "can_use_starting_points": true,
            "starting_points_after": 10
        }, // (1)!
        "3": {
            "direction": "increase",
            "point_change": 15,
            "can_use_xp": false,
            "xp_after": -15,
            "can_use_starting_points": false,
            "starting_points_after": -15
        },
        "4": {
            "direction": "increase",
            "point_change": 35,
            "can_use_xp": false,
            "xp_after": -35,
            "can_use_starting_points": false,
            "starting_points_after": -35
        },
        "5": {
            "direction": "increase",
            "point_change": 60,
            "can_use_xp": false,
            "xp_after": -60,
            "can_use_starting_points": false,
            "starting_points_after": -60
        },
        "DELETE": {
            "direction": "decrease",
            "point_change": 10,
            "can_use_xp": true,
            "xp_after": 10,
            "can_use_starting_points": true,
            "starting_points_after": 0
        }
    }
}
```

1. Trait value "2" is missing because it is the current value.

### PUT `/traits/{character_trait_id}/value`

Modify a trait to a target value using the specified currency. The system automatically determines direction (increase or decrease) from the current value.

**Request body:**

```json
{
    "target_value": 4,
    "currency": "XP"
}
```

**Available currencies:**

| Currency          | Availability                      |
| ----------------- | --------------------------------- |
| `NO_COST`         | Storytellers and admins only      |
| `XP`              | Character owners and storytellers |
| `STARTING_POINTS` | Character owners and storytellers |

### DELETE `/traits/{character_trait_id}`

Remove a trait from the character. Optionally specify a `currency` query parameter to receive a refund. See [Deleting Traits](#deleting-traits) above.
