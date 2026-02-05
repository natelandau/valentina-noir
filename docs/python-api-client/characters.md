---
icon: lucide/user
---

# Characters Service

Manage characters within a campaign, including their statistics, assets, notes, inventory, and supernatural abilities.

## Usage

```python
from vclient import characters_service

characters = characters_service(
    user_id="USER_ID",
    campaign_id="CAMPAIGN_ID",
    company_id="COMPANY_ID"
)
```

## Methods

### CRUD Operations

| Method                                            | Returns     | Description            |
| ------------------------------------------------- | ----------- | ---------------------- |
| `get(character_id)`                               | `Character` | Get a character by ID  |
| `create(CharacterCreate, **kwargs)`               | `Character` | Create a new character |
| `update(character_id, CharacterUpdate, **kwargs)` | `Character` | Update a character     |
| `delete(character_id)`                            | `None`      | Delete a character     |

### Pagination

| Method | Returns | Description |
| --- | --- | --- |
| `get_page(limit?, offset?, user_player_id?, character_class?, character_type?, status?)` | `PaginatedResponse[Character]` | Get a page of characters |
| `list_all(...)` | `list[Character]` | Get all characters (supports same filters) |
| `iter_all(limit?, ...)` | `AsyncIterator[Character]` | Iterate through all characters |

### Statistics

| Method                                          | Returns          | Description              |
| ----------------------------------------------- | ---------------- | ------------------------ |
| `get_statistics(character_id, num_top_traits?)` | `RollStatistics` | Get dice roll statistics |

!!! info "Roll Analytics"
    Statistics include success rates, critical frequencies, and most-used traits. Use this data to understand how a character performs in gameplay.

### Assets

| Method | Returns | Description |
| --- | --- | --- |
| `list_assets(character_id, limit?, offset?)` | `PaginatedResponse[S3Asset]` | List character assets |
| `get_asset(character_id, asset_id)` | `S3Asset` | Get an asset |
| `upload_asset(character_id, filename, content, content_type?)` | `S3Asset` | Upload an asset |
| `delete_asset(character_id, asset_id)` | `None` | Delete an asset |

### Notes

| Method                                                     | Returns                   | Description           |
| ---------------------------------------------------------- | ------------------------- | --------------------- |
| `get_notes_page(character_id, limit?, offset?)`            | `PaginatedResponse[Note]` | Get a page of notes   |
| `list_all_notes(character_id)`                             | `list[Note]`              | Get all notes         |
| `iter_all_notes(character_id, limit?)`                     | `AsyncIterator[Note]`     | Iterate through notes |
| `get_note(character_id, note_id)`                          | `Note`                    | Get a note            |
| `create_note(character_id, NoteCreate, **kwargs)`          | `Note`                    | Create a note         |
| `update_note(character_id, note_id, NoteUpdate, **kwargs)` | `Note`                    | Update a note         |
| `delete_note(character_id, note_id)`                       | `None`                    | Delete a note         |

### Inventory

| Method | Returns | Description |
| --- | --- | --- |
| `get_inventory_page(character_id, limit?, offset?)` | `PaginatedResponse[InventoryItem]` | Get a page of inventory items |
| `list_all_inventory(character_id)` | `list[InventoryItem]` | Get all inventory items |
| `iter_all_inventory(character_id, limit?)` | `AsyncIterator[InventoryItem]` | Iterate through items |
| `get_inventory_item(character_id, item_id)` | `InventoryItem` | Get an item |
| `create_inventory_item(character_id, InventoryItemCreate, **kwargs)` | `InventoryItem` | Create an item |
| `update_inventory_item(character_id, item_id, InventoryItemUpdate, **kwargs)` | `InventoryItem` | Update an item |
| `delete_inventory_item(character_id, item_id)` | `None` | Delete an item |

### Werewolf Gifts

| Method                                          | Returns                           | Description             |
| ----------------------------------------------- | --------------------------------- | ----------------------- |
| `get_gifts_page(character_id, limit?, offset?)` | `PaginatedResponse[WerewolfGift]` | Get a page of gifts     |
| `list_all_gifts(character_id)`                  | `list[WerewolfGift]`              | Get all gifts           |
| `iter_all_gifts(character_id, limit?)`          | `AsyncIterator[WerewolfGift]`     | Iterate through gifts   |
| `get_gift(character_id, werewolf_gift_id)`      | `WerewolfGift`                    | Get a gift              |
| `add_gift(character_id, werewolf_gift_id)`      | `WerewolfGift`                    | Add a gift to character |
| `remove_gift(character_id, werewolf_gift_id)`   | `WerewolfGift`                    | Remove a gift           |

### Werewolf Rites

| Method                                          | Returns                           | Description             |
| ----------------------------------------------- | --------------------------------- | ----------------------- |
| `get_rites_page(character_id, limit?, offset?)` | `PaginatedResponse[WerewolfRite]` | Get a page of rites     |
| `list_all_rites(character_id)`                  | `list[WerewolfRite]`              | Get all rites           |
| `iter_all_rites(character_id, limit?)`          | `AsyncIterator[WerewolfRite]`     | Iterate through rites   |
| `get_rite(character_id, werewolf_rite_id)`      | `WerewolfRite`                    | Get a rite              |
| `add_rite(character_id, werewolf_rite_id)`      | `WerewolfRite`                    | Add a rite to character |
| `remove_rite(character_id, werewolf_rite_id)`   | `WerewolfRite`                    | Remove a rite           |

### Hunter Edges

| Method                                          | Returns                         | Description              |
| ----------------------------------------------- | ------------------------------- | ------------------------ |
| `get_edges_page(character_id, limit?, offset?)` | `PaginatedResponse[EdgeAndPerks]` | Get a page of edges      |
| `list_all_edges(character_id)`                  | `list[EdgeAndPerks]`              | Get all edges            |
| `iter_all_edges(character_id, limit?)`          | `AsyncIterator[EdgeAndPerks]`     | Iterate through edges    |
| `get_edge(character_id, hunter_edge_id)`        | `EdgeAndPerks`      | Get an edge with perks   |
| `add_edge(character_id, hunter_edge_id)`        | `EdgeAndPerks`                    | Add an edge to character |
| `remove_edge(character_id, hunter_edge_id)`     | `EdgeAndPerks`                          | Remove an edge           |

### Hunter Edge Perks

| Method | Returns | Description |
| --- | --- | --- |
| `get_edge_perks_page(character_id, hunter_edge_id, limit?, offset?)` | `PaginatedResponse[Perk]` | Get a page of perks |
| `list_all_edge_perks(character_id, hunter_edge_id)` | `list[Perk]` | Get all perks |
| `iter_all_edge_perks(character_id, hunter_edge_id, limit?)` | `AsyncIterator[Perk]` | Iterate through perks |
| `get_edge_perk(character_id, hunter_edge_id, hunter_edge_perk_id)` | `Perk` | Get a perk |
| `add_edge_perk(character_id, hunter_edge_id, hunter_edge_perk_id)` | `Perk` | Add a perk |
| `remove_edge_perk(character_id, hunter_edge_id, hunter_edge_perk_id)` | `Perk` | Remove a perk |

## Example

```python
from vclient.models import CharacterCreate, CharacterUpdate, InventoryItemCreate, NoteCreate

# Create a vampire character (preferred method: use model object)
request = CharacterCreate(
    character_class="VAMPIRE",
    game_version="V5",
    name_first="Marcus",
    name_last="Blackwood",
    user_player_id="player_user_id"
)
character = await characters.create(request)

# Alternative: pass fields as keyword arguments
character = await characters.create(
    character_class="VAMPIRE",
    game_version="V5",
    name_first="Marcus",
    name_last="Blackwood",
    user_player_id="player_user_id"
)

# Update character details
update = CharacterUpdate(name_first="Marcus", name_last="Black")
updated = await characters.update(character.id, update)

# Retrieve roll statistics
stats = await characters.get_statistics(character.id)
print(f"Total rolls: {stats.total_rolls}")
print(f"Success rate: {stats.success_rate}%")

# Add an inventory item
item_request = InventoryItemCreate(
    name="Silver Dagger",
    type="weapon",
    description="An ornate blade"
)
item = await characters.create_inventory_item(character.id, item_request)

# Create a character note
note_request = NoteCreate(title="Background", content="Born in Victorian London...")
note = await characters.create_note(character.id, note_request)
```

See [Response Models](models.md) for `Character`, `WerewolfGift`, `WerewolfRite`, `HunterEdge`, and related types.
