---
icon: lucide/book
---

# Campaign Books Service

Manage books within a campaign, including their notes and assets.

Campaign books organize your campaign content into chapters. Each book can contain multiple chapters, notes, and assets. Books are numbered sequentially and can be reordered using the `renumber()` method.

## Usage

```python
from vclient import books_service

books = books_service(user_id="USER_ID", campaign_id="CAMPAIGN_ID", company_id="COMPANY_ID")
```

## Methods

### CRUD Operations

| Method                                  | Returns        | Description              |
| --------------------------------------- | -------------- | ------------------------ |
| `get(book_id)`                          | `CampaignBook` | Get a book by ID         |
| `create(BookCreate, **kwargs)`          | `CampaignBook` | Create a new book        |
| `update(book_id, BookUpdate, **kwargs)` | `CampaignBook` | Update a book            |
| `delete(book_id)`                       | `None`         | Delete a book            |
| `renumber(book_id, number)`             | `CampaignBook` | Change a book's position |

### Pagination

| Method                      | Returns                           | Description               |
| --------------------------- | --------------------------------- | ------------------------- |
| `get_page(limit?, offset?)` | `PaginatedResponse[CampaignBook]` | Get a page of books       |
| `list_all()`                | `list[CampaignBook]`              | Get all books             |
| `iter_all(limit?)`          | `AsyncIterator[CampaignBook]`     | Iterate through all books |

### Assets

| Method                                                    | Returns                      | Description      |
| --------------------------------------------------------- | ---------------------------- | ---------------- |
| `list_assets(book_id, limit?, offset?)`                   | `PaginatedResponse[S3Asset]` | List book assets |
| `get_asset(book_id, asset_id)`                            | `S3Asset`                    | Get an asset     |
| `upload_asset(book_id, filename, content, content_type?)` | `S3Asset`                    | Upload an asset  |
| `delete_asset(book_id, asset_id)`                         | `None`                       | Delete an asset  |

### Notes

| Method                                                | Returns                   | Description           |
| ----------------------------------------------------- | ------------------------- | --------------------- |
| `get_notes_page(book_id, limit?, offset?)`            | `PaginatedResponse[Note]` | Get a page of notes   |
| `list_all_notes(book_id)`                             | `list[Note]`              | Get all notes         |
| `iter_all_notes(book_id, limit?)`                     | `AsyncIterator[Note]`     | Iterate through notes |
| `get_note(book_id, note_id)`                          | `Note`                    | Get a note            |
| `create_note(book_id, NoteCreate, **kwargs)`          | `Note`                    | Create a note         |
| `update_note(book_id, note_id, NoteUpdate, **kwargs)` | `Note`                    | Update a note         |
| `delete_note(book_id, note_id)`                       | `None`                    | Delete a note         |

## Examples

### Create and Manage Books

```python
from vclient.models import BookCreate, BookUpdate

# Create a book (preferred: use model object)
request = BookCreate(
    name="Act One",
    description="The beginning of the story"
)
book = await books.create(request)
print(f"Created book #{book.number}: {book.name}")

# Alternative: pass fields as kwargs
book = await books.create(
    name="Act One",
    description="The beginning of the story"
)

# Update a book
update = BookUpdate(name="Act One: Origins")
updated = await books.update(book.id, update)

# Reorder the book
await books.renumber(book.id, number=2)
```

### Manage Book Notes

```python
from vclient.models import NoteCreate

# Create a note
note_request = NoteCreate(title="Chapter Summary", content="...")
note = await books.create_note(book.id, note_request)

# List all notes for a book
notes = await books.list_all_notes(book.id)

# Iterate through notes (memory-efficient)
async for note in books.iter_all_notes(book.id):
    print(f"{note.title}: {note.content[:50]}...")
```

### Manage Book Assets

```python
# Upload a book cover image
with open("cover.jpg", "rb") as f:
    asset = await books.upload_asset(
        book.id,
        filename="book_cover.jpg",
        content=f.read(),
        content_type="image/jpeg"
    )

# List all assets
page = await books.list_assets(book.id, limit=20)
for asset in page.items:
    print(f"{asset.filename}: {asset.url}")
```

See [Response Models](models.md) for `CampaignBook`, `S3Asset`, `Note`, and related types.
