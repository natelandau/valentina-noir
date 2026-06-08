---
icon: lucide/list-checks
---

# Enumerated Values

## Overview

The options endpoint (`GET /options`) is the single source of truth for every enumerated value the API accepts. Character classes, game versions, user roles, permission levels, dice sizes, inventory types, and more all live here. Read them at runtime instead of hardcoding them, so your forms, validation, and labels stay correct as the API evolves.

One request returns every enumeration, grouped by domain, plus a `_related` map of URLs to the [character blueprint](../concepts/character_blueprint.md) catalog endpoints that hold larger reference data like traits, concepts, and clans.

!!! tip "Discover, don't hardcode"

    Treat every enumerated value as data. Populate dropdowns, validation rules, and display labels from this endpoint so your client keeps working when new classes, roles, or item types are added.

## Making the Request

The endpoint is scoped to a company and needs only your API key. It doesn't require the `On-Behalf-Of` header.

```yaml
GET /api/v1/companies/{company_id}/options HTTP/1.1
---
Host: api.valentina-noir.com
X-API-KEY: your-api-key-here
```

```python
import requests

response = requests.get(
    f"https://api.valentina-noir.com/api/v1/companies/{company_id}/options",
    headers={"X-API-KEY": API_KEY},
)
response.raise_for_status()
options = response.json()
```

## Response Structure

The response groups enumerations by domain. Each value is the exact string (or number) the API expects in requests.

??? example "Full response"

    ```json
    {
        "companies": {
            "CompanyPermission": ["USER", "ADMIN", "OWNER", "REVOKE"],
            "PermissionManageCampaign": ["UNRESTRICTED", "STORYTELLER"],
            "PermissionManageNPC": ["UNRESTRICTED", "STORYTELLER"],
            "PermissionsGrantXP": ["UNRESTRICTED", "PLAYER", "STORYTELLER"],
            "PermissionsFreeTraitChanges": ["UNRESTRICTED", "WITHIN_24_HOURS", "STORYTELLER"],
            "PermissionsRecoupXP": ["UNRESTRICTED", "DENIED", "WITHIN_SESSION"]
        },
        "characters": {
            "AbilityFocus": ["JACK_OF_ALL_TRADES", "BALANCED", "SPECIALIST"],
            "AutoGenExperienceLevel": ["NEW", "INTERMEDIATE", "ADVANCED", "ELITE"],
            "BlueprintTraitOrderBy": ["NAME", "SHEET"],
            "CharacterClass": ["VAMPIRE", "WEREWOLF", "MAGE", "HUNTER", "GHOUL", "MORTAL"],
            "CharacterStatus": ["ALIVE", "DEAD"],
            "CharacterType": ["PLAYER", "NPC", "STORYTELLER"],
            "GameVersion": ["V4", "V5"],
            "HunterCreed": ["ENTREPRENEURIAL", "FAITHFUL", "INQUISITIVE", "MARTIAL", "UNDERGROUND"],
            "HunterEdgeType": ["ASSETS", "APTITUDES", "ENDOWMENTS"],
            "InventoryItemType": ["BOOK", "CONSUMABLE", "ENCHANTED", "EQUIPMENT", "OTHER", "WEAPON"],
            "SpecialtyType": ["ACTION", "OTHER", "PASSIVE", "RITUAL", "SPELL"],
            "TraitModifyCurrency": ["NO_COST", "XP", "STARTING_POINTS"],
            "WerewolfRenown": ["GLORY", "HONOR", "WISDOM"],
            "_related": {
                "concepts": "https://api.valentina-noir.com/api/v1/companies/{company_id}/characterblueprint/concepts",
                "traits": "https://api.valentina-noir.com/api/v1/companies/{company_id}/characterblueprint/traits",
                "trait_sections": "https://api.valentina-noir.com/api/v1/companies/{company_id}/characterblueprint/sections",
                "trait_categories": "https://api.valentina-noir.com/api/v1/companies/{company_id}/characterblueprint/categories",
                "vampire_clans": "https://api.valentina-noir.com/api/v1/companies/{company_id}/characterblueprint/vampire-clans",
                "werewolf_tribes": "https://api.valentina-noir.com/api/v1/companies/{company_id}/characterblueprint/werewolf-tribes",
                "werewolf_auspices": "https://api.valentina-noir.com/api/v1/companies/{company_id}/characterblueprint/werewolf-auspices"
            }
        },
        "character_autogeneration": {
            "CharacterClassPercentileChance": ["VAMPIRE: 1-40", "WEREWOLF: 41-65", "..."]
        },
        "users": {
            "IdentityProvider": ["apple", "google", "discord", "github"],
            "IdentityResolution": ["matched", "linked", "created"],
            "UserRole": ["ADMIN", "STORYTELLER", "PLAYER", "UNAPPROVED", "DEACTIVATED"]
        },
        "gameplay": {
            "DiceSize": [4, 6, 8, 10, 20, 100],
            "RollResultType": ["SUCCESS", "FAILURE", "BOTCH", "CRITICAL", "OTHER"]
        },
        "assets": {
            "AssetType": ["image", "text", "audio", "video", "document", "archive", "other"]
        },
        "audit_logs": {
            "AuditEntityType": ["ASSET", "BOOK", "CAMPAIGN", "CHARACTER", "..."],
            "AuditOperation": ["CREATE", "UPDATE", "DELETE"]
        }
    }
    ```

### Groups

Each top-level key groups the enumerations for one domain of the API.

| Group                      | Holds enumerations for                                                          |
| -------------------------- | ------------------------------------------------------------------------------- |
| `companies`                | Developer permission levels and company permission settings                     |
| `characters`               | Classes, types, statuses, game versions, and character-building options, plus `_related` catalog links |
| `character_autogeneration` | The class-distribution table used by random character generation                |
| `users`                    | User roles, identity providers, and identity resolution outcomes               |
| `gameplay`                 | Dice sizes and dice-roll result types                                           |
| `assets`                   | Uploadable asset types                                                          |
| `audit_logs`               | Audit entity types and operations                                               |

## Related Catalog Endpoints

Some reference data is too large to inline, so the `characters._related` block links to the [character blueprint](../concepts/character_blueprint.md) endpoints that return it. Use these to build trait pickers, clan and tribe selectors, and concept lists. Each URL contains a `{company_id}` placeholder you replace with your company ID.

| Key                 | Returns                                                       |
| ------------------- | ------------------------------------------------------------- |
| `concepts`          | Character [concepts](../concepts/character_concepts.md) and their specialties |
| `traits`            | Every trait, filterable by game version and class             |
| `trait_sections`    | Top-level sheet sections (Attributes, Abilities, and so on)   |
| `trait_categories`  | Trait categories within sections                              |
| `vampire_clans`     | Vampire clans and their disciplines, banes, and compulsions   |
| `werewolf_tribes`   | Werewolf tribes                                               |
| `werewolf_auspices` | Werewolf auspices                                             |

## Caching

Options change rarely. The endpoint sends cache headers, and the response is safe to cache in your client. Refetch periodically, or when you encounter a value your client doesn't recognize, rather than on every request.

## Where These Values Are Used

The [quickstart](../quickstart/characters.md) uses this endpoint as the entry point for character creation: read the class and version enums, then follow `_related` to fetch the clans, concepts, and traits a character can take.
