---
icon: lucide/package
---

# Python API Client

Interact with the Valentina Noir REST API from Python using an async client with type-safe models, automatic pagination, and built-in retries.

!!! note

    This client library is a convenience for Python developers. It isn't required to use the Valentina Noir API — you can integrate with any HTTP client in any language by following the [Technical Details](../technical/index.md) documentation.

## Features

- **Async-first design** — Built on httpx for efficient async HTTP operations
- **Type-safe** — Full type hints with Pydantic models for request and response validation
- **Convenient factory pattern** — Create a client once, access services from anywhere
- **Automatic pagination** — Stream through large datasets with `iter_all()` or fetch everything with `list_all()`
- **Robust error handling** — Specific exception types for different error conditions
- **Idempotency support** — Optional automatic idempotency keys for safe retries
- **Automatic retries** — Built-in retry with exponential backoff for rate limits (429), server errors (5xx), and network failures
- **Structured logging** — Loguru-based logging with stdlib bridge, disabled by default

## Requirements

- Python 3.13+
- [Valentina API key](../technical/authentication.md)

## Repository

The source code for the Python client is [on GitHub](https://github.com/natelandau/valentina-python-client).

## Installation

```bash
# Using uv
uv add valentina-python-client

# Using pip
pip install valentina-python-client
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

If you've set the `VALENTINA_CLIENT_BASE_URL` and `VALENTINA_CLIENT_API_KEY` [environment variables](configuration.md#environment-variables), create a client with no arguments:

```python
client = VClient()
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

The `VClient` constructor accepts options for timeouts, retries, idempotency, and more:

```python
from vclient import VClient

client = VClient(
    base_url="https://api.valentina-noir.com",
    api_key="your-api-key",
    timeout=30.0,              # Request timeout in seconds
    max_retries=3,             # Max retry attempts
    auto_idempotency_keys=True # Safe retries for POST/PUT/PATCH
)
```

See the [Configuration](configuration.md) reference for all options, environment variables, retry behavior, logging, and more.

## Services

The client provides services for managing campaigns, characters, dice rolls, users, and more. Browse the individual service pages in the sidebar for method signatures and examples.

Most services are scoped to a company and require a `company_id`. Pass it as a keyword argument, or configure a [`default_company_id`](configuration.md#default-company-id) to avoid repeating it. A few services — Companies, Developers, Global Admin, and System — operate globally and don't require one.

All services share consistent patterns for CRUD operations and pagination. See [Service Patterns](service-patterns.md) for details on `get()`, `create()`, `update()`, `delete()`, and the three pagination methods (`get_page()`, `list_all()`, `iter_all()`).

## Error Handling

The client raises specific exceptions for different HTTP error conditions — `NotFoundError` for 404s, `RateLimitError` for 429s, `AuthenticationError` for 401s, and more. All exceptions inherit from `APIError`. See [Error Handling](errors.md) for the full exception hierarchy and usage examples.

## Response Models

All API responses return as strongly-typed [Pydantic](https://docs.pydantic.dev/) models with automatic validation, serialization, and IDE autocompletion support. Import models from `vclient.models`:

```python
from vclient.models import Company, User, Campaign, Character
```

See the [Response Models](models.md) reference for detailed model specifications.

## Resources

- [API Concepts](../concepts/index.md)
- [Technical Details](../technical/index.md)
- [Full API Reference](https://api.valentina-noir.com/docs)
