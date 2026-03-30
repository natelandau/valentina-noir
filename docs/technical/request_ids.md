---
icon: lucide/fingerprint
---

# Request IDs

## Overview

Every API response includes a unique request ID in the `X-Request-Id` header. Use this ID to correlate requests with server-side logs when debugging issues or contacting support.

## How It Works

The server generates a unique ID for every incoming request and returns it in the response:

1. Client sends a request (no special header needed)
2. Server generates a unique `req_`-prefixed ID
3. Server processes the request normally
4. Server returns the ID in the `X-Request-Id` response header

```mermaid
flowchart LR
    A[Client sends request] --> B[Server generates req_abc123...]
    B --> C[Server processes request]
    C --> D[Response includes X-Request-Id header]
```

## Response Header

The `X-Request-Id` header is present on **every** response — both successful and error responses:

```yaml
HTTP/1.1 200 OK
---
Content-Type: application/json
X-Request-Id: req_7H2kB9xQ4mN1pL5w3nR2Yg
```

| Header         | Description                          |
| -------------- | ------------------------------------ |
| `X-Request-Id` | Unique identifier for this request   |

## Error Responses

Error responses include the request ID both in the response header **and** in the JSON body as the `request_id` field:

```json
{
    "status": 404,
    "title": "Not Found",
    "detail": "Character '68c1f7152cae3787a09a74fa' not found",
    "instance": "/api/v1/companies/abc123/users/def456/campaigns/ghi789/characters/68c1f7152cae3787a09a74fa",
    "request_id": "req_7H2kB9xQ4mN1pL5w3nR2Yg"
}
```

This makes it easy to capture the request ID when handling errors — you're already parsing the error body.

## Examples

### Python

```python
import requests

def make_request(url, api_key):
    """Make an API request and log the request ID for debugging."""
    response = requests.get(url, headers={"X-API-KEY": api_key})

    request_id = response.headers.get("X-Request-Id")

    if not response.ok:
        error = response.json()
        print(f"Error on request {request_id}: {error['detail']}")
        # The request_id is also in the error body
        assert error.get("request_id") == request_id
        raise Exception(error["detail"])

    return response.json()
```

### JavaScript

```javascript
async function makeRequest(url, apiKey) {
    const response = await fetch(url, {
        headers: { "X-API-KEY": apiKey },
    });

    const requestId = response.headers.get("X-Request-Id");

    if (!response.ok) {
        const error = await response.json();
        console.error(`Error on request ${requestId}: ${error.detail}`);
        // The request_id is also in the error body
        throw new Error(`${error.detail} (request: ${requestId})`);
    }

    return response.json();
}
```

## Best Practices

1. **Log request IDs client-side** — Store the `X-Request-Id` value alongside your application logs for debugging
2. **Include in support requests** — When contacting support about an API issue, include the request ID so we can trace exactly what happened
3. **Capture from error bodies** — When handling errors, the `request_id` field in the JSON body is the easiest place to find it
4. **No client action required** — Request IDs are generated automatically; you don't need to send any special header
