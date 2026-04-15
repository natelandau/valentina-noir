"""Application uptime tracking."""

from datetime import UTC, datetime

APP_START_TIME: datetime = datetime.now(tz=UTC)
