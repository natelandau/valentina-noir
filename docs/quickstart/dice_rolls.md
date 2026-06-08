---
icon: lucide/dices
---

# Roll Dice

Dice rolls are the core mechanic of the game. A roll is a pool of ten-sided dice counted against a difficulty, and the pool size comes from a character's traits. This page reads a character's trait values, turns them into a pool, and rolls. That completes the loop you set out to build.

The examples reuse `player_headers`, `company_id`, `campaign_id`, and `character_id` from the previous steps.

## Read the character's traits

Fetch the character with its traits embedded using `include=traits`. Each trait carries its current `value` and an `id` you can roll with directly.

```python
response = requests.get(
    f"{BASE_URL}/companies/{company_id}/characters/{character_id}",
    headers=player_headers,
    params={"include": "traits"},
)
response.raise_for_status()
traits = response.json()["traits"]

# Index by trait name so we can pick the pool
by_name = {t["trait"]["name"]: t for t in traits}
```

## Build the pool and roll

A trait-based roll combines one or more traits. Sum the values of the traits you want, then send that total as `num_dice`. Pass the same traits in `trait_ids` so the roll records which traits built the pool.

```python
strength = by_name["Strength"]
brawl = by_name["Brawl"]
pool = strength["value"] + brawl["value"]  # 3 + 2 = 5 dice

response = requests.post(
    f"{BASE_URL}/companies/{company_id}/dicerolls",
    headers=player_headers,
    json={
        "num_dice": pool,
        "difficulty": 6,
        "character_id": character_id,
        "campaign_id": campaign_id,
        "trait_ids": [strength["id"], brawl["id"]],
        "comment": "Marcus throws a punch",
    },
)
response.raise_for_status()
roll = response.json()
```

The response includes the roll and its `result`:

```json
{
    "id": "a1b2c3d4-...",
    "difficulty": 6,
    "num_dice": 5,
    "comment": "Marcus throws a punch",
    "character_id": "...",
    "result": {
        "total_result": 3,
        "total_result_type": "SUCCESS",
        "total_result_humanized": "3 Successes",
        "total_dice_roll": [2, 6, 7, 9, 10],
        "player_roll": [2, 6, 7, 9, 10],
        "desperation_roll": []
    }
}
```

Read `total_result_type` (`CRITICAL`, `SUCCESS`, `FAILURE`, or `BOTCH`) and `total_result_humanized` to show the outcome. The `result` also carries emoji and shortcode renderings of the dice if you want to display them. For how successes are tallied, see [Rolling Dice](../concepts/dice.md).

!!! tip "Let the API sum the pool for you"

    Instead of computing the pool yourself, a [quick roll](../concepts/quick_rolls.md) saves a trait combination (for example `Firearms` + `Dexterity`). Send `POST /dicerolls/quickroll` with the saved roll and a character, and the API sums that character's matching trait values into the pool automatically.

## You built the loop

Your client can now sign a player in, list their campaigns and characters, and roll a character's dice. Every other resource in the API follows the same patterns you've used here: list under `/companies/{company_id}/...`, act with `On-Behalf-Of`, and create or update with `POST` and `PATCH`.

## Next steps

With the core loop working, expand your client with the features your game needs:

- [Books and chapters](../concepts/index.md) organize a campaign into storylines and sessions, nested under `/campaigns/{campaign_id}/books`.
- [Experience](../concepts/experience.md) tracks the points players spend to raise traits and buy new abilities.
- [Quick rolls](../concepts/quick_rolls.md) save trait combinations for one-tap rolling.
- [Notes](https://api.valentina-noir.com/docs) attach to characters, campaigns, books, and chapters for backstory and session recaps.
- [Dictionary terms](../concepts/dictionary.md) let a company define its own game terminology.
- [User profiles](../technical/user_management.md) round out the accounts you set up in step 2: let players update their display name, email, avatar, and linked Google, Discord, or GitHub accounts, and give admins the role and approval-queue tools.

For production hardening, read about [idempotency keys](../technical/idempotency.md) for safe retries, [rate limits](../technical/rate_limits.md), [error handling](../technical/errors.md), and [request IDs](../technical/request_ids.md) for support and debugging.
