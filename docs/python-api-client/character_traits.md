---
icon: lucide/sliders-horizontal
---

# Character Traits Service

Manage character traits including retrieval, assignment, and value modification.

## Usage

```python
from vclient import character_traits_service

traits = character_traits_service(
    user_id="USER_ID",
    campaign_id="CAMPAIGN_ID",
    character_id="CHARACTER_ID",
    company_id="COMPANY_ID"
)
```

## Methods

### CRUD Operations

| Method                          | Returns          | Description                               |
| ------------------------------- | ---------------- | ----------------------------------------- |
| `get(character_trait_id)`       | `CharacterTrait` | Get a character trait by ID               |
| `assign(trait_id, value)`       | `CharacterTrait` | Assign an existing trait to the character |
| `create(TraitCreate, **kwargs)` | `CharacterTrait` | Create a custom trait                     |
| `delete(character_trait_id)`    | `None`           | Delete a character trait                  |

### Pagination

| Method                                           | Returns                             | Description              |
| ------------------------------------------------ | ----------------------------------- | ------------------------ |
| `get_page(limit?, offset?, parent_category_id?)` | `PaginatedResponse[CharacterTrait]` | Get a page of traits     |
| `list_all(parent_category_id?)`                  | `list[CharacterTrait]`              | Get all character traits |
| `iter_all(limit?, parent_category_id?)`          | `AsyncIterator[CharacterTrait]`     | Iterate through traits   |

### Value Modification

| Method                                                  | Returns                              | Description                 |
| ------------------------------------------------------- | ------------------------------------ | --------------------------- |
| `get_value_options(character_trait_id)`                 | `CharacterTraitValueOptionsResponse` | Get available value options |
| `change_value(character_trait_id, new_value, currency)` | `CharacterTrait`                     | Change trait value          |

!!! warning "Check Options First"

    Always call `get_value_options()` before changing a trait value to ensure the change is valid and to understand the cost implications.

## Example

```python
from vclient.models import TraitCreate

# Assign an existing trait from the blueprint
trait = await traits.assign(trait_id="strength_trait_id", value=3)

# Create a custom trait (preferred method: use model object)
request = TraitCreate(
    name="Street Smarts",
    parent_category_id="skills_category_id",
    max_value=5,
    value=2
)
custom = await traits.create(request)

# Alternative: pass fields as keyword arguments
custom = await traits.create(
    name="Street Smarts",
    parent_category_id="skills_category_id",
    max_value=5,
    value=2
)

# Check available value change options
options = await traits.get_value_options(trait.id)
print(f"Available values: {options.available_values}")
print(f"Current value: {options.current_value}")

# Change the trait value
updated = await traits.change_value(trait.id, new_value=4, currency="XP")
```

See [Response Models](models.md) for `CharacterTrait`, `Trait`, and related types.
