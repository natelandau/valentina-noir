---
icon: lucide/sliders-horizontal
---

# Trait Values

Character traits represent attributes, skills, disciplines, and other abilities. Each trait has a numeric value you can modify through gameplay.

## Modification Currencies

Modify traits using one of three currencies:

### Starting Points

Use starting points during character creation to purchase initial trait values.

-   Available only during character creation
-   Spent when increasing traits
-   Refunded when decreasing traits
-   Tracked per character

### Experience Points (XP)

Earn experience points through gameplay to upgrade traits after character creation.

-   Tracked at the campaign level per user
-   Shared across all user-owned characters in a campaign
-   Spent when increasing traits
-   Refunded when decreasing traits (refunds don't increase total XP earned)

### No Cost

Storytellers and administrators modify traits without spending points at any time. Players can modify traits without cost if [company settings](./company_settings.md) allow it.

Use no-cost modifications to:

-   Correct character creation mistakes
-   Grant abilities as story rewards
-   Adjust characters for game balance

## Cost Calculations

Calculate upgrade or refund costs using two trait values:

-   **Initial Cost** - Cost to purchase the first dot (0 to 1)
-   **Upgrade Cost** - Multiplier for subsequent dots

### Upgrade Formula

Calculate the cost for each dot:

-   First dot (0 to 1): `initial_cost`
-   Subsequent dots: `new_value × upgrade_cost`

!!! example "Upgrade Example"
    A trait with `initial_cost=1` and `upgrade_cost=2` going from value 2 to 4:

    -   Dot 3: `3 × 2 = 6`
    -   Dot 4: `4 × 2 = 8`
    -   **Total: 14 points**

### Downgrade Formula

Refunds use the same calculation in reverse.

!!! example "Downgrade Example"
    Decreasing from value 4 to 2 refunds 14 points.

## Company Settings

The **Free Trait Updates** setting controls when players modify traits without spending points:

| Setting | Behavior |
| --- | --- |
| `UNRESTRICTED` | Players modify traits freely without spending points (default) |
| `WITHIN 24 HOURS` | Free modifications only within 24 hours of character creation |
| `STORYTELLER ONLY` | Players must spend XP; only storytellers make free changes |

!!! info "Currency Availability"
    This setting only affects the `NO_COST` currency. XP and starting points remain available to character owners and storytellers.

## API Endpoints

Two endpoints handle trait value modifications:

### GET `/value-options`

Retrieve all possible target values with costs and affordability calculations.

The response includes:

-   Current trait value and min/max bounds
-   Current XP and starting points available
-   For each possible target value:
    -   Direction (increase or decrease)
    -   Point cost or refund amount
    -   Affordability with XP
    -   Affordability with starting points
    -   Balance after transaction

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

!!! tip "Preview Changes"
    Use this endpoint to display upgrade and downgrade options before users commit to changes.

### PUT `/value`

Modify a trait to a target value using the specified currency.

**Request body:**

```json
{
    "target_value": 4,
    "currency": "XP"
}
```

**Available currencies:**

| Currency | Availability |
| --- | --- |
| `NO_COST` | Storytellers and admins only |
| `XP` | Character owners and storytellers |
| `STARTING_POINTS` | Character owners and storytellers |

The system automatically determines direction (increase or decrease) from the current value.
