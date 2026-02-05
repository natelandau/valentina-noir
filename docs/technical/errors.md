---
icon: lucide/alert-circle
---

# Error Handling

## Overview

All errors follow the [RFC 9457 Problem Details](https://datatracker.ietf.org/doc/html/rfc9457) standard. This format provides consistent, machine-readable error responses across all endpoints.

## Error Response Structure

All error responses use the `application/problem+json` media type with these fields:

| Field      | Type    | Description                                                                    |
| ---------- | ------- | ------------------------------------------------------------------------------ |
| `status`   | integer | HTTP status code                                                               |
| `title`    | string  | Short, human-readable summary of the problem type                              |
| `detail`   | string  | Human-readable explanation specific to this occurrence                         |
| `instance` | string  | URI reference identifying the specific occurrence (typically the request path) |

## Standard Error Response

```json
{
    "status": 404,
    "title": "Not Found",
    "detail": "Character '68c1f7152cae3787a09a74fa' not found",
    "instance": "/api/v1/companies/abc123/users/def456/campaigns/ghi789/characters/68c1f7152cae3787a09a74fa"
}
```

## Common HTTP Status Codes

| Code | Title                   | Description                                                        |
| ---- | ----------------------- | ------------------------------------------------------------------ |
| 400  | Bad Request             | Invalid request syntax or parameters                               |
| 401  | Unauthorized            | Missing or invalid API key                                         |
| 403  | Forbidden               | Valid API key but insufficient permissions                         |
| 404  | Not Found               | Requested resource does not exist                                  |
| 409  | Conflict                | Request conflicts with current state                               |
| 429  | Too Many Requests       | Rate limit exceeded                                                |
| 500  | Internal Server Error   | Unexpected server error                                            |

## Validation Errors

Validation errors (400 Bad Request) include an `invalid_parameters` array identifying which fields failed validation:

```json
{
    "status": 400,
    "title": "Bad Request",
    "detail": "Validation failed for one or more fields.",
    "instance": "/api/v1/companies/abc123/users",
    "invalid_parameters": [
        {
            "field": "name",
            "message": "Field required"
        },
        {
            "field": "role",
            "message": "Input should be 'ADMIN', 'STORYTELLER' or 'PLAYER'"
        }
    ]
}
```

## Error Examples by Type

### 401 Unauthorized

Missing or invalid API key.

```json
{
    "status": 401,
    "title": "Unauthorized",
    "detail": "API key not provided",
    "instance": "/api/v1/companies"
}
```

### 403 Forbidden

Valid API key but insufficient permissions for the requested action.

```json
{
    "status": 403,
    "title": "Forbidden",
    "detail": "No rights to access this resource",
    "instance": "/api/v1/companies/abc123/users"
}
```

### 404 Not Found

Requested resource does not exist.

```json
{
    "status": 404,
    "title": "Not Found",
    "detail": "Company 'abc123' not found",
    "instance": "/api/v1/companies/abc123"
}
```

### 409 Conflict

Request conflicts with current state, such as reusing an idempotency key with a different request body.

```json
{
    "status": 409,
    "title": "Conflict",
    "detail": "Idempotency key 'your-key' was previously used with a different request body. Each unique request must use a unique idempotency key.",
    "instance": "/api/v1/companies/abc123/users"
}
```

### 429 Too Many Requests

Rate limit exceeded. See [Rate Limiting](rate_limits.md) for details.

```json
{
    "status": 429,
    "title": "Too Many Requests",
    "detail": "You are being rate limited.",
    "instance": "/api/v1/companies"
}
```

### 500 Internal Server Error

Unexpected server error occurred.

```json
{
    "status": 500,
    "title": "Internal Server Error",
    "detail": "Something went wrong on our end. Please contact support if the issue persists.",
    "instance": "/api/v1/companies"
}
```

## Error Handling Examples

### Python

```python
import requests

def make_request(url, api_key):
    response = requests.get(url, headers={"X-API-KEY": api_key})

    if response.status_code == 200:
        return response.json()

    error = response.json()

    if response.status_code == 400:
        # Handle validation errors
        if "invalid_parameters" in error:
            for param in error["invalid_parameters"]:
                print(f"Field '{param['field']}': {param['message']}")
        raise ValueError(error["detail"])

    elif response.status_code == 401:
        raise PermissionError("Invalid or missing API key")

    elif response.status_code == 403:
        raise PermissionError(error["detail"])

    elif response.status_code == 404:
        raise LookupError(error["detail"])

    elif response.status_code == 429:
        # Handle rate limiting - see Rate Limiting docs
        retry_after = response.headers.get("Retry-After", 60)
        raise Exception(f"Rate limited. Retry after {retry_after} seconds")

    else:
        raise Exception(f"API error: {error['detail']}")
```

### JavaScript

```javascript
async function makeRequest(url, apiKey) {
    const response = await fetch(url, {
        headers: { "X-API-KEY": apiKey },
    });

    if (response.ok) {
        return response.json();
    }

    const error = await response.json();

    switch (response.status) {
        case 400:
            // Handle validation errors
            if (error.invalid_parameters) {
                error.invalid_parameters.forEach((param) => {
                    console.error(`Field '${param.field}': ${param.message}`);
                });
            }
            throw new Error(error.detail);

        case 401:
            throw new Error("Invalid or missing API key");

        case 403:
            throw new Error(error.detail);

        case 404:
            throw new Error(error.detail);

        case 429:
            const retryAfter = response.headers.get("Retry-After") || 60;
            throw new Error(`Rate limited. Retry after ${retryAfter} seconds`);

        default:
            throw new Error(`API error: ${error.detail}`);
    }
}
```

## Best Practices

1. **Check status codes first** - Determine the error category before parsing the response body
2. **Parse the detail field** - Extract specific information about what went wrong
3. **Handle validation errors** - Check for `invalid_parameters` to provide user-friendly form feedback
4. **Implement retry logic** - Use exponential backoff for 429 and 5xx errors
5. **Log the instance field** - Correlate errors with specific requests during debugging
