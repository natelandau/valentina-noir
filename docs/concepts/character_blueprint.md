---
icon: lucide/logs
---

# Character Blueprint

World of Darkness character sheets contain complex interconnected data. Valentina Noir represents this complexity through a collection of models called the character blueprint.

Understanding the blueprint helps you create, edit, and display characters in your client applications.

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

## Advantage Categories

Certain advantages (`merits`, `flaws`, `backgrounds`) are sub-grouped into advantage categories.

For example, the merit category `Fame` contains:

- Fame
- Influencer
- Enduring Fame

Display this hierarchy on character sheets when a trait includes `advantage_category_name` and `advantage_category_id`.

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
        "advantage_category_id": null, // (14)!
        "advantage_category_name": "string" // (15)!
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
    14. The ID of the advantage category which the trait belongs to.
    15. The name of the advantage category which the trait belongs to.

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
      "name": "Ragabash", //
      "description": "string",
      "game_versions": ["V4", "V5"],
      "gift_ids": [ // (1)!
          "69679d6b92e8772cd93d8185",
          "69679d6b92e8772cd93d8185",
          "69679d6b92e8772cd93d8185"]
      ,
      "link": "https://wta.paradoxwikis.com/Ragabash"
    }
    ```

    1.  An array of gift IDs which are native to this auspice. For example, Ragabash has the gifts `The Thousand Forms`, `Whelp Body`, and `Coup de Grâce`.

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
      "gift_ids": [ // (1)!
          "69679d6b92e8772cd93d8185",
          "69679d6b92e8772cd93d8185",
          "69679d6b92e8772cd93d8185"]
      ,
      "link": "https://wta.paradoxwikis.com/Black_Furies"
    }
    ```

    1.  An array of gift IDs which are native to this tribe. For example, the Black Furies has the gifts `Whelp Body`, `Kali's Scar`, and `Coup de Grâce`.

#### Gifts

List all available gifts for a game version:

```shell
GET /api/v1/companies/{company_id}/characterblueprint/werewolf-gifts?limit=10&offset=0&game_version=V5
```

??? example "Gift Object"

    Each gift object has the following fields:

    ```json
    {
      "id": "69679d6b92e8772cd93d8185",
      "date_created": "2026-01-15T18:47:12.709Z",
      "date_modified": "2026-01-15T18:47:12.709Z",
      "name": "Blissful Ignorance",
      "description": "By remaining completely still, the Garou can become invisible to others...",
      "game_versions": ["V4","V5"],
      "renown": "GLORY", // (1)!
      "cost": "1 Willpower", // (2)!
      "duration": "One scene", // (3)!
      "dice_pool": ["Wisdom"], // (4)!
      "opposing_pool": ["Composure", "Stealth"], // (5)!
      "minimum_renown": 2, // (6)!
      "is_native_gift": false, // (7)!
      "notes": "When used in attempt to ambush it follows the normal ambush rules, allowing the target a chance to spot the attacker, Wits + Awareness against the attacker's Composure + Stealth.", // (8)!
      "tribe_id": "68c1f7152cae3787a09a74fa", // (9)!
      "auspice_id": null // (10)!
    }
    ```

    1.  The renown this gift is associated with.
    2.  The cost to use the gift.
    3.  How long the gift lasts.
    4.  The dice pool to use when using the gift.
    5.  The opposing pool to use when using the gift.
    6.  The minimum renown required to use the gift.
    7.  Whether the gift is native to all werewolves
    8.  Notes about using the gift.
    9.  The tribe ID which the gift is native to.
    10.  The auspice ID which the gift is native to.

#### Rites

List all available rites for a game version:

```shell
GET /api/v1/companies/{company_id}/characterblueprint/werewolf-rites?limit=10&offset=0&game_version=V5
```

??? example "Rite Object"

    Each rite object has the following fields:

    ```json
    {
      "id": "69679d6b92e8772cd93d8185",
      "date_created": "2026-01-15T18:47:12.709Z",
      "date_modified": "2026-01-15T18:47:12.709Z",
      "name": "Rite of Abjuration",
      "description": "This Rite will purify a person, place, or object, driving out any spiritual possessions.",
      "game_versions": ["V4","V5"],
      "pool": "Honor + Occult", // (1)!
    }
    ```

    1.  The dice pool required to use the rite.

### Mages

!!! warning "Limited Support"

    Mage `Spheres` and `Traditions` have limited support. See the [roadmap](../roadmap/index.md) for details.

### Hunters

Hunters access `Edges`, each containing multiple `Perks`.

!!! info "V5 Only"

    The Hunter Edge system only supports V5 mechanics.

#### Edges

List all available edges:

```shell
GET /api/v1/companies/{company_id}/characterblueprint/hunter-edges?limit=10&offset=0
```

??? example "Edge Object"

    Each edge object has the following fields:

    ```json
    {
      "id": "69679d6b92e8772cd93d8185",
      "date_created": "2026-01-15T18:47:12.709Z",
      "date_modified": "2026-01-15T18:47:12.709Z",
      "name": "Library",
      "description": "The Hunter has access to a wealth of information on a wide variety of topics...",
      "game_versions": ["V5"],
      "pool": "`Resolve` + `Academics`", // (1)!
      "system": "The Hunter must spend about a day researching their quarry before making an Edge test...", // (2)!
      "type": "ASSETS", // (3)!
      "perk_ids": [ // (4)!
          "69679d6b92e8772cd93d8185",
          "69679d6b92e8772cd93d8185",
          "69679d6b92e8772cd93d8185"]
    }
    ```

    1.  The dice pool required to use the edge.
    2.  The text description of the edge
    3.  The type of the edge.  One of `ASSETS`, `APTITUDES`, `ENDOWMENTS`.
    4.  The array of perk IDs associated with the edge.

#### Perks

List all available perks for an edge:

```shell
GET /api/v1/companies/{company_id}/characterblueprint/hunter-edges/{edge_id}/perks?limit=10&offset=0
```

??? example "Perk Object"

    Each perk object has the following fields:

    ```json
    {
      "id": "69679d6b92e8772cd93d8185",
      "date_created": "2026-01-15T18:47:12.709Z",
      "date_modified": "2026-01-15T18:47:12.709Z",
      "name": "Team Requisition",
      "description": "Up to the margin of the win, the hunter can provide additional copies of the same weapon.",
      "game_versions": ["V5"],
      "edge_id": "68c1f7152cae3787a09a74fa" // (1)!
    }
    ```

    1.  The ID of the edge which the perk is associated with.

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
