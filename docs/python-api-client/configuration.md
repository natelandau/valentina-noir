---
icon: lucide/settings
---

# Configuration

The `VClient` constructor accepts several options that control timeouts, retries, idempotency, and more. You can also set required values through environment variables.

## Configuration Options

Pass these options when creating a `VClient` instance:

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
    retry_statuses={429, 500, 502, 503, 504},
    default_company_id=None,
    headers=None,
)
```

| Option                  | Type                       | Default                     | Description                                                                                                  |
| ----------------------- | -------------------------- | --------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `base_url`              | `str` or `None`            | `None`                      | Base URL for the API. Falls back to `VALENTINA_CLIENT_BASE_URL` env var.                                     |
| `api_key`               | `str` or `None`            | `None`                      | API key for authentication. Falls back to `VALENTINA_CLIENT_API_KEY` env var.                                |
| `timeout`               | `float`                    | `30.0`                      | Request timeout in seconds.                                                                                  |
| `max_retries`           | `int`                      | `3`                         | Maximum retry attempts for failed requests.                                                                  |
| `retry_delay`           | `float`                    | `1.0`                       | Base delay between retries in seconds.                                                                       |
| `auto_retry_rate_limit` | `bool`                     | `True`                      | Automatically retry rate-limited requests.                                                                   |
| `auto_idempotency_keys` | `bool`                     | `False`                     | Auto-generate idempotency keys for POST/PUT/PATCH.                                                           |
| `retry_statuses`        | `set[int]` or `None`       | `{429, 500, 502, 503, 504}` | HTTP status codes that trigger automatic retries.                                                            |
| `default_company_id`    | `str` or `None`            | `None`                      | Default company ID for service factory methods. Falls back to `VALENTINA_CLIENT_DEFAULT_COMPANY_ID` env var. |
| `headers`               | `dict[str, str]` or `None` | `None`                      | Additional headers to include with all requests.                                                             |

!!! note

    `base_url` and `api_key` are required. If not passed as arguments, they must be set via the corresponding [environment variables](#environment-variables). A `ValueError` is raised if neither source provides a value.

## Environment Variables

The client reads configuration from environment variables when constructor arguments aren't provided. Explicit arguments always take precedence.

| Environment Variable                  | Maps To              | Required |
| ------------------------------------- | -------------------- | -------- |
| `VALENTINA_CLIENT_BASE_URL`           | `base_url`           | Yes      |
| `VALENTINA_CLIENT_API_KEY`            | `api_key`            | Yes      |
| `VALENTINA_CLIENT_DEFAULT_COMPANY_ID` | `default_company_id` | No       |

```python
from vclient import VClient

# All config from environment variables
client = VClient()

# Mix: explicit base_url, api_key from env var
client = VClient(base_url="https://staging.valentina-noir.com")
```

## Idempotency Keys

Enable automatic idempotency key generation for all mutating requests (POST, PUT, PATCH). The client includes a unique UUID v4 header with each request, ensuring safe retries.

```python
from vclient import VClient

client = VClient(
    base_url="https://api.valentina-noir.com",
    api_key="your-api-key",
    auto_idempotency_keys=True,
)
```

!!! tip "Safe Retries"

    When enabled, the client automatically generates and includes an `Idempotency-Key` header for every POST, PUT, and PATCH request. The server detects duplicate requests and returns the same response, making retries safe even for non-idempotent operations.

## Retry Behavior

When `auto_retry_rate_limit` is enabled (the default), the client automatically retries requests that encounter transient failures. Retries use exponential backoff with jitter.

The following table summarizes which conditions trigger retries:

| Condition          | Retried?                | Notes                                                               |
| ------------------ | ----------------------- | ------------------------------------------------------------------- |
| Rate limit (429)   | Always                  | Respects `Retry-After` / `RateLimit` headers                        |
| Server error (5xx) | Idempotent methods only | GET, PUT, DELETE always retry; POST/PATCH only with idempotency key |
| Network error      | Idempotent methods only | `ConnectError`, `TimeoutException` from httpx                       |
| Client error (4xx) | Never                   | 400, 401, 403, 404, 409 are not transient                           |

Non-idempotent methods (POST, PATCH) are only retried on 5xx and network errors when an idempotency key is present — either explicitly provided or auto-generated via `auto_idempotency_keys=True`. This prevents duplicate side effects from retrying unsafe requests.

!!! tip "Safe Retries for All Methods"

    Enable `auto_idempotency_keys=True` to make all mutating requests (POST, PUT, PATCH) safe to retry on transient errors. The client auto-generates a unique `Idempotency-Key` header for each request.

To customize which status codes trigger retries:

```python
# Only retry on 429 and 503
client = VClient(
    base_url="https://api.valentina-noir.com",
    api_key="your-api-key",
    retry_statuses={429, 503},
)
```

## Logging

The client uses [Loguru](https://github.com/Delgan/loguru) for structured logging, disabled by default. Enable it to see HTTP request/response details, retry attempts, and error information.

### Enable Logging

```python
from loguru import logger

# Enable vclient logs (they flow to your existing loguru handlers)
logger.enable("vclient")
```

### Using with Standard Library Logging

The client includes a bridge to Python's stdlib `logging` module. After enabling, logs are also available through the standard `logging` system:

```python
import logging
from loguru import logger

# Enable vclient logs
logger.enable("vclient")

# Configure stdlib handler
logging.getLogger("vclient").addHandler(logging.StreamHandler())
logging.getLogger("vclient").setLevel(logging.DEBUG)
```

### Log Levels

| Level   | Events                                                                                |
| ------- | ------------------------------------------------------------------------------------- |
| DEBUG   | Request start, response received, 404, client lifecycle                               |
| WARNING | Retries (rate limit, server error, network), validation errors (400), conflicts (409) |
| ERROR   | Authentication failures (401), authorization failures (403), retries exhausted        |

## Default Company ID

Most services require a `company_id`. Set a default to avoid passing it to every service method.

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

    If no `company_id` is provided and no default is configured, a `ValueError` is raised.

## Context Manager

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
