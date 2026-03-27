---
icon: lucide/sparkles
---

# Character Concepts

Character concepts define a character's archetype and playstyle. Each concept grants specialties (unique abilities) and favored abilities (traits that receive a boost during autogeneration). Concepts add mechanical depth beyond a character's class and traits.

## How Concepts Work

A concept has three parts:

- **Description** — A short summary of the archetype (e.g., "Disciplined martial artists who harness inner chi")
- **Specialties** — Unique abilities the character gains. Some concepts offer more specialties than the character can take, requiring a choice (indicated by `max_specialties`)
- **Favored abilities** — Trait names that the autogeneration engine prioritizes when distributing dots

Specialties have a `type` field indicating how they're used in play:

| Type | Meaning |
| --- | --- |
| `PASSIVE` | Always active — no action required |
| `ACTION` | Requires the character to take an action |

## Assigning Concepts

The autogeneration engine automatically assigns a concept to new characters. When creating characters manually, you can optionally assign a concept by passing a `concept_id` during character creation. See [manual character creation](./characters.md#manual-entry) for details.

## Browsing Available Concepts

Fetch the full list of concepts from the character blueprint API:

```shell
GET /api/v1/companies/{company_id}/characterblueprint/concepts?limit=10&offset=0
```

??? example "Concept Response"

    ```json
    {
        "id": "69679d6b92e8772cd93d8185",
        "name": "Soldier",
        "description": "Skilled warriors possess a wide range of combat abilities and weapon expertise.",
        "examples": ["Mercenary", "Veteran", "Bodyguard"],
        "max_specialties": 1,
        "specialties": [
            {
                "name": "Firearms Specialist",
                "type": "ACTION",
                "description": "Re-roll any single Firearms roll once per turn. Specialize in new firearms at 3, 4, and 5 dots (grants an additional die when using specialized weapons)."
            },
            {
                "name": "Hand-to-hand Specialist",
                "type": "ACTION",
                "description": "Re-roll any single Brawl roll once per turn. Gain new specializations at 3, 4, and 5 dots (grants an additional die when using specialized martial arts styles)."
            },
            {
                "name": "Melee Specialist",
                "type": "ACTION",
                "description": "Re-roll any single Melee roll once per turn. Gain new specializations at 3, 4, and 5 dots (grants an additional die when using specialized melee weapons)."
            }
        ],
        "favored_ability_names": ["Firearms", "Brawl", "Melee"]
    }
    ```

    In this example, the Soldier concept offers three specialties but `max_specialties` is `1`, so the player picks one.

## Displaying Concepts in Your UI

When building a concept selection interface:

1. Fetch available concepts from the blueprint API
2. Display each concept's `description` and `examples` to help the user choose
3. If `max_specialties` is less than the total number of specialties, prompt the user to select
4. Pass the chosen `concept_id` when creating the character
