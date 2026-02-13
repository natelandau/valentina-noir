---
icon: lucide/package
---

# Python API Client

The Valentina Python Client is an async Python library that provides a convenient wrapper around the Valentina Noir REST API.

> **Note:** This client library is provided as a convenience for Python developers. It is **not required** to use the Valentina Noir API. You can integrate with any HTTP client in any programming language by following the [Technical Details](../technical/index.md) documentation.

## Features

- **Async-first design** - Built on httpx for efficient async HTTP operations
- **Type-safe** - Full type hints with Pydantic models for request and response validation
- **Convenient factory pattern** - Create a client once, access services from anywhere
- **Automatic pagination** - Stream through large datasets with `iter_all()` or fetch everything with `list_all()`
- **Robust error handling** - Specific exception types for different error conditions
- **Idempotency support** - Optional automatic idempotency keys for safe retries
- **Rate limit handling** - Built-in automatic retry support for rate-limited requests

## Requirements

- Python 3.13+
- [Valentina API key](../technical/authentication.md)

## Repository

The repository for the Python client is [here](https://github.com/natelandau/valentina-python-client).

## Installation

```bash
# Using uv
uv add git+https://github.com/natelandau/valentina-python-client.git
```

## Quick Start

Create a client once at application startup, then use service factory functions from any module.

### 1. Create the Client

```python
from vclient import VClient

# Client automatically registers itself as the default
client = VClient(
    base_url="https://api.valentina-noir.com",
    api_key="your-api-key",
)
```

### 2. Use Services from Any Module

```python
import asyncio
from vclient import companies_service, dicerolls_service, system_service

async def main():
    # Check system health
    system = system_service()
    health = await system.health()
    print(f"API Version: {health.version}")
    print(f"Database: {health.database_status}")

    # List companies you have access to
    companies = companies_service()
    for company in await companies.list_all():
        print(f"Company: {company.name}")

    # Roll some dice
    dicerolls = dicerolls_service(user_id="USER_ID", company_id="COMPANY_ID")
    roll = await dicerolls.create(
        dice_size=10,
        num_dice=5,
        difficulty=6,
        character_id="CHARACTER_ID",
        campaign_id="CAMPAIGN_ID"
    )
    print(f"Roll result: {roll.successes} successes")

asyncio.run(main())
```

## Configuration

### Configuration Options

```python
from vclient import VClient

client = VClient(
    base_url="https://api.valentina-noir.com",
    api_key="your-api-key",
    timeout=30.0,
    max_retries=3,
    retry_delay=1.0,
    auto_retry_rate_limit=True,
    auto_idempotency_keys=False,
    default_company_id=None,
    headers=None,
)
```

| Option                  | Type                       | Default  | Description                                       |
| ----------------------- | -------------------------- | -------- | ------------------------------------------------- |
| `base_url`              | `str`                      | Required | Base URL for the API                              |
| `api_key`               | `str`                      | Required | API key for authentication                        |
| `timeout`               | `float`                    | `30.0`   | Request timeout in seconds                        |
| `max_retries`           | `int`                      | `3`      | Maximum retry attempts for failed requests        |
| `retry_delay`           | `float`                    | `1.0`    | Base delay between retries in seconds             |
| `auto_retry_rate_limit` | `bool`                     | `True`   | Automatically retry rate-limited requests         |
| `auto_idempotency_keys` | `bool`                     | `False`  | Auto-generate idempotency keys for POST/PUT/PATCH |
| `default_company_id`    | `str` or `None`            | `None`   | Default company ID for service factory methods    |
| `headers`               | `dict[str, str]` or `None` | `None`   | Additional headers to include with all requests   |

### Idempotency Keys

Enable automatic idempotency key generation for all mutating requests (POST, PUT, PATCH). This ensures safe retries by including a unique UUID v4 header with each request.

```python
from vclient import VClient

client = VClient(
    base_url="https://api.valentina-noir.com",
    api_key="your-api-key",
    auto_idempotency_keys=True,  # Auto-generate for all POST/PUT/PATCH
)
```

!!! tip "Safe Retries"

When enabled, the client automatically generates and includes an `Idempotency-Key` header for every POST, PUT, and PATCH request. This allows the server to detect duplicate requests and return the same response, making retries safe even for non-idempotent operations.

### Default Company ID

Configure a default company ID to avoid passing it to every service method. The default is used when `company_id` is not explicitly provided.

```python
from vclient import VClient, users_service

# Configure default company ID
client = VClient(
    base_url="https://api.valentina-noir.com",
    api_key="your-api-key",
    default_company_id="507f1f77bcf86cd799439011",
)

# Uses default company_id
users = client.users()
all_users = await users.list_all()

# Override for a specific call
other_users = client.users(company_id="other-company-id")

# Also works with factory functions
svc = users_service()  # Uses default
svc2 = users_service(company_id="explicit-id")  # Override
```

!!! warning

"Required Company ID" If no `company_id` is provided and no default is configured, a `ValueError` is raised.

## Available Services

Services that require a `company_id` accept it as an optional keyword argument. If not provided, the `default_company_id` from the client configuration is used.

| Service                                       | Factory Function                                                               | Description                              |
| --------------------------------------------- | ------------------------------------------------------------------------------ | ---------------------------------------- |
| [Campaigns](campaigns.md)                     | `campaigns_service(user_id, company_id=...)`                                   | Manage campaigns, assets, and notes      |
| [Campaign Books](campaign_books.md)           | `books_service(user_id, campaign_id, company_id=...)`                          | Manage campaign books, notes, and assets |
| [Campaign Chapters](campaign_chapters.md)     | `chapters_service(user_id, campaign_id, book_id, company_id=...)`              | Manage campaign book chapters            |
| [Character Autogen](character_autogen.md)     | `character_autogen_service(user_id, campaign_id, company_id=...)`              | Auto-generate characters                 |
| [Character Blueprint](character_blueprint.md) | `character_blueprint_service(company_id=...)`                                  | Manage character blueprints              |
| [Character Traits](character_traits.md)       | `character_traits_service(user_id, campaign_id, character_id, company_id=...)` | Manage character traits                  |
| [Characters](characters.md)                   | `characters_service(user_id, campaign_id, company_id=...)`                     | Manage characters, assets, and notes     |
| [Companies](companies.md)                     | `companies_service()`                                                          | Manage companies and permissions         |
| [Developers](developers.md)                   | `developer_service()`                                                          | Manage your developer profile            |
| [Dice Rolls](dice_rolls.md)                   | `dicerolls_service(user_id, company_id=...)`                                   | Manage dice rolls                        |
| [Dictionary](dictionary.md)                   | `dictionary_service(company_id=...)`                                           | Manage dictionary terms                  |
| [Global Admin](global_admin.md)               | `global_admin_service()`                                                       | Manage developer accounts (admin only)   |
| [Options](options.md)                         | `options_service(company_id=...)`                                              | Retrieve API options and enumerations    |
| [System](system.md)                           | `system_service()`                                                             | Health checks and system status          |
| [Users](users.md)                             | `users_service(company_id=...)`                                                | Manage users and permissions             |

## Common Service Methods

Services that manage resources share a consistent API pattern for CRUD operations and pagination.

### CRUD Operations

All services follow a consistent pattern for creating, reading, updating, and deleting resources.

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

### Pagination

Services that return collections provide three methods for accessing paginated data.

| Method       | Returns                | Description                                     |
| ------------ | ---------------------- | ----------------------------------------------- |
| `get_page()` | `PaginatedResponse[T]` | Retrieve a single page with pagination metadata |
| `list_all()` | `list[T]`              | Fetch all items across all pages into a list    |
| `iter_all()` | `AsyncIterator[T]`     | Memory-efficient streaming through all pages    |

#### PaginatedResponse Model

| Field    | Type      | Description                            |
| -------- | --------- | -------------------------------------- |
| `items`  | `list[T]` | The requested page of results          |
| `limit`  | `int`     | The limit that was applied             |
| `offset` | `int`     | The offset that was applied            |
| `total`  | `int`     | Total number of items across all pages |

#### Computed Properties

| Property       | Type   | Description                            |
| -------------- | ------ | -------------------------------------- |
| `has_more`     | `bool` | Whether there are more pages available |
| `next_offset`  | `int`  | The offset for the next page           |
| `total_pages`  | `int`  | Total number of pages                  |
| `current_page` | `int`  | Current page number (1-indexed)        |

#### Example Usage

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

## Error Handling

The client provides specific exception types for different error conditions:

```python
from vclient import companies_service
from vclient.exceptions import (
    APIError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    RateLimitError,
    RequestValidationError,
    ServerError,
    ValidationError,
)

companies = companies_service()

try:
    company = await companies.get("invalid-id")
except NotFoundError:
    print("Company not found")
except AuthorizationError:
    print("You don't have access to this company")
except AuthenticationError:
    print("Invalid API key")
except ValidationError as e:
    print(f"Server validation failed: {e}")
except RequestValidationError as e:
    print(f"Client validation failed: {e}")
except ConflictError:
    print("Resource conflict (check idempotency key)")
except RateLimitError as e:
    print(f"Rate limited, retry after {e.retry_after}s")
except ServerError:
    print("Server error, try again later")
except APIError as e:
    print(f"API error: {e}")
```

### Exception Hierarchy

| Exception                | HTTP Status | Description                            |
| ------------------------ | ----------- | -------------------------------------- |
| `APIError`               | -           | Base class for all API errors          |
| `AuthenticationError`    | 401         | Invalid or missing API key             |
| `AuthorizationError`     | 403         | Insufficient permissions               |
| `NotFoundError`          | 404         | Resource not found                     |
| `ValidationError`        | 400         | Server-side validation failed          |
| `RequestValidationError` | -           | Client-side validation failed          |
| `ConflictError`          | 409         | Resource conflict (e.g., duplicate ID) |
| `RateLimitError`         | 429         | Rate limit exceeded                    |
| `ServerError`            | 5xx         | Server-side error                      |

## Response Models

All API responses are returned as [Pydantic](https://docs.pydantic.dev/) models, providing automatic validation, serialization, and IDE autocompletion support.

Import models from `vclient.models` for use in your code.

See the [Response Models](models.md) reference for detailed model specifications.

## Context Manager Usage

For applications that need explicit resource management, use the async context manager pattern:

```python
from vclient import VClient

async with VClient(
    base_url="https://api.valentina-noir.com",
    api_key="your-api-key",
    set_as_default=False,  # Don't register as default
) as client:
    companies = client.companies
    all_companies = await companies.list_all()
    # HTTP client is automatically closed when exiting the context
```

## Resources

- [API Concepts](../concepts/index.md)
- [Technical Details](../technical/index.md)
- [Full API Reference](https://api.valentina-noir.com/docs)
