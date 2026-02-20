---
icon: lucide/layers
---

# Service Patterns

All services that manage resources share a consistent API for CRUD operations and pagination. This page covers the common methods available across services.

## CRUD Operations

Every resource service provides standard methods for creating, reading, updating, and deleting resources:

| Method            | Description                                   |
| ----------------- | --------------------------------------------- |
| `get(id)`         | Retrieve a single resource by ID              |
| `create(...)`     | Create a new resource                         |
| `update(id, ...)` | Update an existing resource (partial updates) |
| `delete(id)`      | Delete a resource                             |

```python
# Get a single resource
company = await companies.get("507f1f77bcf86cd799439011")

# Create a new resource
company = await companies.create(name="My Company", email="contact@example.com")

# Update (only include fields to change)
updated = await companies.update("507f1f77bcf86cd799439011", name="New Name")

# Delete
await companies.delete("507f1f77bcf86cd799439011")
```

## Pagination

Services that return collections provide three methods for accessing paginated data:

| Method       | Returns                | Description                                     |
| ------------ | ---------------------- | ----------------------------------------------- |
| `get_page()` | `PaginatedResponse[T]` | Retrieve a single page with pagination metadata |
| `list_all()` | `list[T]`              | Fetch all items across all pages into a list    |
| `iter_all()` | `AsyncIterator[T]`     | Memory-efficient streaming through all pages    |

### PaginatedResponse Model

The `PaginatedResponse` object contains both the results and metadata about the current page:

| Field    | Type      | Description                            |
| -------- | --------- | -------------------------------------- |
| `items`  | `list[T]` | The requested page of results          |
| `limit`  | `int`     | The limit that was applied             |
| `offset` | `int`     | The offset that was applied            |
| `total`  | `int`     | Total number of items across all pages |

### Computed Properties

These properties simplify page navigation:

| Property       | Type   | Description                            |
| -------------- | ------ | -------------------------------------- |
| `has_more`     | `bool` | Whether there are more pages available |
| `next_offset`  | `int`  | The offset for the next page           |
| `total_pages`  | `int`  | Total number of pages                  |
| `current_page` | `int`  | Current page number (1-indexed)        |

### Example

```python
# Get a single page with metadata
page = await companies.get_page(limit=10, offset=0)
print(f"Page {page.current_page} of {page.total_pages}")

for company in page.items:
    print(company.name)

# Check if there are more pages
if page.has_more:
    next_page = await companies.get_page(limit=10, offset=page.next_offset)

# Fetch all items at once
all_companies = await companies.list_all()

# Stream through all items (memory-efficient for large datasets)
async for company in companies.iter_all():
    print(company.name)
```
