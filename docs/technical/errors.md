---
icon: lucide/alert-circle
---

# Error Handling

## Overview

All errors follow the [RFC 9457 Problem Details](https://datatracker.ietf.org/doc/html/rfc9457) standard. This format provides consistent, machine-readable error responses across all endpoints.

## Error Response Structure

All error responses use the `application/problem+json` media type with these fields:

| Field        | Type    | Description                                                                                                             |
| ------------ | ------- | ----------------------------------------------------------------------------------------------------------------------- |
| `status`     | integer | HTTP status code                                                                                                        |
| `title`      | string  | Short, human-readable summary of the problem type                                                                       |
| `detail`     | string  | Human-readable explanation specific to this occurrence                                                                  |
| `instance`   | string  | The request path, without host or query string                                                                          |
| `request_id` | string  | Unique request identifier (matches the `X-Request-Id` response header)                                                  |
| `code`       | string  | Optional. A stable, machine-readable identifier for errors that clients handle in code. Match on this, not on `detail`. |

## Standard Error Response

```json
{
    "status": 404,
    "title": "Not Found",
    "detail": "Character '68c1f7152cae3787a09a74fa' not found",
    "instance": "/api/v1/companies/abc123/campaigns/ghi789/characters/68c1f7152cae3787a09a74fa",
    "request_id": "req_7H2kB9xQ4mN1pL5w3nR2Yg"
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
| 413  | Content Too Large       | Request body is larger than 5 MB                                   |
| 429  | Too Many Requests       | Rate limit exceeded                                                |
| 500  | Internal Server Error   | Unexpected server error                                            |

## Validation Errors

Validation errors (400 Bad Request) include an `invalid_parameters` array. Each entry has a `field` and a `message`.

```json
{
    "status": 400,
    "title": "Bad Request",
    "detail": "Validation failed for one or more fields.",
    "instance": "/api/v1/companies/abc123/campaigns",
    "request_id": "req_m4N5o6P7q8R9s0T1",
    "invalid_parameters": [
        {
            "field": "danger",
            "message": "Must be at most 5."
        }
    ]
}
```

Each message in the [Messages](#messages) table is a complete sentence. You can show it to your users as it is. It never repeats the value that you sent. Other entries can come from the rules of an endpoint, and their messages can differ.

The `field` is the path of the field in the request that you sent. For a nested field, the path joins the names with dots, for example `metadata.source`. For a list item, the path includes the position of the item, for example `traits[2].value`. If the request body is a list, the path starts with the position, for example `[0].trait_id`. For a query parameter, a path parameter, or a header, `field` is the name of the parameter. If no single field caused the error, `field` is `body`.

The API reports at most one error for each parameter. Each query parameter, path parameter, and header is one parameter, and the request body is one parameter. If two fields in the body fail, the response names only one of them. If you fix that field and send the request again, the response can name a different field.

### Messages

| Message                                                                  | Meaning                                                                                |
| ------------------------------------------------------------------------ | -------------------------------------------------------------------------------------- |
| `This field is required.`                                                | The request does not contain the field, the parameter, or the body.                    |
| `Is not a recognized field.`                                             | The field does not exist. Only endpoints that reject unknown fields send this message. |
| `Must have a value.`                                                     | The field is `null`, and `null` is not allowed.                                        |
| `Must be at most 5.`                                                     | The number is more than the maximum.                                                   |
| `Must be at least 1.`                                                    | The number is less than the minimum.                                                   |
| `Must be less than 10.`                                                  | The number is not below an exclusive limit.                                            |
| `Must be greater than 0.`                                                | The number is not above an exclusive limit.                                            |
| `Must be at most 50 characters.`                                         | The text is too long.                                                                  |
| `Must be at least 3 characters.`                                         | The text is too short.                                                                 |
| `Must have at most 10 items.`                                            | The list is too long.                                                                  |
| `Must have at least 2 items.`                                            | The list is too short.                                                                 |
| `Must be one of: BOOK, CONSUMABLE, ENCHANTED, EQUIPMENT, OTHER, WEAPON.` | The value is not in the list of allowed values. The list depends on the field.         |
| `Is not an allowed value.`                                               | The value is not allowed, and the API has no list to show.                             |
| `Must be a whole number.`                                                | The value is not an integer.                                                           |
| `Must be a number.`                                                      | The value is not a number.                                                             |
| `Must be text.`                                                          | The value is not a string.                                                             |
| `Must be true or false.`                                                 | The value is not a boolean.                                                            |
| `Must be a list.`                                                        | The value is not an array.                                                             |
| `Must be an object.`                                                     | The value is not an object.                                                            |
| `Must be a valid ID.`                                                    | The value is not a UUID.                                                               |
| `Must be a valid date.`                                                  | The value is not a date.                                                               |
| `Must be a valid time.`                                                  | The value is not a time.                                                               |
| `Must be a valid date and time.`                                         | The value is not a date and time.                                                      |
| `Is not in the expected format.`                                         | The text does not match the required pattern.                                          |
| `Is not valid.`                                                          | The value fails a rule that no other message describes.                                |
| `One or more fields did not pass validation.`                            | The request fails a rule, and the API cannot name one field. `field` is `body`.        |

A bound of 1 uses the singular, for example `Must be at least 1 character.` and `Must have at most 1 item.`

Some rules depend on more than one property of a field, for example text that is empty after the API removes the spaces at its start and end. When such a rule rejects a field, the response names the field with `Is not valid.` If the rule applies to the request as a whole, `field` is `body`.

### Limits in the OpenAPI schema

The OpenAPI schema of each request body lists the limits of each field, such as `maxLength`, `minimum`, `maximum`, and `maxItems`.

## Error Examples by Type

### 401 Unauthorized

Missing or invalid API key.

```json
{
    "status": 401,
    "title": "Unauthorized",
    "detail": "API key not provided",
    "instance": "/api/v1/companies",
    "request_id": "req_a1B2c3D4e5F6g7H8"
}
```

### 403 Forbidden

Valid API key but insufficient permissions for the requested action.

```json
{
    "status": 403,
    "title": "Forbidden",
    "detail": "No rights to access this resource",
    "instance": "/api/v1/companies/abc123/users",
    "request_id": "req_j9K0l1M2n3O4p5Q6"
}
```

### 404 Not Found

Requested resource does not exist.

```json
{
    "status": 404,
    "title": "Not Found",
    "detail": "Company 'abc123' not found",
    "instance": "/api/v1/companies/abc123",
    "request_id": "req_r7S8t9U0v1W2x3Y4"
}
```

### 409 Conflict

Request conflicts with current state. Examples:

- You reuse an idempotency key with a different request body.
- You send a request while an earlier request with the same idempotency key is still running. This response has `code: "IDEMPOTENCY_IN_PROGRESS"` and a `Retry-After` header. Wait that many seconds, then retry with the same key and body. See [Concurrent Requests](idempotency.md#concurrent-requests).
- You change a character trait's value after another request changed it. Fetch the trait again and retry. See [Modifying Trait Values](../concepts/character_traits.md#modifying-trait-values).

Only the in-progress conflict carries a `code`. Do not resend any other 409 unchanged: fix the request or reload the resource first.

```json
{
    "status": 409,
    "title": "Conflict",
    "detail": "Idempotency key 'your-key' was previously used with a different request body. Each unique request must use a unique idempotency key.",
    "instance": "/api/v1/companies/abc123/users",
    "request_id": "req_z5A6b7C8d9E0f1G2"
}
```

### 429 Too Many Requests

Rate limit exceeded. See [Rate Limiting](rate_limits.md) for details.

```json
{
    "status": 429,
    "title": "Too Many Requests",
    "detail": "You are being rate limited.",
    "instance": "/api/v1/companies",
    "request_id": "req_h3I4j5K6l7M8n9O0"
}
```

### 500 Internal Server Error

Unexpected server error occurred.

```json
{
    "status": 500,
    "title": "Internal Server Error",
    "detail": "Something went wrong on our end. Please contact support if the issue persists.",
    "instance": "/api/v1/companies",
    "request_id": "req_p1Q2r3S4t5U6v7W8"
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
    request_id = error.get("request_id") or response.headers.get("X-Request-Id")

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
        raise Exception(f"API error ({request_id}): {error['detail']}")
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
    const requestId = error.request_id || response.headers.get("X-Request-Id");

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
            throw new Error(`API error (${requestId}): ${error.detail}`);
    }
}
```

## Best Practices

1. **Check status codes first** - Determine the error category before parsing the response body
2. **Parse the detail field** - Extract specific information about what went wrong
3. **Handle validation errors** - Check for `invalid_parameters` to provide user-friendly form feedback
4. **Implement retry logic** - Use exponential backoff for 429 and 5xx errors
5. **Include the request ID** - Use the `request_id` field from error responses (or `X-Request-Id` header) when contacting support or correlating with your own logs
