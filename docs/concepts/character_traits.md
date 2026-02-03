---
icon: lucide/sliders-horizontal
---

# Trait Values

Character traits represent attributes, skills, disciplines, and other abilities that define a character. Each trait has a numeric value that can be modified through gameplay.

## Currencies for Trait Modification

Traits can be modified using three different currencies:

### Starting Points

Starting points are available during character creation. Use these points to purchase initial trait values before the character enters gameplay.

-   Available only on the character object
-   Spent when increasing traits during character creation
-   Refunded when decreasing traits during character creation
-   Tracked per character, not per user

### Experience Points (XP)

Experience points are earned through gameplay and used to upgrade traits after character creation.

-   Tracked at the campaign level for each user
-   Shared across all characters owned by a user within a campaign
-   Spent when increasing traits with XP
-   Refunded when decreasing traits with XP (refunds do not increase total XP earned)

### No Cost (Storyteller Only)

Storytellers and administrators can modify traits without spending any points at any time. Players can modify traits without spending experience points if the Company's settings allow it.

This is useful for:

-   Correcting mistakes made during character creation
-   Granting abilities as story rewards
-   Adjusting characters for game balance

## Cost Calculations

The cost to upgrade or refund a trait is calculated based on two values defined on each trait:

-   **Initial Cost**: The cost to purchase the first dot (going from 0 to 1)
-   **Upgrade Cost**: The multiplier for subsequent dots

### Upgrade Formula

For each dot purchased:

-   First dot (0 to 1): `initial_cost`
-   Subsequent dots: `new_value × upgrade_cost`

**Example:** A trait with `initial_cost=1` and `upgrade_cost=2` going from value 2 to 4:

-   Dot 3: `3 × 2 = 6`
-   Dot 4: `4 × 2 = 8`
-   Total: `14 points`

### Downgrade Formula

Refunds use the same calculation in reverse. Decreasing from value 4 to 2 would refund 14 points.

## Company Settings

The **Free Trait Updates** company setting controls when players can modify traits without spending points:

| Setting            | Behavior                                                           |
| ------------------ | ------------------------------------------------------------------ |
| `UNRESTRICTED`     | Players can modify traits freely without spending points (default) |
| `WITHIN 24 HOURS`  | Free modifications only within 24 hours of character creation      |
| `STORYTELLER ONLY` | Players must spend XP; only storytellers can make free changes     |

This setting only affects the `NO_COST` currency option. XP and starting points are always available to character owners and storytellers.

## API Endpoints

Two endpoints handle all trait value modifications:

### GET `/value-options`

Retrieves all possible target values with costs and affordability calculations.

**Response includes:**

-   Current trait value and min/max bounds
-   Current XP and starting points available
-   For each possible target value:
    -   Direction (increase or decrease)
    -   Point cost or refund amount
    -   Whether affordable with XP
    -   Whether affordable with starting points
    -   Resulting balance after transaction

```json
{
    "current_value": 2,
    "min_value": 1,
    "max_value": 5,
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
        },
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
        }
    }
}
```

Use this endpoint to display upgrade/downgrade options to users before they commit to a change.

### PUT `/value`

Modifies the trait to a target value using the specified currency.

**Request body:**

```json
{
    "target_value": 4,
    "currency": "XP"
}
```

**Currency options:**

-   `NO_COST` - Requires storyteller/admin privileges
-   `XP` - Available to character owners and storytellers
-   `STARTING_POINTS` - Available to character owners and storytellers

The direction (increase/decrease) is determined automatically from the current value.
