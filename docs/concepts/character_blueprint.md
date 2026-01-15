---
icon: lucide/logs
---

# Character Blueprint

World of Darkness character sheets and classes hide a lot of complexity when they are printed to paper. Valentina Noir works through this complexity by using a collection of models to represent a character. These models collectively are called the character blueprint.

!!! info "API Documentation"

    The detailed documentation for each character blueprint endpoint is available in the [API documentation](https://api.valentina-noir.com/docs#tag/characters---blueprints).

Below is a description of each part of the character blueprint. Understanding these is critical for understanding how your client should create, edit, and display characters.

## Sheet Sections

Sheet sections are the main sections of a character sheet. There are four sections which are common to all characters.

| Name | Description |
| --- | --- |
| **Attributes** | The inborn, most raw aptitudes and potential a character possesses |
| **Abilities** | Any skills or aptitudes that your character possesses that make them better at certain activities, whether learned skills or inborn affinities. |
| **Advantages** | Benefits a character has over 'normal' folk. |
| **Other** | Any other traits that your character possesses which do not fit into the other sections. |

## Section Categories

Section categories are how traits are grouped within a section. For example, `Attributes` has the following categories:

| Name | Description |
| --- | --- |
| **Physical** | Measure of physical ability. Used to resolve all actions involving fighting, lifting things, running, etc. |
| **Social** | Measure of social ability. Used to resolve all actions involving interacting with others, such as persuasion, negotiation, and social interaction. |
| **Mental** | Measure of mental ability. Used to resolve all actions involving thinking, reasoning, and problem-solving. |

!!! info "Game Version Support"

    While we strive to support both V4 and V5 of the World of Darkness mechanics, please note that `Ability` categories are only supported in V5. This means `Talents`, `Skills`, and `Knowledges` are replaced with `Physical`, `Social`, and `Mental` as seen on the V5 character sheet.

## Advantage Categories

To make matters more complex, certain advantages (`merits`, `flaws`, and `backgrounds`) are sub-grouped into advantage categories.

For example, there is a merit category named `Fame` which has the following merits:

-   Fame
-   Influencer
-   Enduring Fame

If a trait has an `advantage_category_name` and an `advantage_category_id`, you can display this hierarchy on the character sheet.

## Traits

Character traits are the core attributes of a character. They are used to determine the character's abilities and limitations and are assigned a value in `dots`. In Valentina Noir, traits are represented in two objects: `Core Traits` and `Custom Traits`.

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

Core traits are traits which are common to all characters. Think of them as the traits which are described within the World of Darkness books. There are `~250` core traits available which can be filtered by character class and game version.

An example request to list all core traits for a `V5` `Vampire` character is:

```shell
GET /api/v1/companies/{company_id}/characterblueprint/traits?limit=10&offset=0&game_version=V5&character_class=VAMPIRE&order_by=NAME
```

### Custom Traits

Custom traits are traits which are specific to a character. They have all the same fields as a core trait but are not available to be used by other characters. Adding custom traits to a characrer provides significant flexibility in the traits that are displayed on their character sheets and that are available for dice rolling, experience, etc.

!!! example

    Suppose a character has spent significant time in the game learning how to decipher encoded messages.  The Storyteller may grant that character a skill of `Cryptography`.  Since `Cryptography` is not a core trait, it will be added as a custom trait to the character.  The character can then use `Cryptography` in the game and it will be displayed on their character sheet.

## Class Specific

### Vampire Clans

Vampires are assigned a unique clan as part of their character creation process. Each clan has a unique set of Disciplines which are native to their clan. You can list all the available clans for a game version by making the following request:

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

Werewolves have a number of unique characteristics which are unique to each werewolf character.

#### Auspice

You can list all the available auspices for a by making the following request:

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

You can list all the available tribes for a game version by making the following request:

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

You can list all the available gifts for a game version by making the following request:

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

You can list all the available rites for a game version by making the following request:

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

!!! failure "Not Supported"

    Full support for Mage `Spheres` and `Traditions` are not supported in Valentina Noir. [See the roadmap](../roadmap/index.md) for more information.

### Hunters

Hunters have access to `Edges` which are each comprised of multiple `Perks`.

!!! info "Game Version Support"

    While we strive to support both V4 and V5 of the World of Darkness mechanics, **we only support V5 of the Hunter Edge system.**

#### Edges

To list all available edges run the following request:

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

To list all available perks for an edge run the following request:

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

You can read more about character concepts in the [Character Concepts](character-concepts.md) documentation.

To list all available concepts run the following request:

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
