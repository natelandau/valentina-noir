---
icon: lucide/user
---

# Characters

Characters are the core entities in Valentina Noir. They represent player characters, NPCs, and storyteller-controlled figures within your campaigns. Each character belongs to a single campaign and company.

## Character Properties

Every character has several key properties that define who they are in the game world.

### Character Classes

Character class determines the supernatural type (or lack thereof) and affects which traits, disciplines, and abilities are available.

| Class      | Description                     |
| ---------- | ------------------------------- |
| `VAMPIRE`  | Vampire playable class          |
| `WEREWOLF` | Werewolf (Garou) playable class |
| `MAGE`     | Mage playable class             |
| `HUNTER`   | Hunter playable class           |
| `GHOUL`    | Ghoul playable class            |
| `MORTAL`   | Mortal (non-supernatural) class |

### Character Types

Character type indicates who controls the character and its role in the story.

| Type          | Description                      |
| ------------- | -------------------------------- |
| `PLAYER`      | Player character                 |
| `NPC`         | Non-player character             |
| `STORYTELLER` | Storyteller-controlled character |
| `DEVELOPER`   | Developer character              |

### Game Versions

Each character targets a specific game version, which determines available traits and mechanics.

| Version | Description                                    |
| ------- | ---------------------------------------------- |
| `V4`    | Classic World of Darkness (WoD 2nd edition)    |
| `V5`    | Chronicles of Darkness / New World of Darkness |

### Status

Characters track their living status, which the system uses to manage gameplay state.

| Status  | Description                                                     |
| ------- | --------------------------------------------------------------- |
| `ALIVE` | Character is alive and active                                   |
| `DEAD`  | Character is deceased (automatically records the date of death) |

### Temporary Characters

Characters can be marked as being temporary by setting the `is_temporary` flag to `True` when creating or updating a character. Temporary characters are not displayed in the character list by default, but can be filtered by setting the `is_temporary` flag to `True` in the character list endpoint.

This can be useful when creating characters in multi-stage creation sessions. Don't forget to set the `is_temporary` flag to `False` when the character is finalized.

### Class-Specific Attributes

Some character classes have additional attributes beyond the standard set.

- **Vampires** - Clan, generation, sire, bane, and compulsion (auto-populated from clan data)
- **Werewolves** - Tribe, auspice, pack name, gifts, rites, and total renown (computed from Honor + Wisdom + Glory)
- **Mages** - Sphere and tradition
- **Hunters** - Creed and edges (managed as traits via [subcategories](./character_traits.md#trait-subcategories))

See the [character blueprint](./character_blueprint.md) documentation for details on class-specific options.

## Character Creation

Create characters using one of three methods. Each method suits different workflows, from quick NPC generation to full manual control.

### Single Autogeneration

Generate a single character with random attributes. This method is restricted to storytellers and works well for quickly populating campaigns with NPCs.

You can optionally specify:

- Character class (or let the system choose randomly)
- Character type (defaults to NPC)
- Experience level - How many dots and traits are granted to the character - `NEW`, `INTERMEDIATE`, `ADVANCED`, or `ELITE`
- Skill focus - How dots of traits are distributed between abilities - `JACK_OF_ALL_TRADES`, `BALANCED`, or `SPECIALIST`
- [Concept](./character_concepts.md)
- Class-specific options (vampire clan, werewolf tribe/auspice, hunter creed, etc.)

### Multiple Autogeneration

Generate multiple characters at once and select the one you want to keep. The system creates several options (the number is configurable in [company settings](./company_settings.md)), presents them for review, and lets you finalize your choice. Depending on company settings, users may need to spend [experience points](./experience.md) to use this feature.

The multiple autogeneration flow works as follows:

1. Start a chargen session. The API returns a session object containing an `id` and a list of generated characters. The session expires after 24 hours.
2. Optionally retrieve active sessions later using the list or detail session endpoints.
3. Finalize the session by selecting your preferred character. The system keeps your selection and removes the others.

!!! info "Experience Cost"

    Some companies charge experience points for multiple autogeneration. Check your [company settings](./company_settings.md) for details.

### Manual Entry

Enter each trait and attribute individually. This method gives you complete control over every aspect of the character.

The process for manually creating a character is as follows:

1. Use the [character blueprint](./character_blueprint.md) endpoints to get all available sections, categories, and traits for the target game version and character class.
2. Optional: Fetch available [concepts](./character_concepts.md) from the character blueprint concepts endpoint. Assign a `concept_id` to grant the character specialties and favored abilities tied to that concept.
3. Gather the starting value for each trait you want to include.
4. Create the character with the list of traits and optional `concept_id`.

```shell
POST /api/v1/companies/{company_id}/campaigns/{campaign_id}/characters
```

**Request body:**

```json
{
    "name_first": "John",
    "name_last": "Doe",
    "character_class": "MORTAL",
    "game_version": "V5",
    "type": "PLAYER",
    "concept_id": "69679d6b92e8772cd93d8187",
    "traits": [
        {
            "trait_id": "69679d6b92e8772cd93d8185",
            "value": 1
        },
        {
            "trait_id": "69679d6b92e8772cd93d8186",
            "value": 2
        }
    ]
}
```

## Full Character Sheet

The full character sheet endpoint returns a character's complete trait data in a single request, organized in the same hierarchy as a physical character sheet. Use this endpoint to render a character sheet for gameplay without assembling the hierarchy client-side.

```shell
GET /api/v1/companies/{company_id}/users/{user_id}/campaigns/{campaign_id}/characters/{character_id}/full-sheet
```

The response contains two top-level fields:

- `character` - The complete character object
- `sections` - The trait hierarchy, structured as **Section > Category > Subcategory > Trait**

Each level in the hierarchy includes display metadata like `show_when_empty`, `initial_cost`, and `upgrade_cost` so your client can render the sheet without additional API calls.

!!! info "Assigned Traits Only"

    The response includes only sections, categories, and subcategories where the character has assigned traits. It doesn't return the full blueprint of all possible traits. For building trait selection or editing interfaces, use the [character blueprint](./character_blueprint.md) endpoints instead.

??? example "Response Structure"

    ```json
    {
        "character": { ... },
        "sections": [
            {
                "name": "Attributes",
                "description": "Inborn aptitudes and raw potential",
                "order": 1,
                "show_when_empty": true,
                "categories": [
                    {
                        "name": "Physical",
                        "description": "Physical ability for fighting, lifting, running, etc.",
                        "order": 1,
                        "show_when_empty": true,
                        "initial_cost": 1,
                        "upgrade_cost": 2,
                        "subcategories": [
                            {
                                "name": "Allies",
                                "description": "People who support and assist the character.",
                                "initial_cost": 1,
                                "upgrade_cost": 2,
                                "show_when_empty": true,
                                "requires_parent": false,
                                "pool": null,
                                "system": null,
                                "hunter_edge_type": null,
                                "character_traits": [
                                    {
                                        "value": 2,
                                        "trait": {
                                            "name": "Contact: Detective",
                                            "description": "A detective who owes you a favor.",
                                            "max_value": 5,
                                            "min_value": 0,
                                            ...
                                        }
                                    }
                                ]
                            }
                        ],
                        "character_traits": [
                            {
                                "value": 3,
                                "trait": {
                                    "name": "Strength",
                                    "description": "Raw physical power.",
                                    "max_value": 5,
                                    "min_value": 0,
                                    ...
                                }
                            }
                        ]
                    }
                ]
            }
        ]
    }
    ```

    Traits appear in two places within each category:

    - `subcategories[].character_traits` - Traits grouped under a subcategory
    - `character_traits` - Traits that belong directly to the category without a subcategory

## Character Sub-Resources

Characters support several sub-resources for managing related data.

### Traits

Traits represent a character's attributes, skills, disciplines, and other abilities. Each trait has a numeric value you can modify through gameplay using experience points, starting points, or at no cost (depending on permissions).

See the [character traits](./character_traits.md) documentation for details on adding, modifying, and removing traits.

### Inventory

Track items a character carries or owns. Each inventory item has a name, description, and type.

| Item Type    | Description         |
| ------------ | ------------------- |
| `BOOK`       | Books and tomes     |
| `CONSUMABLE` | Single-use items    |
| `ENCHANTED`  | Magical items       |
| `EQUIPMENT`  | General gear        |
| `WEAPON`     | Weapons             |
| `OTHER`      | Miscellaneous items |
