# Developing Your Client

Valentina Noir is a REST API for building World of Darkness tabletop gaming applications. This guide covers the essential concepts for integrating with the API.

When you're read to start making requests, read the **[full API Documentation](https://api.valentina-noir.com/docs)** for detailed information on the API endpoints and how to use them.

## Getting Started

1. At this time, API keys are only available to developers who have been granted access by the Valentina Noir team. Please contact us at [support@valentina-noir.com](mailto:support@valentina-noir.com) to request an API key.
2. Authenticate your application using your API key
3. Start making requests

## Quick Reference

### Making Requests

All requests require the `X-API-KEY` header:

```shell
GET /api/v1/companies HTTP/1.1
Host: api.valentina-noir.com
X-API-KEY: your-api-key-here
```

For `POST`, `PUT`, and `PATCH` requests, include an `Idempotency-Key` header to enable safe retries:

```shell
POST /api/v1/companies/{company_id}/users HTTP/1.1
Host: api.valentina-noir.com
X-API-KEY: your-api-key-here
Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000
Content-Type: application/json
```

## Base URL

All API endpoints use the following base URL:

```
https://api.valentina-noir.com/api/v1
```

## Response Format

All responses are returned as JSON. Successful responses return the requested data directly. Error responses follow the [RFC 9457 Problem Details](errors.md) format.

## Need Help?

-   Review the API documentation for endpoint-specific details
-   Check the [Error Handling](errors.md) guide for troubleshooting
