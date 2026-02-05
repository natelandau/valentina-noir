---
icon: lucide/layout-template
---

# Character Blueprint Service

Access read-only character sheet blueprints, including sections, categories, traits, and supernatural content that define character sheet structure.

## Usage

```python
from vclient import character_blueprint_service

blueprint = character_blueprint_service(company_id="COMPANY_ID")
```

## Methods

### Sections

Top-level organization of a character sheet (e.g., "Attributes", "Skills", "Disciplines").

| Method | Returns | Description |
| --- | --- | --- |
| `get_sections_page(*, game_version, limit?, offset?, character_class?)` | `PaginatedResponse[SheetSection]` | Get a page of sections |
| `list_all_sections(*, game_version, character_class?)` | `list[SheetSection]` | Get all sections |
| `iter_all_sections(*, game_version, character_class?)` | `AsyncIterator[SheetSection]` | Iterate through sections |
| `get_section(*, game_version, section_id)` | `SheetSection` | Get a section by ID |

### Categories

Nested within sections (e.g., "Physical", "Social", "Mental" within "Attributes").

| Method | Returns | Description |
| --- | --- | --- |
| `get_categories_page(*, game_version, section_id, limit?, offset?, character_class?)` | `PaginatedResponse[TraitCategory]` | Get a page of categories |
| `list_all_categories(*, game_version, section_id, character_class?)` | `list[TraitCategory]` | Get all categories |
| `iter_all_categories(*, game_version, section_id, character_class?)` | `AsyncIterator[TraitCategory]` | Iterate through categories |
| `get_category(*, game_version, section_id, category_id)` | `TraitCategory` | Get a category by ID |

### Category Traits

Traits within a specific category (requires section and category context).

| Method | Returns | Description |
| --- | --- | --- |
| `get_category_traits_page(*, game_version, section_id, category_id, limit?, offset?, character_class?, character_id?)` | `PaginatedResponse[Trait]` | Get a page of traits in a category |
| `list_all_category_traits(*, game_version, section_id, category_id, character_class?, character_id?)` | `list[Trait]` | Get all traits in a category |
| `iter_all_category_traits(*, game_version, section_id, category_id, character_class?, character_id?)` | `AsyncIterator[Trait]` | Iterate through category traits |

### All Traits

Search across all traits without section/category context. All parameters are optional.

!!! note "Direct Trait Access"
    Use these methods to search all traits directly without navigating the section/category hierarchy. Useful when you know what trait you're looking for but not its location in the character sheet.

| Method | Returns | Description |
| --- | --- | --- |
| `get_traits_page(*, limit?, offset?, game_version?, character_class?, parent_category_id?, order_by?)` | `PaginatedResponse[Trait]` | Get a page of all traits |
| `list_all_traits(*, game_version?, character_class?, parent_category_id?, order_by?)` | `list[Trait]` | Get all traits |
| `iter_all_traits(*, game_version?, character_class?, parent_category_id?, order_by?)` | `AsyncIterator[Trait]` | Iterate through all traits |
| `get_trait(*, trait_id)` | `Trait` | Get a trait by ID |

### Character Concepts

| Method                               | Returns                               | Description              |
| ------------------------------------ | ------------------------------------- | ------------------------ |
| `get_concepts_page(*, limit?, offset?)` | `PaginatedResponse[CharacterConcept]` | Get a page of concepts   |
| `list_all_concepts()`                | `list[CharacterConcept]`              | Get all concepts         |
| `iter_all_concepts()`                | `AsyncIterator[CharacterConcept]`     | Iterate through concepts |
| `get_concept(*, concept_id)`            | `CharacterConcept`                    | Get a concept by ID      |

### Vampire Clans

| Method                                    | Returns                          | Description           |
| ----------------------------------------- | -------------------------------- | --------------------- |
| `get_vampire_clans_page(*, limit?, offset?)` | `PaginatedResponse[VampireClan]` | Get a page of clans   |
| `list_all_vampire_clans()`                | `list[VampireClan]`              | Get all clans         |
| `iter_all_vampire_clans()`                | `AsyncIterator[VampireClan]`     | Iterate through clans |
| `get_vampire_clan(*, vampire_clan_id)`       | `VampireClan`                    | Get a clan by ID      |

### Werewolf Tribes

| Method                                      | Returns                            | Description            |
| ------------------------------------------- | ---------------------------------- | ---------------------- |
| `get_werewolf_tribes_page(*, limit?, offset?)` | `PaginatedResponse[WerewolfTribe]` | Get a page of tribes   |
| `list_all_werewolf_tribes()`                | `list[WerewolfTribe]`              | Get all tribes         |
| `iter_all_werewolf_tribes()`                | `AsyncIterator[WerewolfTribe]`     | Iterate through tribes |
| `get_werewolf_tribe(*, werewolf_tribe_id)`     | `WerewolfTribe`                    | Get a tribe by ID      |

### Werewolf Auspices

| Method                                        | Returns                              | Description              |
| --------------------------------------------- | ------------------------------------ | ------------------------ |
| `get_werewolf_auspices_page(*, limit?, offset?)` | `PaginatedResponse[WerewolfAuspice]` | Get a page of auspices   |
| `list_all_werewolf_auspices()`                | `list[WerewolfAuspice]`              | Get all auspices         |
| `iter_all_werewolf_auspices()`                | `AsyncIterator[WerewolfAuspice]`     | Iterate through auspices |
| `get_werewolf_auspice(*, werewolf_auspice_id)`   | `WerewolfAuspice`                    | Get an auspice by ID     |

### Werewolf Gifts

| Method                                     | Returns                           | Description           |
| ------------------------------------------ | --------------------------------- | --------------------- |
| `get_werewolf_gifts_page(*, limit?, offset?)` | `PaginatedResponse[WerewolfGift]` | Get a page of gifts   |
| `list_all_werewolf_gifts()`                | `list[WerewolfGift]`              | Get all gifts         |
| `iter_all_werewolf_gifts()`                | `AsyncIterator[WerewolfGift]`     | Iterate through gifts |
| `get_werewolf_gift(*, werewolf_gift_id)`      | `WerewolfGift`                    | Get a gift by ID      |

### Werewolf Rites

| Method                                     | Returns                           | Description           |
| ------------------------------------------ | --------------------------------- | --------------------- |
| `get_werewolf_rites_page(*, limit?, offset?)` | `PaginatedResponse[WerewolfRite]` | Get a page of rites   |
| `list_all_werewolf_rites()`                | `list[WerewolfRite]`              | Get all rites         |
| `iter_all_werewolf_rites()`                | `AsyncIterator[WerewolfRite]`     | Iterate through rites |
| `get_werewolf_rite(*, werewolf_rite_id)`      | `WerewolfRite`                    | Get a rite by ID      |

### Hunter Edges

| Method                                   | Returns                         | Description           |
| ---------------------------------------- | ------------------------------- | --------------------- |
| `get_hunter_edges_page(*, limit?, offset?)` | `PaginatedResponse[HunterEdge]` | Get a page of edges   |
| `list_all_hunter_edges()`                | `list[HunterEdge]`              | Get all edges         |
| `iter_all_hunter_edges()`                | `AsyncIterator[HunterEdge]`     | Iterate through edges |
| `get_hunter_edge(*, hunter_edge_id)`        | `HunterEdge`                    | Get an edge by ID     |

### Hunter Edge Perks

| Method | Returns | Description |
| --- | --- | --- |
| `get_hunter_edge_perks_page(*, hunter_edge_id, limit?, offset?)` | `PaginatedResponse[HunterEdgePerk]` | Get a page of perks |
| `list_all_hunter_edge_perks(*, hunter_edge_id)` | `list[HunterEdgePerk]` | Get all perks for an edge |
| `iter_all_hunter_edge_perks(*, hunter_edge_id)` | `AsyncIterator[HunterEdgePerk]` | Iterate through perks |
| `get_hunter_edge_perk(*, hunter_edge_id, hunter_edge_perk_id)` | `HunterEdgePerk` | Get a perk by ID |

## Example

```python
# List all sections for V5
sections = await blueprint.list_all_sections(game_version="V5")

for section in sections:
    print(f"Section: {section.name}")

    # Get categories within this section
    categories = await blueprint.list_all_categories(
        game_version="V5",
        section_id=section.id
    )

    for category in categories:
        print(f"  Category: {category.name}")

        # Get traits within this category
        traits = await blueprint.list_all_category_traits(
            game_version="V5",
            section_id=section.id,
            category_id=category.id
        )

        for trait in traits:
            print(f"    Trait: {trait.name}")

# Search all traits directly
all_traits = await blueprint.list_all_traits(game_version="V5")
```

See [Response Models](models.md) for `SheetSection`, `TraitCategory`, `Trait`, and related types.
