---
icon: lucide/book-open
---

# Dictionary Terms

Dictionary terms provide in-app definitions for World of Darkness game terminology. Players and storytellers can look up traits, disciplines, clans, tribes, and other game concepts without leaving your application.

## How Dictionary Terms Work

Each term has a name and either a definition (markdown text) or a link (URL to an external resource). Terms are searchable by name and by synonym.

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
| `company_id` | string or null | The owning company's ID, if this is a company term. Null for system terms. |
| `source_type` | string or null | The type of game record this term links to. One of: `trait`, `clan`, `tribe`, `auspice`, `trait_subcategory`. Null for company terms. |
| `source_id` | string or null | The ID of the linked game record. Use this to fetch the full object from the corresponding [character blueprint](./character_blueprint.md) endpoint. Always paired with `source_type`. |

A term must have at least one of `definition` or `link`. The API rejects terms that have neither.

A system term is identified by having a non-null `source_type`. The `source_type` and `source_id` fields are always set together — if one is present, the other must be too.

## System Terms and Source Linking

System terms are pre-populated from the game's trait database. Each term's `definition` field contains a pre-built markdown summary that includes relevant details from the source object (descriptions, bane/compulsion text for clans, renown and patron spirit for tribes, dice pools and gift attributes for traits, etc.).

For richer UI experiences, use `source_type` to determine which character blueprint endpoint to query, and `source_id` as the object ID:

| `source_type` | Blueprint endpoint | What the source object adds |
|---|---|---|
| `clan` | `/characterblueprint/vampire-clans/{source_id}` | Disciplines, structured bane/compulsion objects |
| `tribe` | `/characterblueprint/werewolf-tribes/{source_id}` | Gift trait IDs, structured renown/favor/ban fields |
| `auspice` | `/characterblueprint/werewolf-auspices/{source_id}` | Gift trait IDs |
| `trait_subcategory` | `/characterblueprint/subcategories/{source_id}` | Cost data, `requires_parent`, character class filtering |
| `trait` | `/characterblueprint/traits/{source_id}` | Cost data, min/max values, character classes, game versions, gift attributes |

## API Endpoints

### GET `/dictionaries`

List dictionary terms for the authenticated company. Returns both system and company-specific terms, sorted alphabetically. Supports pagination (`limit`, `offset`) and optional `term` filtering that matches against both term names and synonyms.

### GET `/dictionaries/{dictionary_term_id}`

Retrieve a single dictionary term by ID.

### POST `/dictionaries`

Create a company dictionary term. The term is automatically associated with the authenticated company. The `source_type` and `source_id` fields can't be set through this endpoint.

```json
{
    "term": "Blood Bond",
    "definition": "A supernatural tie created by drinking a vampire's blood three times.",
    "synonyms": ["Vinculum"]
}
```

### PATCH `/dictionaries/{dictionary_term_id}`

Update a company dictionary term. Only terms owned by the authenticated company with no `source_type` can be updated. Attempting to update a system term or another company's term returns an error.

### DELETE `/dictionaries/{dictionary_term_id}`

Archive a company dictionary term. Only terms owned by the authenticated company with no `source_type` can be deleted. The term is soft-deleted (archived), not permanently removed.
