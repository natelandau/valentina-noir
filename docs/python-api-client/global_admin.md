---
icon: lucide/shield
---

# Global Admin Service

Manage developer accounts and API keys across the entire system. All operations require global admin privileges.

!!! warning "Global Admin Only"
    This service requires global admin privileges. Regular developers cannot access these endpoints.

## Initialize the Service

```python
from vclient import global_admin_service

admins = global_admin_service()
```

## Available Methods

### CRUD Operations

| Method                                          | Returns     | Description                     |
| ----------------------------------------------- | ----------- | ------------------------------- |
| `get(developer_id)`                             | `Developer` | Retrieve a developer by ID      |
| `create(request=None, /, **kwargs)`             | `Developer` | Create a new developer account  |
| `update(developer_id, request=None, /, **kwargs)` | `Developer` | Update developer properties     |
| `delete(developer_id)`                          | `None`      | Delete a developer account      |

### Pagination Methods

| Method                                                   | Returns                        | Description                          |
| -------------------------------------------------------- | ------------------------------ | ------------------------------------ |
| `get_page(limit=10, offset=0, is_global_admin=None)`     | `PaginatedResponse[Developer]` | Retrieve a paginated page            |
| `list_all(is_global_admin=None)`                         | `list[Developer]`              | Retrieve all developers              |
| `iter_all(limit=100, is_global_admin=None)`              | `AsyncIterator[Developer]`     | Iterate through all developers       |

### API Key Management

| Method                         | Returns               | Description                            |
| ------------------------------ | --------------------- | -------------------------------------- |
| `create_api_key(developer_id)` | `DeveloperWithApiKey` | Generate a new API key for a developer |

## Examples

### Create a Developer Account

Add a new developer to the system.

```python
from vclient.models import DeveloperCreate

# Option 1: Use a model object (preferred)
request = DeveloperCreate(
    username="newdev",
    email="dev@example.com",
    is_global_admin=False
)
dev = await admins.create(request)

# Option 2: Pass fields as keyword arguments
dev = await admins.create(
    username="newdev",
    email="dev@example.com"
)
```

### Update Developer Settings

Modify a developer account's properties.

```python
from vclient.models import DeveloperUpdate

update = DeveloperUpdate(
    email="newemail@example.com",
    is_global_admin=True
)
updated = await admins.update(dev.id, update)
```

### Generate API Key

Create a new API key for an existing developer.

```python
dev_with_key = await admins.create_api_key(dev.id)
print(f"New API Key: {dev_with_key.api_key}")
```

!!! warning "Save API Keys Immediately"
    API keys are only displayed once during creation. Save the key from the response - it cannot be retrieved later.

### List Developers

Retrieve all developer accounts with optional filtering.

```python
# Get all developers
all_devs = await admins.list_all()

# Filter by global admin status
admin_devs = await admins.list_all(is_global_admin=True)

# Paginated access
page = await admins.get_page(limit=25, offset=0)
print(f"Total developers: {page.total}")
```

### Iterate Through Developers

Use memory-efficient iteration for large developer lists.

```python
async for developer in admins.iter_all():
    print(f"{developer.username} - {developer.email}")
```

## Related Documentation

- [Response Models](models.md) - View `Developer` and `DeveloperWithApiKey` model schemas
