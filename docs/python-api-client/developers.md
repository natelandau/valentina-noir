---
icon: lucide/terminal
---

# Developer Service

Manage your developer profile, including viewing account details, updating settings, and regenerating your API key.

## Initialize the Service

```python
from vclient import developer_service

developer = developer_service()
```

## Available Methods

| Method                              | Returns                 | Description                     |
| ----------------------------------- | ----------------------- | ------------------------------- |
| `get_me()`                          | `MeDeveloper`           | Retrieve your developer profile |
| `update_me(request=None, **kwargs)` | `MeDeveloper`           | Update your profile fields      |
| `regenerate_api_key()`              | `MeDeveloperWithApiKey` | Generate a new API key          |

## Examples

### Retrieve Your Profile

Get your authenticated developer account details.

```python
me = await developer.get_me()
print(f"Username: {me.username}")
print(f"Companies: {len(me.companies)}")
```

### Update Your Profile

Modify your developer account settings. You can pass a model object or use keyword arguments.

```python
from vclient.models import MeDeveloperUpdate

# Option 1: Use a model object (preferred)
update = MeDeveloperUpdate(username="new_username", email="newemail@example.com")
updated = await developer.update_me(update)

# Option 2: Pass fields as keyword arguments
updated = await developer.update_me(username="new_username")
```

### Regenerate API Key

Generate a new API key for authentication. The current key becomes invalid immediately.

```python
result = await developer.regenerate_api_key()
print(f"New API Key: {result.api_key}")
```

!!! warning "Save Your API Key"

    Regenerating your API key immediately invalidates the current key. Save the new key from the response - it will not be displayed again.

## Related Documentation

- [Response Models](models.md) - View `MeDeveloper` and `MeDeveloperWithApiKey` model schemas
