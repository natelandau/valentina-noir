---
icon: lucide/scroll-text
---

# Display a Character

Showing a character means rendering two things: their **identity** (name, class, status, and class-specific details like a vampire clan) and their **traits**, laid out the way a physical character sheet is. The API can return both in one call, already organized into the sheet hierarchy, so your client doesn't have to assemble it. This page reads the character you just built and renders it.

The examples reuse `player_headers`, `company_id`, and the `character_id` from the previous step.

## Pick the right endpoint

There are two ways to read a character, depending on how much you need to show.

| Endpoint                          | Returns                                                       | Use it for                           |
| --------------------------------- | ------------------------------------------------------------- | ------------------------------------ |
| `GET /characters/{id}`            | Core object only; add `?include=traits` for a flat trait list | Pickers, summaries, quick lookups    |
| `GET /characters/{id}/full-sheet` | Core object plus traits in the full Section hierarchy         | Rendering a complete character sheet |

This page uses the full sheet.

```python
response = requests.get(
    f"{BASE_URL}/companies/{company_id}/characters/{character_id}/full-sheet",
    headers=player_headers,
)
response.raise_for_status()
sheet = response.json()
character = sheet["character"]
sections = sheet["sections"]
```

## Display the identity

The `character` object holds everything that describes who the character is. Class-specific attributes live in their own block and are `null` for every class except the matching one.

```json
{
    "name_full": "Marcus Vane",
    "character_class": "VAMPIRE",
    "type": "PLAYER",
    "game_version": "V5",
    "status": "ALIVE",
    "concept_name": "Hardboiled Detective",
    "specialties": [{ "name": "Investigation", "type": "..." }],
    "vampire_attributes": {
        "clan_name": "Ventrue",
        "generation": 10,
        "bane_name": "...",
        "compulsion_name": "..."
    },
    "werewolf_attributes": null,
    "mage_attributes": null,
    "hunter_attributes": null
}
```

Read the block that matches `character_class`:

| Class      | Block                 | Key fields                                                |
| ---------- | --------------------- | --------------------------------------------------------- |
| `VAMPIRE`  | `vampire_attributes`  | `clan_name`, `generation`, `bane_name`, `compulsion_name` |
| `WEREWOLF` | `werewolf_attributes` | `tribe_name`, `auspice_name`, `pack_name`, `total_renown` |
| `MAGE`     | `mage_attributes`     | `sphere`, `tradition`                                     |
| `HUNTER`   | `hunter_attributes`   | `creed`                                                   |

## Understand the trait hierarchy

Traits are organized into four levels, the same shape as a paper character sheet. Render them top down.

```
Section          Attributes, Abilities, Advantages, Other
  Category        Physical, Social, Mental, Disciplines, ...
    Subcategory   used by some categories, e.g. Backgrounds, Merits, Flaws, Edges
      Trait       Strength = 3, Brawl = 2, ...
```

Each `section` contains `categories`. Subcategories aren't consistent across categories: some categories group their traits into subcategories, others hold their traits directly. An example of this is `Advantages` -> `Backgrounds` -> `Safe House` -> `Hidden Armory`. Your rendering has to handle both, because a single category can place traits at either level:

- `category.character_traits` holds traits that belong directly to the category, with no subcategory.
- `subcategory.character_traits` holds traits grouped under one of the category's subcategories. A category with no subcategories returns an empty `subcategories` list.

Every level carries display metadata so you can lay it out without guessing:

| Field                          | Use when rendering                                                           |
| ------------------------------ | ---------------------------------------------------------------------------- |
| `order`                        | Sort sections and categories for display.                                    |
| `show_when_empty`              | Whether to draw the section, category, or subcategory when it has no traits. |
| `initial_cost`, `upgrade_cost` | Show the experience cost to add or raise a trait.                            |

Each trait entry has the character's `value` (the dots) and a nested `trait` object with `name`, `description`, `max_value`, and `min_value`.

## Render the sheet

Walk the hierarchy in order and print each trait's name and value. A real client would draw dots instead of a number, but the traversal is the same.

```python
for section in sorted(sections, key=lambda s: s["order"]):
    print(f"\n{section['name'].upper()}")

    for category in sorted(section["categories"], key=lambda c: c["order"]):
        print(f"  {category['name']}")

        # Traits attached directly to the category
        for ct in category["character_traits"]:
            print(f"    {ct['trait']['name']}: {ct['value']}")

        # Traits grouped under a subcategory
        for sub in category["subcategories"]:
            for ct in sub["character_traits"]:
                print(f"    {sub['name']} / {ct['trait']['name']}: {ct['value']}")
```

For Marcus, that prints his Strength and Brawl under the right sections:

```text
ATTRIBUTES
  Physical
    Strength: 3

ABILITIES
  Physical
    Brawl: 2
```

By default the sheet includes only the sections, categories, and subcategories where the character has traits. It won't list every possible trait.

## Build an editing interface

When you're building a screen to add or raise traits, you also need the traits the character _doesn't_ have yet. Pass `include_available_traits=true` and each category and subcategory gains an `available_traits` list of unassigned blueprint traits alongside its `character_traits`.

```python
response = requests.get(
    f"{BASE_URL}/companies/{company_id}/characters/{character_id}/full-sheet",
    headers=player_headers,
    params={"include_available_traits": "true"},
)
```

To refresh one part of the sheet without refetching the whole thing, request a single category slice:

```shell
GET /companies/{company_id}/characters/{character_id}/full-sheet/categories/{category_id}
```

To actually change a trait's value, add a trait, or remove one, use the dedicated [character trait endpoints](../concepts/character_traits.md). The sheet endpoint is read-only.

## What you have now

You can render a character's identity and full sheet. Next, [roll its dice](dice_rolls.md).
