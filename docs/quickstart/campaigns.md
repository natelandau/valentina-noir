---
icon: lucide/book-open
---

# Campaigns

Campaigns organize a game world. Every character, book, note, and dice roll is scoped to a campaign, and a company can hold many of them. This page lists the campaigns in your company and creates one for your player to act in.

From here on, every request is a game-resource request, so it carries both `X-API-KEY` and `On-Behalf-Of`. The examples reuse the `player_headers` below.

```python
player_headers = {
    "X-API-KEY": API_KEY,
    "On-Behalf-Of": user_id,  # the approved PLAYER from the previous step
}
```

## List campaigns

Fetch the campaigns in your company so your app can show a picker. The response is [paginated](../technical/pagination.md): the campaigns are in `items`, with `total`, `limit`, and `offset` alongside.

```python
response = requests.get(
    f"{BASE_URL}/companies/{company_id}/campaigns",
    headers=player_headers,
)
response.raise_for_status()
campaigns = response.json()["items"]
```

```json
{
    "items": [
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "The Sabbat Ascendant",
            "description": "A chronicle of the war for the city.",
            "desperation": 0,
            "danger": 0,
            "num_books": 2,
            "num_player_characters": 4
        }
    ],
    "total": 1,
    "limit": 10,
    "offset": 0
}
```

A fresh company has no campaigns yet, so `items` is empty. Create one next.

## Create a campaign

A campaign needs only a `name`. The `description`, `desperation`, and `danger` fields are optional and default to empty or `0`.

```python
response = requests.post(
    f"{BASE_URL}/companies/{company_id}/campaigns",
    headers=player_headers,
    json={
        "name": "The Sabbat Ascendant",
        "description": "A chronicle of the war for the city.",
    },
)
response.raise_for_status()
campaign_id = response.json()["id"]
```

The response is the new campaign, including counts of its child resources (all `0` to start):

```json
{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "The Sabbat Ascendant",
    "description": "A chronicle of the war for the city.",
    "desperation": 0,
    "danger": 0,
    "company_id": "697996c7659f4e107e3bc81a",
    "num_books": 0,
    "num_player_characters": 0
}
```

!!! info "Who can create campaigns"

    By default any approved member can create a campaign. A company can tighten this to storytellers only through the `permission_manage_campaign` [company setting](../concepts/company_settings.md). If your player gets a `403`, check that setting.

## Update and delete

Editing and deleting a campaign follow the same pattern as every other resource: `PATCH` the detail URL with the fields to change, or `DELETE` it.

```python
# Update
requests.patch(
    f"{BASE_URL}/companies/{company_id}/campaigns/{campaign_id}",
    headers=player_headers,
    json={"danger": 2},
)

# Delete
requests.delete(
    f"{BASE_URL}/companies/{company_id}/campaigns/{campaign_id}",
    headers=player_headers,
)
```

Deleting a campaign archives it and its contents rather than erasing them. See the [full API documentation](https://api.valentina-noir.com/docs) for every field and response code.

## Associate characters with chapters

A chapter can record which characters appeared in that session. Pass an optional `character_ids` array when you create or update a chapter:

```python
# Create a chapter with associated characters
requests.post(
    f"{BASE_URL}/companies/{company_id}/campaigns/{campaign_id}/books/{book_id}/chapters",
    headers=player_headers,
    json={
        "name": "The Long Night",
        "character_ids": [
            "550e8400-e29b-41d4-a716-446655440000",
            "660e8400-e29b-41d4-a716-446655440111",
        ],
    },
)
```

Every ID in `character_ids` must reference an active character that belongs to the same campaign as the chapter. If any ID is missing, archived, or from another campaign, the request fails with a `400`.

On `PATCH`, `character_ids` replaces the chapter's entire list:

- Omit the field to leave the existing associations unchanged.
- Send `[]` to clear all associations.
- Send a new array to replace the list with exactly those characters.

```python
# Replace a chapter's associated characters
requests.patch(
    f"{BASE_URL}/companies/{company_id}/campaigns/{campaign_id}/books/{book_id}/chapters/{chapter_id}",
    headers=player_headers,
    json={"character_ids": ["550e8400-e29b-41d4-a716-446655440000"]},
)
```

Chapter responses (both the list and the detail endpoints) include a `character_ids` array listing the associated characters.

Book responses also include a `character_ids` array, but it is **read-only**. It reports the distinct union of the characters across all of the book's chapters and cannot be set on a book directly. Manage character associations through the chapters instead. Archived characters are excluded from every `character_ids` field.

The association is also visible from the other direction: character responses include a **read-only** `chapter_ids` array listing the non-archived chapters the character is associated with. Like the book rollup, it cannot be set on a character directly. Manage it through the chapters.

## What you have now

You have a campaign and its `campaign_id`. Next, [create a character](characters.md) inside it.
