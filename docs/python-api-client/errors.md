---
icon: lucide/alert-triangle
---

# Error Handling

The client provides specific exception types for different error conditions. All exceptions inherit from `APIError`, so you can catch broad or narrow depending on your needs.

## Exception Hierarchy

Every API error maps to a specific exception class based on the HTTP status code:

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

## Example

Catch specific exceptions to handle different failure modes:

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

!!! tip

    Catch `APIError` as a fallback to handle any unexpected API error. Place it last in your `except` chain so more specific exceptions are matched first.
