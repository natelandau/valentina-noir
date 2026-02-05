---
icon: lucide/dices
---

# Dice Rolls Service

Create and retrieve dice rolls for characters within a company.

The Dice Rolls service manages dice roll records in the Valentina API, allowing you to create rolls manually or from quickroll templates.

## Usage

```python
from vclient import dicerolls_service

dicerolls = dicerolls_service(user_id="USER_ID", company_id="COMPANY_ID")
```

## Methods

### CRUD Operations

| Method                                              | Returns    | Description                    |
| --------------------------------------------------- | ---------- | ------------------------------ |
| `get(diceroll_id)`                                  | `Diceroll` | Get a dice roll by ID          |
| `create(DicerollCreate, **kwargs)`                  | `Diceroll` | Create a new dice roll         |
| `create_quickroll(quickroll_id, character_id, ...)` | `Diceroll` | Create a roll from a quickroll |

### Pagination

Filter rolls by user, character, or campaign using optional query parameters.

| Method                                                          | Returns                         | Description             |
| --------------------------------------------------------------- | ------------------------------- | ----------------------- |
| `get_page(limit?, offset?, userid?, characterid?, campaignid?)` | `PaginatedResponse[Diceroll]`   | Get a page of rolls     |
| `list_all(userid?, characterid?, campaignid?)`                  | `list[Diceroll]`                | Get all rolls           |
| `iter_all(userid?, characterid?, campaignid?, limit?)`          | `AsyncIterator[Diceroll]`       | Iterate through rolls   |

## Examples

### Create a Manual Dice Roll

```python
from vclient.models import DicerollCreate

# Create a dice roll (preferred: use model object)
request = DicerollCreate(
    dice_size=10,
    num_dice=5,
    difficulty=6,
    num_desperation_dice=0,
    comment="Strength + Brawl",
    trait_ids=["strength_id", "brawl_id"],
    character_id="character_id",
    campaign_id="campaign_id"
)
roll = await dicerolls.create(request)
print(f"Rolled {roll.successes} successes")

# Alternative: pass fields as kwargs
roll = await dicerolls.create(
    dice_size=10,
    num_dice=5,
    difficulty=6,
    comment="Strength + Brawl",
    character_id="character_id",
    campaign_id="campaign_id"
)
```

### Use a Quickroll Template

```python
# Create a roll from a saved quickroll template
roll = await dicerolls.create_quickroll(
    quickroll_id="quickroll_id",
    character_id="character_id",
    comment="Combat roll",
    difficulty=6
)
```

### Query Rolls

```python
# Get all rolls for a specific character
character_rolls = await dicerolls.list_all(characterid="character_id")

# Get all rolls in a campaign
campaign_rolls = await dicerolls.list_all(campaignid="campaign_id")

# Iterate through all rolls (memory-efficient)
async for roll in dicerolls.iter_all():
    print(f"{roll.comment}: {roll.successes} successes")
```

See [Response Models](models.md) for `Diceroll`.
