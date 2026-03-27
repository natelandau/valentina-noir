---
icon: lucide/book-open
---

# Dictionary Terms

Dictionary terms provide in-app definitions for World of Darkness game terminology. Players and storytellers can look up traits, disciplines, clans, tribes, and other game concepts without leaving the application.

## How Dictionary Terms Work

Each term has a name and either a definition (markdown text) or a link (URL to an external resource). Terms are searchable by name and by synonym, and the API returns them with pagination.

There are two types of dictionary terms:

- **System terms** are pre-populated from the game's trait database. They cover traits, vampire clans, werewolf tribes, werewolf auspices, and trait subcategories. Each system term includes a `source_type` and `source_id` that link it to the original game record. You can use these fields to fetch the full source object from the [character blueprint](./character_blueprint.md) endpoints. System terms can't be edited or deleted through the API.
- **Company terms** are created by a company's users for their own campaigns. These cover house rules, custom abilities, or any terminology specific to a gaming group. Company terms are fully editable by the owning company.

## Term Fields

Every dictionary term includes these fields:

| Field | Type | Description |
|---|---|---|
| `term` | string | The term name. Stored lowercase; 3-50 characters. |
| `definition` | string or null | Markdown-formatted definition text. |
| `link` | string or null | URL to an external resource. |
| `synonyms` | list of strings | Alternative names for the term. Stored lowercase and deduplicated. |
| `company_id` | string or null | The owning company's ID, if this is a company term. |
| `source_type` | string or null | The type of game record this term links to. One of: `trait`, `clan`, `tribe`, `auspice`, `trait_subcategory`. Null for company terms. |
| `source_id` | string or null | The ID of the linked game record. Use this to fetch the full object from the corresponding [character blueprint](./character_blueprint.md) endpoint. Always paired with `source_type`. |
| `pool` | string or null | The dice pool associated with this term (e.g., `"Dexterity + Athletics"`). |
| `opposing_pool` | string or null | The opposing dice pool for contested rolls (e.g., `"Stamina + Athletics"`). |
| `system` | string or null | Mechanical rules text describing how this ability works in play. |
| `character_classes` | list of strings | Which character classes this term applies to (e.g., `["VAMPIRE"]`, `["WEREWOLF"]`). |
| `game_versions` | list of strings | Which game editions this term applies to (e.g., `["V4"]`, `["V5"]`, or both). |

A term must have at least one of `definition` or `link`. The API rejects terms that have neither.

A system term is identified by having a non-null `source_type`. The `source_type` and `source_id` fields are always set together — if one is present, the other must be too.

### Dice Pool Fields

The `pool`, `opposing_pool`, and `system` fields give players quick access to mechanical information. For a trait like "Celerity", the pool might be `"Dexterity + Athletics"` and the system might describe the roll's effect. These fields are optional and most commonly populated on system terms synced from the trait database.

### Filtering Fields

The `character_classes` and `game_versions` fields indicate which characters and editions a term is relevant to. A vampire clan term has `character_classes: ["VAMPIRE"]`; a trait available in both editions has `game_versions: ["V4", "V5"]`. Client applications can use these fields to filter terms contextually based on a character's class and game version.

Possible values for `character_classes`: `VAMPIRE`, `WEREWOLF`, `MAGE`, `HUNTER`, `GHOUL`, `MORTAL`.

Possible values for `game_versions`: `V4`, `V5`.

## System Terms and Source Linking

System terms are pre-populated from the game's trait database. Each term's `definition` field contains a pre-built markdown summary, but the linked source object often has additional structured data — such as `game_version`, `character_class`, and other attributes — that you can use to build richer UI experiences.

Use `source_type` to determine which character blueprint endpoint to query, and `source_id` as the object ID:

| `source_type` | Blueprint endpoint | What the definition includes |
|---|---|---|
| `clan` | `/characterblueprint/vampire-clans/{source_id}` | Name, description, bane, compulsion |
| `tribe` | `/characterblueprint/werewolf-tribes/{source_id}` | Name, description, renown, patron spirit, favor, ban |
| `auspice` | `/characterblueprint/werewolf-auspices/{source_id}` | Name, description |
| `trait_subcategory` | `/characterblueprint/.../subcategories/{source_id}` | Name, description, pool, system |
| `trait` | `/characterblueprint/traits/{source_id}` | Name, description, pool, opposing pool, system, gift attributes |

For traits with gift attributes (werewolf gifts), the definition also includes formatted gift metadata: renown type, cost, duration, minimum renown, and associated tribe or auspice.

## API Endpoints

### GET `/dictionary`

List dictionary terms for the authenticated company. Returns both system and company-specific terms, sorted alphabetically. Supports pagination (`limit`, `offset`) and optional `term` filtering that matches against both term names and synonyms.

### GET `/dictionary/{dictionary_term_id}`

Retrieve a single dictionary term by ID.

### POST `/dictionary`

Create a company dictionary term. The term is automatically associated with the authenticated company. The `source_type` and `source_id` fields can't be set through this endpoint.

```json
{
    "term": "Blood Bond",
    "definition": "A supernatural tie created by drinking a vampire's blood three times.",
    "synonyms": ["Vinculum"],
    "character_classes": ["VAMPIRE"],
    "game_versions": ["V5"]
}
```

### PATCH `/dictionary/{dictionary_term_id}`

Update a company dictionary term. Only terms owned by the authenticated company with no `source_type` can be updated. Attempting to update a system term or another company's term returns an error.

### DELETE `/dictionary/{dictionary_term_id}`

Archive a company dictionary term. Only terms owned by the authenticated company with no `source_type` can be deleted. The term is soft-deleted (archived), not permanently removed.
