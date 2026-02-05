---
icon: lucide/activity
---

# System Service

Check API health and system status. Use this service to monitor the API's operational state and verify that all dependencies are running correctly.

!!! info "No Authentication Required"
    This service does not require authentication. Use it for health checks and monitoring without an API key.

## Initialize the Service

```python
from vclient import system_service

system = system_service()
```

## Available Methods

| Method     | Returns        | Description                                |
| ---------- | -------------- | ------------------------------------------ |
| `health()` | `SystemHealth` | Check API server and dependency health     |

## Examples

### Check System Health

Verify that the API server, database, and cache are operational.

```python
health = await system.health()

print(f"API Version: {health.version}")
print(f"Database Status: {health.database_status}")
print(f"Cache Status: {health.cache_status}")

# Check if all systems are operational
if health.database_status == "online" and health.cache_status == "online":
    print("All systems operational")
else:
    print("System degradation detected")
```

### Use in Monitoring

Integrate health checks into your monitoring infrastructure.

```python
import asyncio
from vclient import system_service

async def monitor_health():
    """Poll API health every 60 seconds."""
    system = system_service()

    while True:
        try:
            health = await system.health()
            if health.database_status != "online":
                # Alert: database connection failed
                send_alert(f"Database offline: {health.database_status}")
        except Exception as e:
            # Alert: API unreachable
            send_alert(f"API health check failed: {e}")

        await asyncio.sleep(60)
```

## Related Documentation

- [Response Models](models.md) - View `SystemHealth` model schema
