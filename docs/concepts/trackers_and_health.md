---
icon: lucide/heart-pulse
---

# Trackers and Health

Trackers record the in-play state of a character: spent Willpower, damage taken, and Humanity stains. Health is the character's damage track. This page explains the tracker types, how to change them, and how to build a tracker interface from the rules the API provides.

## Tracker Types

A trait can have a tracker. The tracker type depends on the trait and on the character's [game version](./characters.md#game-versions). The `tracker_type_v4` and `tracker_type_v5` fields on a trait in the [character blueprint](./character_blueprint.md) show the type for each version, or `null` when the trait has none. Custom traits never have a tracker.

Every character trait response contains a `tracker` field. The field is `null` when the trait has no tracker. Otherwise the `type` field tells you which shape the object has.

| `type`    | Used for                                                       | Game versions |
| --------- | -------------------------------------------------------------- | ------------- |
| `COUNTER` | Pools that are spent and regained, such as Blood Pool, Gnosis, Rage, Conviction, and Willpower | V4 |
| `DAMAGE`  | A damage track with superficial and aggravated damage, used by Willpower | V5 |
| `STAINS`  | Humanity stains                                                | V5 |

The size of every tracker follows the value of its trait. A `COUNTER` or `DAMAGE` tracker on a trait with value 6 has size 6. If the trait value decreases, the API removes marks that no longer fit, starting with the least severe.

=== "COUNTER (V4)"

    `current` is the trait value minus the amount spent.

    ```json
    {
        "type": "COUNTER",
        "size": 6,
        "current": 4
    }
    ```

=== "DAMAGE (V5)"

    `boxes` lists the track from the most severe damage to empty boxes. An empty box is `null`. `is_impaired` is `true` when every box is marked.

    ```json
    {
        "type": "DAMAGE",
        "size": 6,
        "superficial": 2,
        "aggravated": 1,
        "boxes": ["AGGRAVATED", "SUPERFICIAL", "SUPERFICIAL", null, null, null],
        "is_impaired": false,
        "bashing": null,
        "lethal": null,
        "levels": null,
        "current_penalty": null
    }
    ```

=== "STAINS (V5)"

    `humanity` is the trait value. `stain_capacity` is the number of free boxes on the Humanity track, which is 10 minus `humanity`. The character is impaired when `stains` is more than `stain_capacity`. `willpower_damage_applied` is `null` in `GET` and `PUT` responses. Action responses report a number (see [Stains overflow](#stains-overflow-into-willpower)).

    ```json
    {
        "type": "STAINS",
        "humanity": 7,
        "stain_capacity": 3,
        "stains": 3,
        "is_impaired": false,
        "willpower_damage_applied": null
    }
    ```

## Change a Tracker

There are two ways to change a tracker. Use actions during play and set the full state to correct or import a tracker.

!!! note "Permissions"

    Only the character's player or a storyteller can change a tracker or health. Send the `On-Behalf-Of` header with every change request.

### Apply an action

An action is one in-play event, such as taking damage or spending a point. The API applies the game rules and returns the new tracker state, so your client does not need to calculate the result.

```shell
POST /api/v1/companies/{company_id}/characters/{character_id}/traits/{character_trait_id}/tracker/actions
```

**Request body:**

```json
{
    "action": "damage",
    "amount": 2,
    "damage_type": "SUPERFICIAL"
}
```

| Field         | Description                                                                                      |
| ------------- | ------------------------------------------------------------------------------------------------ |
| `action`      | The action to apply. See the table below.                                                        |
| `amount`      | How much to change. Minimum 1. Default 1.                                                        |
| `damage_type` | Required for `damage` and `heal`. Not accepted for any other action.                             |

| Tracker type | Accepted actions                    |
| ------------ | ----------------------------------- |
| `COUNTER`    | `spend`, `gain`, `reset`            |
| `DAMAGE`     | `damage`, `heal`, `reset`           |
| `STAINS`     | `add_stain`, `remove_stain`, `reset` |

The rules for each action are:

- `spend` removes points from `current`. The request returns `400` if `amount` is more than `current`.
- `gain` adds points to `current`. The value does not go above `size`.
- `damage` marks boxes of the given `damage_type`. If the track is full, the damage upgrades existing marks. In V5, superficial damage becomes aggravated.
- `heal` removes marks of the given `damage_type` only. Healing more than is marked stops at zero.
- `add_stain` and `remove_stain` change `stains`. The value stays between 0 and 10.
- `reset` clears the tracker. Spent points return and all marks and stains are removed.

The request returns `400` if the action or damage type is not accepted for the tracker and game version. Use the `TrackerRules` option to find the accepted values (see [Build a tracker interface](#build-a-tracker-interface)).

### Stains overflow into Willpower

In V5, stains above the free boxes on the Humanity track deal aggravated damage to the character's Willpower. This happens when you apply `add_stain`. The response reports the number of Willpower boxes that became aggravated in `willpower_damage_applied`.

Example: a character has Humanity 7 and 3 stains. The character adds 2 stains. Both stains overflow.

```json
{
    "type": "STAINS",
    "humanity": 7,
    "stain_capacity": 3,
    "stains": 5,
    "is_impaired": true,
    "willpower_damage_applied": 2
}
```

`willpower_damage_applied` can be less than the overflow when Willpower has no more boxes to mark. It is `0` when no damage was dealt, including for `remove_stain` and `reset`. To read the new Willpower state, fetch the Willpower tracker again.

### Set the full state

To replace a tracker state in one request, use `PUT` on the tracker.

```shell
PUT /api/v1/companies/{company_id}/characters/{character_id}/traits/{character_trait_id}/tracker
```

Send only the fields that match the tracker `type`.

| Tracker type | Fields                         | Limits                                                  |
| ------------ | ------------------------------ | ------------------------------------------------------- |
| `COUNTER`    | `current` (required)           | 0 up to the trait value                                 |
| `DAMAGE`     | `superficial`, `aggravated`    | Together at most the trait value. Omitted fields are 0. |
| `STAINS`     | `stains`                       | 0 up to 10                                              |

```json
{
    "superficial": 2,
    "aggravated": 1
}
```

The request returns `400` if a field does not apply to the tracker type, a required field is missing, or a value is negative or too large. `GET` on the same path returns the current tracker. All tracker endpoints return `404` if the trait has no tracker for the character's game version.

## Health

Every character has a health track. It is embedded in the character response as the `health` field, and you can read and change it with its own endpoints.

| Endpoint                                                                       | Description                                    |
| ------------------------------------------------------------------------------ | ---------------------------------------------- |
| `GET /api/v1/companies/{company_id}/characters/{character_id}/health`          | Retrieve the health track.                     |
| `PUT /api/v1/companies/{company_id}/characters/{character_id}/health`          | Set the full health state.                     |
| `POST /api/v1/companies/{company_id}/characters/{character_id}/health/actions` | Apply one `damage`, `heal`, or `reset` action. |

All health endpoints return `404` if the character has no health track. Health actions use the same request body as tracker actions. In `PUT`, send every field you want to keep, because omitted fields reset to 0.

The `health` object has `type` set to `DAMAGE` and the same fields as the V5 damage tracker, plus `extra_levels`. The shape differs by game version.

=== "V4"

    A V4 track has seven named levels (Bruised, Hurt, Injured, Wounded, Mauled, Crippled, Incapacitated). Each level has a dice penalty. Extra levels add more Bruised levels at the top of the track. The track size is 7 plus `extra_levels`.

    Damage types are `BASHING`, `LETHAL`, and `AGGRAVATED`. Marks fill the levels from the most severe damage down. `current_penalty` is the penalty of the lowest marked level. It is `null` when the character is incapacitated.

    ```json
    {
        "type": "DAMAGE",
        "size": 7,
        "superficial": 0,
        "aggravated": 0,
        "boxes": ["LETHAL", "BASHING", "BASHING", null, null, null, null],
        "is_impaired": false,
        "bashing": 2,
        "lethal": 1,
        "levels": [
            {"name": "Bruised", "penalty": 0, "mark": "LETHAL"},
            {"name": "Hurt", "penalty": -1, "mark": "BASHING"},
            {"name": "Injured", "penalty": -1, "mark": "BASHING"},
            {"name": "Wounded", "penalty": -2, "mark": null},
            {"name": "Mauled", "penalty": -2, "mark": null},
            {"name": "Crippled", "penalty": -5, "mark": null},
            {"name": "Incapacitated", "penalty": null, "mark": null}
        ],
        "current_penalty": -1,
        "extra_levels": 0
    }
    ```

    When the track is full, each new bashing or lethal box upgrades the least severe mark one step: a bashing mark becomes lethal, or if there is no bashing mark, a lethal mark becomes aggravated. Each new aggravated box converts the least severe bashing or lethal mark to aggravated. If no bashing or lethal mark is left to upgrade, the damage is dropped. `is_impaired` is `true` when the Incapacitated level is marked.

=== "V5"

    The track size is Stamina plus 3 plus `extra_levels`. Damage types are `SUPERFICIAL` and `AGGRAVATED`. The V4-only fields `bashing`, `lethal`, `levels`, and `current_penalty` are `null`.

    ```json
    {
        "type": "DAMAGE",
        "size": 6,
        "superficial": 2,
        "aggravated": 1,
        "boxes": ["AGGRAVATED", "SUPERFICIAL", "SUPERFICIAL", null, null, null],
        "is_impaired": false,
        "bashing": null,
        "lethal": null,
        "levels": null,
        "current_penalty": null,
        "extra_levels": 0
    }
    ```

    When the track is full, damage converts superficial damage to aggravated. If the track is already all aggravated, the damage is dropped.

The V5 track size updates when the character's Stamina changes. If the track gets smaller, the API removes marks that no longer fit, starting with the least severe.

!!! tip "Re-fetch after a Stamina change"

    The response of `PUT .../traits/{character_trait_id}/value` contains only the changed trait. When you change Stamina on a V5 character, fetch `GET .../health` again to get the new track size and marks.

To set the health state, send the damage fields for the character's game version and optionally `extra_levels`.

```json
{
    "extra_levels": 1,
    "superficial": 2,
    "aggravated": 1
}
```

The request returns `400` if a field does not apply to the game version and is not 0, a value is negative, or the marks together are more than the track size.

## Create a Character with Health and Trackers

When you [create a character](./characters.md#manual-entry), you can set the health state and the tracker of each trait. Use this to import a character that is already hurt.

```json
{
    "name_first": "John",
    "name_last": "Doe",
    "character_class": "MORTAL",
    "game_version": "V5",
    "campaign_id": "550e8400-e29b-41d4-a716-446655440000",
    "type": "PLAYER",
    "health": {"superficial": 2},
    "traits": [
        {
            "trait_id": "3f2b8c1e-6d4a-4f9b-a1c7-2e5d9b8a7c41",
            "value": 3
        },
        {
            "trait_id": "8a1d4e7f-2c3b-4e6a-9f5d-7b0c1e2d3f84",
            "value": 7,
            "tracker": {"stains": 2}
        }
    ]
}
```

The `health` field takes the same body as `PUT .../health`. The `tracker` field takes the same body as `PUT .../tracker`. Without these fields, the character starts with full health and unmarked trackers.

Creation is atomic. If any part of the request returns `400`, the API creates nothing. A request returns `400` if:

- A `tracker` is sent for a trait that has no tracker in the character's game version.
- A tracker or health value does not fit its limits.
- The same `trait_id` appears more than once in `traits`.

## V5 Willpower

In V5, the Willpower trait always equals Composure plus Resolve. The API recalculates it when either attribute changes, and the Willpower tracker size follows it. The response of `PUT .../value` on Composure or Resolve contains only that attribute, so fetch the Willpower trait again to get its new value and tracker.

- You cannot buy, change, or delete V5 Willpower. `PUT .../value` and `DELETE` return `400`, and `value-options` returns an empty `options` object.
- Every V5 character has Willpower from the moment it is created. A request to assign it again returns `409`.

V4 Willpower is a normal purchased trait with a `COUNTER` tracker.

## Build a Tracker Interface

The `TrackerRules` option lists which controls each tracker supports. Read it instead of hard-coding actions in your client, because a rule change then needs no client update.

```shell
GET /api/v1/companies/{company_id}/options
```

The rules are under `characters.TrackerRules`, keyed by game version and then by tracker type or `HEALTH`.

```json
{
    "V5": {
        "STAINS": {
            "actions": ["add_stain", "remove_stain", "reset"],
            "damage_types": []
        },
        "HEALTH": {
            "actions": ["damage", "heal", "reset"],
            "damage_types": ["SUPERFICIAL", "AGGRAVATED"]
        }
    }
}
```

A suggested flow:

1. Fetch the character. Each character trait has a `tracker` and the character has `health`.
2. For each tracker, switch on `type` to choose how to draw it.
3. Look up `TrackerRules[game_version][type]`. Show a control for each listed action. Offer a damage type picker only when `damage_types` is not empty.
4. Send actions as the player taps. Redraw from the response body. A new fetch is not needed.

See [Enumerated Values](../technical/enumerated_values.md#tracker-rules) for the full option structure.
