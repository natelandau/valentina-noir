---
icon: lucide/image
---

# Image Assets

Many objects in Valentina Noir can hold uploaded images: character portraits, campaign maps, book covers, and reference art. This page explains which formats are accepted, how to upload an image, and how the response gives you a ready-to-use CDN URL.

Uploads are limited to images. If you need to store an audio clip, PDF, or other file type, host it elsewhere and reference it from a note.

> **Note:** User avatars use a separate endpoint with its own resizing rules. See [User Management](user_management.md#avatars).

## Supported formats

You can upload these image formats:

| Format | Extension | MIME type    |
| ------ | --------- | ------------ |
| PNG    | `.png`    | `image/png`  |
| JPEG   | `.jpg`    | `image/jpeg` |
| GIF    | `.gif`    | `image/gif`  |
| WEBP   | `.webp`   | `image/webp` |

The API detects the format from the file's actual contents, not from the filename or the `Content-Type` you send. The `mime_type` on the response reflects the detected format, so a file named `art.txt` that is really a PNG is stored as `image/png`. Any upload that is not one of these four formats, including SVG, is rejected with a `400`.

## Objects that hold assets

Five object types accept image assets. Each has the same four endpoints under an `/assets` path:

| Object    | Assets path                                                                              |
| --------- | ---------------------------------------------------------------------------------------- |
| Character | `/companies/{company_id}/characters/{character_id}/assets`                                |
| Campaign  | `/companies/{company_id}/campaigns/{campaign_id}/assets`                                  |
| Book      | `/companies/{company_id}/campaigns/{campaign_id}/books/{book_id}/assets`                  |
| Chapter   | `/companies/{company_id}/campaigns/{campaign_id}/books/{book_id}/chapters/{chapter_id}/assets` |
| User      | `/companies/{company_id}/users/{user_id}/assets`                                          |

Every asset endpoint requires the `X-API-KEY` header and the [`On-Behalf-Of`](authentication.md#the-on-behalf-of-header) header that identifies the acting user. Uploading and deleting also require that user to have permission to manage the parent object (for example, a campaign manager for campaign assets, or the character's player or a storyteller for character assets).

## Upload an image

Send a `multipart/form-data` request with a single file part to the object's `/assets/upload` path. The examples below use a character, but the request shape is identical for every object type.

```bash
curl -X POST "$API/companies/$COMPANY_ID/characters/$CHARACTER_ID/assets/upload" \
  -H "X-API-KEY: $API_KEY" \
  -H "On-Behalf-Of: $USER_ID" \
  -F "file=@portrait.png"
```

A successful upload returns `201 Created` with the new asset:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "date_created": "2026-06-09T14:30:00Z",
  "date_modified": "2026-06-09T14:30:00Z",
  "asset_type": "image",
  "mime_type": "image/png",
  "original_filename": "portrait.png",
  "public_url": "https://cdn.valentina-noir.com/.../image/20260609T143000a1b2c3.png",
  "company_id": "11111111-1111-1111-1111-111111111111",
  "uploaded_by_id": "22222222-2222-2222-2222-222222222222",
  "character_id": "33333333-3333-3333-3333-333333333333",
  "campaign_id": null,
  "book_id": null,
  "chapter_id": null,
  "user_parent_id": null
}
```

Uploads share a dedicated rate limit across all five object types (a burst of 50, refilling to 300 per hour), so spreading uploads across endpoints does not raise the ceiling. See [Rate Limiting](rate_limits.md).

### The public URL

The `public_url` field is a CDN (CloudFront) link you can use directly in an `<img>` tag or fetch without authentication. The URL is stable for the life of the asset and is served with a long cache lifetime, so you can safely cache it on your side. Deleting the asset removes the file from the CDN.

### Response fields

| Field               | Type          | Description                                                       |
| ------------------- | ------------- | ----------------------------------------------------------------- |
| `id`                | `UUID`        | The asset's unique identifier                                     |
| `date_created`      | `datetime`    | When the asset was uploaded                                       |
| `date_modified`     | `datetime`    | When the asset record last changed                                |
| `asset_type`        | `string`      | Always `image` for new uploads                                    |
| `mime_type`         | `string`      | The MIME type detected from the file's contents                   |
| `original_filename` | `string`      | The sanitized name of the uploaded file                           |
| `public_url`        | `string`      | The CDN URL for retrieving the image                              |
| `company_id`        | `UUID`        | The company the asset belongs to                                  |
| `uploaded_by_id`    | `UUID\|null`  | The user who uploaded the asset                                   |
| `character_id`      | `UUID\|null`  | The parent character, if attached to a character                  |
| `campaign_id`       | `UUID\|null`  | The parent campaign, if attached to a campaign                    |
| `book_id`           | `UUID\|null`  | The parent book, if attached to a book                            |
| `chapter_id`        | `UUID\|null`  | The parent chapter, if attached to a chapter                      |
| `user_parent_id`    | `UUID\|null`  | The parent user, if attached to a user                            |

Exactly one of the five parent fields (`character_id`, `campaign_id`, `book_id`, `chapter_id`, `user_parent_id`) is set; the rest are `null`.

## List assets

Retrieve a paginated list of an object's assets with a `GET` request to its `/assets` path:

```bash
curl "$API/companies/$COMPANY_ID/characters/$CHARACTER_ID/assets" \
  -H "X-API-KEY: $API_KEY" \
  -H "On-Behalf-Of: $USER_ID"
```

The response uses the standard paginated envelope (`items`, `limit`, `offset`, `total`). Control the page with the `limit` and `offset` query parameters. See [Pagination](pagination.md) for details.

```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "asset_type": "image",
      "mime_type": "image/png",
      "original_filename": "portrait.png",
      "public_url": "https://cdn.valentina-noir.com/.../image/20260609T143000a1b2c3.png",
      "character_id": "33333333-3333-3333-3333-333333333333"
    }
  ],
  "limit": 10,
  "offset": 0,
  "total": 1
}
```

When loading a character, you can embed its assets in the same request with `?include=assets` instead of making a separate call. See [Characters](../concepts/characters.md#embedding-related-resources).

## Retrieve a single asset

Fetch one asset by its ID from the object's `/assets/{asset_id}` path:

```bash
curl "$API/companies/$COMPANY_ID/characters/$CHARACTER_ID/assets/$ASSET_ID" \
  -H "X-API-KEY: $API_KEY" \
  -H "On-Behalf-Of: $USER_ID"
```

## Delete an asset

Remove an asset with a `DELETE` request to the same `/assets/{asset_id}` path. This deletes the file from the CDN and cannot be undone.

```bash
curl -X DELETE "$API/companies/$COMPANY_ID/characters/$CHARACTER_ID/assets/$ASSET_ID" \
  -H "X-API-KEY: $API_KEY" \
  -H "On-Behalf-Of: $USER_ID"
```

A successful delete returns `204 No Content`.

## Errors

| Status | Cause                                                                                  |
| ------ | -------------------------------------------------------------------------------------- |
| `400`  | The upload is not a PNG, JPEG, GIF, or WEBP image (including SVG or a corrupt file)     |
| `404`  | The asset, the parent object, or the company does not exist or is not visible to you   |
| `429`  | The upload rate limit was exceeded                                                     |

Error responses follow the [RFC 9457 Problem Details](errors.md) format.
