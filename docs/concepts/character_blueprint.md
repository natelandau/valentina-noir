---
icon: lucide/logs
---

# Character Blueprint

World of Darkness character sheets contain complex interconnected data. Valentina Noir represents this complexity through a collection of models called the character blueprint.

Understanding the blueprint helps you create and edit characters in your client applications. To render a character sheet for gameplay, use the [full character sheet](./characters.md#full-character-sheet) endpoint instead.

!!! info "API Documentation"

    View detailed endpoint documentation at [api.valentina-noir.com/docs#tag/characters---blueprints](https://api.valentina-noir.com/docs#tag/characters---blueprints).

## Sheet Sections

All characters share four main sheet sections:

| Name           | Description                                                   |
| -------------- | ------------------------------------------------------------- |
| **Attributes** | Inborn aptitudes and raw potential                            |
| **Abilities**  | Learned skills and inborn affinities that improve performance |
| **Advantages** | Benefits over normal individuals                              |
| **Other**      | Traits that don't fit into other sections                     |

## Section Categories

Section categories group traits within sections. For example, `Attributes` contains these categories:

| Name         | Description                                                 |
| ------------ | ----------------------------------------------------------- |
| **Physical** | Physical ability for fighting, lifting, running, etc.       |
| **Social**   | Social ability for persuasion, negotiation, and interaction |
| **Mental**   | Mental ability for thinking, reasoning, and problem-solving |

!!! info "V5 Ability Categories"

    `Ability` categories only exist in V5. The V4 categories (`Talents`, `Skills`, `Knowledges`) are replaced with `Physical`, `Social`, and `Mental` in V5.

## Traits

Traits are the core attributes that determine a character's abilities and limitations. Each trait has a value measured in `dots`.

Valentina Noir represents traits in two categories: `Core Traits` and `Custom Traits`.

??? example "API Response"

    Each trait is represented by a `Trait` object which has the following fields:

    ```json
    {
        "id": "69679d6b92e8772cd93d8185",
        "date_created": "2026-01-15T18:47:12.709Z",
        "date_modified": "2026-01-15T18:47:12.709Z",
        "name": "Strength",
        "description": "Indicates how much weight the character can carry, shove or lift.",
        "character_classes": ["VAMPIRE", "WEREWOLF", ...], // (1)!
        "game_versions": ["V4", "V5"], // (2)!
        "link": "https://vtm.paradoxwikis.com/Strength", // (3)!
        "show_when_zero": true, // (4)!
        "max_value": 5, // (5)!
        "min_value": 0, // (6)!
        "is_custom": false,
        "initial_cost": 1, // (7)!
        "upgrade_cost": 2, // (8)!
        "sheet_section_name": "Attributes", // (9)!
        "sheet_section_id": "69679d6b92e8772cd93d8185", // (10)!
        "parent_category_name": "Physical", // (11)!
        "parent_category_id": "69679d6b92e8772cd93d8185", // (12)!
        "custom_for_character_id": null, // (13)!
        "trait_subcategory_id": null, // (14)!
        "trait_subcategory_name": null, // (15)!
        "pool": null, // (16)!
        "system": null // (17)!
    }
    ```

    1.  An array of character classes which natively support this trait. Useful for filtering traits when creating a character.
    2.  An array of game versions which support this trait. Useful for filtering traits when creating a character.
    3.  Optional URL linking to online resources for the trait.
    4.  Whether to display the trait on a sheet when the value is 0.
    5.  The maximum dot value of the trait.
    6.  The minimum dot value of the trait.
    7.  The initial experience cost to assign the trait to a character.
    8.  The experience cost to upgrade the trait by 1 dot.
    9.  The name of the sheet section which the trait belongs to.
    10. The ID of the sheet section which the trait belongs to.
    11. The name of the parent category which the trait belongs to.
    12. The ID of the parent category which the trait belongs to.
    13. If the trait is custom, this is the ID of the character which the trait is custom for.
    14. The ID of the trait subcategory, if the trait belongs to one. See [Trait Subcategories](./character_traits.md#trait-subcategories).
    15. The name of the trait subcategory, if the trait belongs to one.
    16. A string describing the dice pool associated with this trait, if applicable (e.g., hunter edges).
    17. A string describing the system description for this trait, if applicable (e.g., hunter edges).

### Core Traits

Core traits are common to all characters and match traits described in World of Darkness books. Approximately 250 core traits exist, filterable by character class and game version.

List all core traits for a `V5` `Vampire` character:

```shell
GET /api/v1/companies/{company_id}/characterblueprint/traits?limit=10&offset=0&game_version=V5&character_class=VAMPIRE&order_by=NAME
```

### Custom Traits

Custom traits are specific to individual characters. They share the same fields as core traits but remain unavailable to other characters. Custom traits provide flexibility for displaying unique abilities on character sheets and for dice rolling, experience tracking, etc.

!!! example "Example: Learning 'Cryptography'"

    A character spends significant time learning to decipher encoded messages. The Storyteller grants them the skill `Cryptography`. Since `Cryptography` is not a core trait, it becomes a custom trait for that character. The character can use `Cryptography` in gameplay and see it on their character sheet.

## Navigating the Blueprint Hierarchy

The blueprint API exposes a hierarchical navigation path that mirrors the structure of a character sheet: **Sheet Section → Category → Subcategory → Trait**. Use these endpoints to walk the hierarchy and build trait selection interfaces.

### Listing Category Traits

List the traits within a category by navigating through the hierarchy:

```shell
GET /api/v1/companies/{company_id}/characterblueprint/{game_version}/sections/{section_id}/categories/{category_id}/traits?limit=10&offset=0
```

Some categories contain both top-level traits and traits grouped under [subcategories](./character_traits.md#trait-subcategories). Use the `exclude_subcategory_traits` parameter to return only top-level traits that don't belong to any subcategory:

```shell
GET .../categories/{category_id}/traits?exclude_subcategory_traits=true
```

This is useful when you want to display top-level traits separately from subcategory-grouped traits in your UI.

### Listing Category Subcategories

List the subcategories within a category. Not all categories have subcategories — categories like Attributes and Abilities contain only top-level traits.

```shell
GET /api/v1/companies/{company_id}/characterblueprint/{game_version}/sections/{section_id}/categories/{category_id}/subcategories?limit=10&offset=0
```

Optionally filter by `character_class` to get class-specific subcategories.

??? example "API Response"

    Each subcategory is represented by a `TraitSubcategory` object:

    ```json
    {
        "id": "69679d6b92e8772cd93d8185",
        "date_created": "2026-01-15T18:47:12.709Z",
        "date_modified": "2026-01-15T18:47:12.709Z",
        "name": "Allies",
        "description": "People who support and assist the character.",
        "game_versions": ["V4", "V5"],
        "character_classes": ["VAMPIRE", "WEREWOLF", ...],
        "show_when_empty": true, // (1)!
        "initial_cost": 1, // (2)!
        "upgrade_cost": 2, // (3)!
        "requires_parent": false, // (4)!
        "pool": null, // (5)!
        "system": null, // (6)!
        "parent_category_id": "69679d6b92e8772cd93d8185",
        "parent_category_name": "Backgrounds"
    }
    ```

    1.  Whether to display the subcategory on a sheet when it has no assigned traits.
    2.  Default initial cost for traits in this subcategory.
    3.  Default upgrade cost multiplier for traits in this subcategory.
    4.  Whether this subcategory must be explicitly added to a character before its child traits can be assigned. Used for hunter edges where the edge itself must be selected before perks become available.
    5.  A dice pool description associated with this subcategory, if applicable.
    6.  A system/mechanical rules description for this subcategory, if applicable.

### Getting a Single Subcategory

Retrieve a specific subcategory by its ID:

```shell
GET /api/v1/companies/{company_id}/characterblueprint/{game_version}/sections/{section_id}/categories/{category_id}/subcategories/{subcategory_id}
```

### Listing Subcategory Traits

List traits within a specific subcategory. This returns only the traits grouped under that subcategory.

```shell
GET /api/v1/companies/{company_id}/characterblueprint/{game_version}/sections/{section_id}/categories/{category_id}/subcategories/{subcategory_id}/traits?limit=10&offset=0
```

Optionally filter by `character_class` to get class-specific traits.

!!! tip "Building a Complete Trait Picker"

    To display a complete trait selection UI for a category that has subcategories:

    1. List top-level traits with `exclude_subcategory_traits=true`
    2. List subcategories for the category
    3. For each subcategory, list its traits

    This gives you a clean separation between standalone traits and subcategory-grouped traits.

## Class Specific

### Vampire Clans

Vampires are assigned a unique clan during character creation. Each clan has native Disciplines.

List all available clans for a game version:

```shell
GET /api/v1/companies/{company_id}/characterblueprint/vampire-clans?limit=10&offset=0&game_version=V5
```

??? example "API Response"

    Each clan object has the following fields:

    ```json
    {
        "id": "69679d6b92e8772cd93d8185",
        "date_created": "2026-01-15T18:47:12.709Z",
        "date_modified": "2026-01-15T18:47:12.709Z",
        "name": "Banu Haqim",
        "description": "The Judges of the Banu Haqim are torn between their hereditary thirst for vampiric Blood and their passion for justice.",
        "game_versions": ["V5"], // (1)!
        "discipline_ids": ["69679d6b92e8772cd93d8185", "69679d6b92e8772cd93d8185", "69679d6b92e8772cd93d8185"], // (2)!
        "bane": {
            // (3)!
            "name": "Blood Addiction",
            "description": "When the Banu Haqim slakes at least one Hunger level from another vampire..."
        },
        "variant_bane": {
            // (4)!
            "name": "Noxious Blood",
            "description": "The Blood of the Banu Haqim is toxic to mortals, but not to other vampires."
        },
        "compulsion": {
            // (5)!
            "name": "Judgment",
            "description": "Urged to punish a wrongdoer, the vampire must slake one Hunger from anyone that acts against their own Convictions."
        },
        "link": "https://vtm.paradoxwikis.com/Banu_Haqim" // (6)!
    }
    ```

    1.  An array of game versions which support this clan
    2.  An array of discipline IDs which are native to this clan. For example, the Banu Haqim has the disciplines `Blood Sorcery`, `Celerity`, and `Obfuscate`.
    3.  The Bane of the clan. The Bane is a trait that the clan is afflicted with. It is used to determine the character's ability to use the clan's Disciplines.
    4.  The Variant Bane of the clan. The Variant Bane is a trait that the clan is afflicted with. It is used to determine the character's ability to use the clan's Disciplines.
    5.  The Compulsion of the clan. The Compulsion is a trait that the clan is afflicted with. It is used to determine the character's ability to use the clan's Disciplines.
    6.  The URL linking to the clan's page on the World of Darkness wiki.

### Werewolves

Each werewolf character has unique characteristics.

#### Auspice

List all available auspices:

```shell
GET /api/v1/companies/{company_id}/characterblueprint/werewolf-auspices?limit=10&offset=0&game_version=V5
```

??? example "Auspice Object"

    Each auspice object has the following fields:

    ```json
    {
      "id": null,
      "date_created": "2026-01-15T18:47:12.709Z",
      "date_modified": "2026-01-15T18:47:12.709Z",
      "name": "Ragabash",
      "description": "string",
      "game_versions": ["V4", "V5"],
      "gift_trait_ids": [ // (1)!
          "69679d6b92e8772cd93d8185",
          "69679d6b92e8772cd93d8185",
          "69679d6b92e8772cd93d8185"
      ],
      "link": "https://wta.paradoxwikis.com/Ragabash"
    }
    ```

    1.  An array of Trait IDs for gifts native to this auspice. For example, Ragabash has the gifts `The Thousand Forms`, `Whelp Body`, and `Coup de Grâce`.

#### Tribe

List all available tribes for a game version:

```shell
GET /api/v1/companies/{company_id}/characterblueprint/werewolf-tribes?limit=10&offset=0&game_version=V5
```

??? example "Tribe Object"

    Each tribe object has the following fields:

    ```json
    {
      "id": "69679d6b92e8772cd93d8185",
      "date_created": "2026-01-15T18:47:12.709Z",
      "date_modified": "2026-01-15T18:47:12.709Z",
      "name": "Black Furies",
      "description": "The Black Furies is a tribe known for circumventing or shattering obstacles...",
      "game_versions": ["V5", "V4"],
      "renown": "GLORY",
      "patron_spirit": "Gorgon",
      "favor": "Black Furies player can add a die to a pool used to oppose or circumvent...",
      "ban": "If a Black Fury let an injustice persist when they could've prevented or addressed it...",
      "gift_trait_ids": [ // (1)!
          "69679d6b92e8772cd93d8185",
          "69679d6b92e8772cd93d8185",
          "69679d6b92e8772cd93d8185"
      ],
      "link": "https://wta.paradoxwikis.com/Black_Furies"
    }
    ```

    1.  An array of Trait IDs for gifts native to this tribe. For example, the Black Furies have the gifts `Whelp Body`, `Kali's Scar`, and `Coup de Grâce`.

#### Gifts and Rites

Werewolf gifts and rites are managed as traits under the "Other" sheet section. Gifts belong to the "Gifts" category and rites belong to the "Rites" category. Browse them using the [trait blueprint endpoints](#listing-traits) with the appropriate `parent_category_id` filter.

Both gifts and rites are binary traits (`min_value=1`, `max_value=1`). Assign them to a character with `value=1` through the standard [trait assignment](./character_traits.md#assigning-constant-traits) endpoint.

Gift traits include a `gift_attributes` field with werewolf-specific metadata:

??? example "Gift Trait Object"

    ```json
    {
      "id": "69679d6b92e8772cd93d8185",
      "name": "Blissful Ignorance",
      "description": "By remaining completely still, the Garou can become invisible to others...",
      "character_classes": ["WEREWOLF"],
      "game_versions": ["V4", "V5"],
      "min_value": 1,
      "max_value": 1,
      "pool": "Wisdom + Glory",
      "opposing_pool": "Resolve + Honor",
      "gift_attributes": {
        "renown": "WISDOM",
        "cost": "1 Willpower",
        "duration": "One scene",
        "minimum_renown": 2,
        "is_native_gift": false,
        "tribe_id": "68c1f7152cae3787a09a74fa",
        "auspice_id": null
      }
    }
    ```

When requesting a werewolf's [full character sheet](./character_traits.md#available-traits) with `include_available_traits=true`, gift traits are automatically filtered to those matching the character's tribe, auspice, or marked as native. See [Werewolf Gift Filtering](./character_traits.md#werewolf-gift-filtering) for details.

Rite traits use the standard `pool` field for their dice pool and have no additional metadata beyond standard trait fields.

### Mages

!!! warning "Limited Support"

    Mage `Spheres` and `Traditions` have limited support. See the [roadmap](../roadmap/index.md) for details.

### Hunters

Hunter edges and perks are managed through the unified trait system using [trait subcategories](./character_traits.md#trait-subcategories). Each edge type (Assets, Aptitudes, Endowments) is represented as a trait subcategory, and individual edges and perks are traits within those subcategories.

Use the [subcategory endpoints](#listing-category-subcategories) to browse hunter edges. Filter by `character_class=HUNTER` to see hunter-specific subcategories and traits.

## Character Concepts

Read more about character concepts in the [Character Concepts](character_concepts.md) documentation.

List all available concepts:

```shell
GET /api/v1/companies/{company_id}/characterblueprint/concepts?limit=10&offset=0
```

??? example "Concept Object"

    Each concept object has the following fields:

    ```json
    {
      "id": "69679d6b92e8772cd93d8185",
      "name": "Ascetic",
      "description": "Disciplined martial artists who harnesses their inner chi to perform incredible feats and attacks.",
      "examples": [ // (1)!
        "Martial Artist", "Dojo Owner", "Competitor",
      ],
      "max_specialties": 1, // (2)!
      "specialties": [ // (3)!
            {
                "name": "Focus",
                "type": "PASSIVE",
                "description": "Gathering their Chi, the monk can resist gases, poisons, psionic attacks, and hold their breath one turn per existing `stamina`+ `willpower`.  Monks are immune to the vampiric discipline of `Dominate`."
            },
            {
                "name": "Iron hand",
                "type": "ACTION",
                "description": "Deliver a single punch, once per scene, with damage augmented by spending `willpower`, `1` point per damage level."
            }
      ],
      "favored_ability_names": ["Brawl", "Athletics"] // (4)!
    }
    ```

    1.  Examples of character archetypes that might fit this concept.
    2.  The number of specialties that are available to the character. Users must select up to this number of specialties if the number of specialties is less than the length of the specialties array.
    3.  The array of specialties associated with the concept.
    4.  The array of favored ability names associated with the concept. These abilities are boosted by the RNG engine when generating a character.
