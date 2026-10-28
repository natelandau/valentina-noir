---
icon: lucide/heart-pulse
---

# Trackers and Health

Trackers record the in-play state of a character: spent Willpower, spent blood, Humanity, and V5 vampire stains. Health is the damage the character has taken. This page explains the tracker types, how to change trackers and health, and how to build a tracker interface from the rules that the API provides.

Valentina simplifies the published game rules for trackers and health. Damage has one type, and Willpower and Humanity are spend-and-gain counters. See [House Rules](./house_rules.md) for the full list of differences.

## Tracker Types

A trait can have a tracker. The tracker type depends on the trait and on the [game version](./characters.md#game-versions) of the character. The `tracker_type_v4` and `tracker_type_v5` fields on a trait in the [character blueprint](./character_blueprint.md) show the type for each version, or `null` when the trait has no tracker. Custom traits never have a tracker.

Every character trait response contains a `tracker` field. The field is `null` when the trait has no tracker. Otherwise, the `type` field tells you which shape the object has.

| `type`    | Used for                                                                                     | Game versions |
| --------- | -------------------------------------------------------------------------------------------- | ------------- |
| `COUNTER` | Pools that are spent and regained, such as Willpower, Humanity, Blood Pool, Gnosis, and Rage | V4, V5        |
| `STAINS`  | Humanity stains of a V5 vampire                                                              | V5            |

Humanity is the one trait whose tracker also depends on the character class. A V5 vampire tracks stains. Every other character with Humanity, including a V4 vampire, has a `COUNTER`. The blueprint shows `tracker_type_v5: "STAINS"` for Humanity because a blueprint trait has no class. Read the `type` of the character trait's `tracker` to know which tracker a character has.

The size of every tracker follows the value of its trait. A `COUNTER` on a trait with value 6 has size 6. If the trait value decreases, the API lowers the spent amount so that it fits.

=== "COUNTER"

    `current` is the trait value minus the amount spent.

    ```json
    {
        "type": "COUNTER",
        "size": 6,
        "current": 4
    }
    ```

=== "STAINS (V5 vampires)"

    `humanity` is the trait value. `stain_capacity` is the number of free boxes on the Humanity track, which is 10 minus `humanity`. `stains` can be more than `stain_capacity`. The API records stains and has no other rule for them.

    ```json
    {
        "type": "STAINS",
        "humanity": 7,
        "stain_capacity": 3,
        "stains": 4
    }
    ```

## Change a Tracker

There are two ways to change a tracker. Use actions during play. Set the full state to correct or import a tracker.

!!! note "Permissions"

    Only the player of the character or a storyteller can change a tracker or health. Send the `On-Behalf-Of` header with every change request.

### Apply an action

An action is one in-play event, such as spending a point or adding a stain. The API applies the rules and returns the new tracker state, so your client does not need to calculate the result.

```shell
POST /api/v1/companies/{company_id}/characters/{character_id}/traits/{character_trait_id}/tracker/actions
```

**Request body:**

```json
{
    "action": "spend",
    "amount": 2
}
```

| Field    | Description                                    |
| -------- | ---------------------------------------------- |
| `action` | The action to apply. See the table below.      |
| `amount` | How much to change. Minimum 1. Default 1.      |

| Tracker type | Accepted actions                     |
| ------------ | ------------------------------------ |
| `COUNTER`    | `spend`, `gain`, `reset`             |
| `STAINS`     | `add_stain`, `remove_stain`, `reset` |

The actions do these things:

- `spend` removes points from `current`. The request returns `400` if `amount` is more than `current`.
- `gain` adds points to `current`. The value does not go above `size`.
- `add_stain` and `remove_stain` change `stains`. The value stays between 0 and 10.
- `reset` clears the tracker. Spent points return and all stains are removed.

The request returns `400` if the tracker does not accept the action. Use the `TrackerRules` option to find the accepted actions (see [Build a tracker interface](#build-a-tracker-interface)).

### Set the full state

To replace a tracker state in one request, use `PUT` on the tracker.

```shell
PUT /api/v1/companies/{company_id}/characters/{character_id}/traits/{character_trait_id}/tracker
```

Send only the field that matches the tracker `type`.

| Tracker type | Field                | Limits                  |
| ------------ | -------------------- | ----------------------- |
| `COUNTER`    | `current` (required) | 0 up to the trait value |
| `STAINS`     | `stains`             | 0 up to 10              |

```json
{
    "current": 3
}
```

The request returns `400` if a field does not apply to the tracker type, a required field is missing, or a value is negative or too large. `GET` on the same path returns the current tracker. All tracker endpoints return `404` if the trait has no tracker for the character.

## Health

Every character has a health track. It is in the character response as the `health` field, and it has its own endpoints.

| Endpoint                                                                       | Description                                    |
| ------------------------------------------------------------------------------ | ---------------------------------------------- |
| `GET /api/v1/companies/{company_id}/characters/{character_id}/health`          | Retrieve the health track.                     |
| `PUT /api/v1/companies/{company_id}/characters/{character_id}/health`          | Set the full health state.                     |
| `POST /api/v1/companies/{company_id}/characters/{character_id}/health/actions` | Apply one `damage`, `heal`, or `reset` action. |

All health endpoints return `404` if the character has no health track.

Health records one number, `damage`, which is the count of marked boxes. Damage has no type. `damage` adds boxes and `heal` removes them. Damage past a full track and healing past zero are dropped. Health actions use the same request body as tracker actions.

```json
{
    "action": "damage",
    "amount": 2
}
```

The `health` object has `type` set to `DAMAGE`. The shape differs by game version.

=== "V4"

    A V4 track has seven named levels (Bruised, Hurt, Injured, Wounded, Mauled, Crippled, Incapacitated). Extra levels add more Bruised levels at the top of the track. The track size is 7 plus `extra_levels`. Damage marks the levels from the top down.

    ```json
    {
        "type": "DAMAGE",
        "size": 7,
        "damage": 3,
        "extra_levels": 0,
        "levels": [
            {"name": "Bruised", "marked": true},
            {"name": "Hurt", "marked": true},
            {"name": "Injured", "marked": true},
            {"name": "Wounded", "marked": false},
            {"name": "Mauled", "marked": false},
            {"name": "Crippled", "marked": false},
            {"name": "Incapacitated", "marked": false}
        ]
    }
    ```

=== "V5"

    The track size is Stamina plus 3 plus `extra_levels`. The V4-only field `levels` is `null`.

    ```json
    {
        "type": "DAMAGE",
        "size": 6,
        "damage": 2,
        "extra_levels": 0,
        "levels": null
    }
    ```

The V5 track size changes when the Stamina of the character changes. If the track gets smaller, the API lowers `damage` so that it fits.

!!! tip "Fetch health again after a Stamina change"

    The response of `PUT .../traits/{character_trait_id}/value` contains only the changed trait. When you change Stamina on a V5 character, send `GET .../health` again to get the new track size and damage.

### What health does not track

The API records only the damage on the track. It does not calculate dice penalties, impairment, or the state of the character, such as incapacitated, in torpor, or dead. The players and the Storyteller decide these in play. Use the `status` field of the character to record a death.

### Set the health state

To set the health state, send `damage` and, if necessary, `extra_levels`. Omitted fields reset to 0.

```json
{
    "extra_levels": 1,
    "damage": 2
}
```

The request returns `400` if the body has any other field, a value is negative, or `damage` is more than the track size.

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
    "health": {"damage": 2},
    "traits": [
        {
            "trait_id": "3f2b8c1e-6d4a-4f9b-a1c7-2e5d9b8a7c41",
            "value": 3
        },
        {
            "trait_id": "8a1d4e7f-2c3b-4e6a-9f5d-7b0c1e2d3f84",
            "value": 7,
            "tracker": {"current": 6}
        }
    ]
}
```

The `health` field takes the same body as `PUT .../health`. The `tracker` field takes the same body as `PUT .../tracker`. Without these fields, the character starts with no damage and with full trackers.

Creation is atomic. If any part of the request returns `400`, the API creates nothing. A request returns `400` if:

- A `tracker` is sent for a trait that has no tracker for the character.
- A tracker or health value does not fit its limits.
- The same `trait_id` occurs more than once in `traits`.

## V5 Willpower

In V5, the Willpower trait always equals Composure plus Resolve. The API calculates it again when either attribute changes, and the size of the Willpower tracker follows it. The response of `PUT .../value` on Composure or Resolve contains only that attribute, so fetch the Willpower trait again to get its new value and tracker.

- You cannot buy, change, or delete V5 Willpower. `PUT .../value` and `DELETE` return `400`, and `value-options` returns an empty `options` object.
- Every V5 character has Willpower from the moment that it is created. A request to assign it again returns `409`.

V4 Willpower is a normal purchased trait. In both versions, the Willpower tracker is a `COUNTER`.

## Build a Tracker Interface

The `TrackerRules` option lists the actions that each tracker accepts. Read it instead of hard-coding actions in your client, so that a rule change does not need a client update.

```shell
GET /api/v1/companies/{company_id}/options
```

The rules are under `characters.TrackerRules`, keyed by game version and then by tracker type. The `DAMAGE` key holds the health actions.

```json
{
    "V5": {
        "COUNTER": {"actions": ["spend", "gain", "reset"]},
        "STAINS": {"actions": ["add_stain", "remove_stain", "reset"]},
        "DAMAGE": {"actions": ["damage", "heal", "reset"]}
    }
}
```

A suggested flow:

1. Fetch the character. Each character trait has a `tracker` and the character has `health`.
2. For each tracker, use `type` to choose how to draw it.
3. Look up `TrackerRules[game_version][type]` and show a control for each listed action.
4. Send actions as the player taps. Draw the tracker again from the response body. You do not need to fetch it again.

See [Enumerated Values](../technical/enumerated_values.md#tracker-rules) for the full option structure.
