---
icon: lucide/user-plus
---

# Create a Character

A character is more than a name. It has a class, a game version, a set of traits with numeric values, and, for supernatural classes, an identity like a vampire clan or a werewolf tribe and auspice. Every one of those choices comes from the **character blueprint**: the catalog of classes, concepts, class options, and traits the API recognizes. This page walks the discovery-then-create flow and ends with a character you'll display and roll for in the next steps.

!!! warning "Discover, don't hardcode"

    Classes, traits, clans, and concepts are data, not constants. They differ by game version and can change over time. Read them from the blueprint endpoints at runtime instead of baking IDs or names into your client.

The examples reuse `player_headers`, `company_id`, and `campaign_id` from the previous steps, and build a V5 Vampire named Marcus Vane.

## Start at the options endpoint

The [options endpoint](../technical/enumerated_values.md) is your map of the blueprint. One call returns every enumeration a character can use (classes, game versions, types, hunter creeds, and more) plus a `_related` block of URLs that point to the catalog endpoints.

```python
response = requests.get(
    f"{BASE_URL}/companies/{company_id}/options",
    headers=player_headers,
)
response.raise_for_status()
options = response.json()
```

The `characters` block holds the choices you need to create one:

```json
{
    "characters": {
        "CharacterClass": ["VAMPIRE", "WEREWOLF", "MAGE", "HUNTER", "GHOUL", "MORTAL"],
        "GameVersion": ["V4", "V5"],
        "CharacterType": ["PLAYER", "NPC", "STORYTELLER"],
        "HunterCreed": ["..."],
        "_related": {
            "concepts": "https://api.valentina-noir.com/api/v1/companies/{company_id}/characterblueprint/concepts",
            "traits": "https://api.valentina-noir.com/api/v1/companies/{company_id}/characterblueprint/traits",
            "vampire_clans": ".../characterblueprint/vampire-clans",
            "werewolf_tribes": ".../characterblueprint/werewolf-tribes",
            "werewolf_auspices": ".../characterblueprint/werewolf-auspices"
        }
    }
}
```

## Enumerate the building blocks

Use the enums to populate class, version, and type pickers, then follow the catalog endpoints for the rest. Every catalog endpoint is [paginated](../technical/pagination.md) and accepts a `game_version` filter, so request a high `limit` to pull the full list.

| You need                       | Where it comes from                                   |
| ------------------------------ | ----------------------------------------------------- |
| Classes, versions, types       | Enums in the options response                         |
| Concepts                       | `GET /characterblueprint/concepts`                    |
| Traits                         | `GET /characterblueprint/traits`                      |
| Vampire clans                  | `GET /characterblueprint/vampire-clans`               |
| Werewolf tribes and auspices   | `GET /characterblueprint/werewolf-tribes`, `.../werewolf-auspices` |
| Hunter creeds                  | The `HunterCreed` enum in the options response        |

## Choose a class identity

Supernatural classes carry extra attributes that you set at creation through a class-specific block. A `MORTAL` or `GHOUL` needs none.

| Class      | Block to send         | Required fields            |
| ---------- | --------------------- | -------------------------- |
| `VAMPIRE`  | `vampire_attributes`  | `clan_id`                  |
| `WEREWOLF` | `werewolf_attributes` | `tribe_id`, `auspice_id`   |
| `MAGE`     | `mage_attributes`     | None (`sphere`, `tradition` optional) |
| `HUNTER`   | `hunter_attributes`   | None (`creed` optional)    |
| `MORTAL`, `GHOUL` | None           | None                       |

Marcus is a Vampire, so fetch the clans and pick one. A clan also tells you its disciplines, bane, and compulsion if you want to show them.

```python
response = requests.get(
    options["characters"]["_related"]["vampire_clans"].format(company_id=company_id),
    headers=player_headers,
    params={"game_version": "V5", "limit": 100},
)
response.raise_for_status()
clans_by_name = {c["name"]: c["id"] for c in response.json()["items"]}
clan_id = clans_by_name["Ventrue"]
```

## Add a concept (optional)

A [concept](../concepts/character_concepts.md) is a character archetype, such as "Hardboiled Detective." Assigning one grants the character that concept's specialties and favored abilities. Fetch the available concepts and keep the ID you want.

```python
response = requests.get(
    f"{BASE_URL}/companies/{company_id}/characterblueprint/concepts",
    headers=player_headers,
    params={"limit": 100},
)
response.raise_for_status()
concepts_by_name = {c["name"]: c["id"] for c in response.json()["items"]}
concept_id = concepts_by_name["Hardboiled Detective"]
```

## Gather the starting traits

Traits are the values that drive gameplay. Fetch the traits for your game version and class, then pick the ones you want with their starting values. Filtering by class keeps the list to traits Marcus can actually take.

```python
response = requests.get(
    f"{BASE_URL}/companies/{company_id}/characterblueprint/traits",
    headers=player_headers,
    params={"game_version": "V5", "character_class": "VAMPIRE", "limit": 1000},
)
response.raise_for_status()
traits_by_name = {t["name"]: t["id"] for t in response.json()["items"]}

starting_traits = [
    {"trait_id": traits_by_name["Strength"], "value": 3},
    {"trait_id": traits_by_name["Brawl"], "value": 2},
]
```

Each trait carries its own `max_value`, `min_value`, `category_name`, and `sheet_section_name`, which you'll use again when you [display the sheet](character_sheet.md). For the full trait model and the section hierarchy, see [Character Blueprint](../concepts/character_blueprint.md).

!!! note "There are a lot of traits"

    The catalog holds hundreds of traits, so request the maximum `limit` of `1000` to pull a class's full list in one call. If a list ever exceeds the limit, page through it with `offset` as described in [Pagination](../technical/pagination.md).

## Create the character

Assemble the pieces into one request. Only `name_first`, `name_last`, `character_class`, `game_version`, and `campaign_id` are required; `type` defaults to `PLAYER`.

```python
response = requests.post(
    f"{BASE_URL}/companies/{company_id}/characters",
    headers=player_headers,
    json={
        "name_first": "Marcus",
        "name_last": "Vane",
        "character_class": "VAMPIRE",
        "game_version": "V5",
        "campaign_id": campaign_id,
        "type": "PLAYER",
        "concept_id": concept_id,
        "vampire_attributes": {"clan_id": clan_id},
        "traits": starting_traits,
    },
)
response.raise_for_status()
character_id = response.json()["id"]
```

The response is the new character's core object, including the resolved `vampire_attributes` (clan name, generation) and any specialties the concept granted. By default it doesn't embed traits or other collections; add `?include=traits` to pull them back in the same call.

!!! info "Other ways to create characters"

    Manual entry gives you full control. Storytellers can also autogenerate a fully statted character in one call, and players can run a guided multi-step builder that returns several options to choose from. See [Character Creation](../concepts/characters.md#character-creation) for all three methods, and the [`is_temporary` flag](../concepts/characters.md#temporary-characters) for staged builders.

## Permissions

The acting user's [role](../technical/user_management.md#user-roles) and the character `type` decide who can create what:

- A `PLAYER` can create `PLAYER` characters for themselves.
- `STORYTELLER` characters can only be created by storytellers and admins.
- Whether a player can create an `NPC` depends on the company's `permission_manage_npc` [setting](../concepts/company_settings.md).

A `403 Forbidden` means the acting user's role doesn't allow the character type they're trying to create.

## What you have now

You have a fully built character and its `character_id`. Next, [display its sheet](character_sheet.md).
