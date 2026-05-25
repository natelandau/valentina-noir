"""Server log entry response DTO and JSON-line parser."""

import json
from typing import Any

import msgspec

# Keys produced by LitestarJsonFormatter that map to dedicated LogEntry fields.
_KNOWN_KEYS = frozenset({"level", "timestamp", "message", "name", "exception"})


class LogEntry(msgspec.Struct):
    """A single application log line parsed from its JSON representation."""

    timestamp: str | None = None
    level: str | None = None
    name: str | None = None
    message: str | None = None
    exception: str | None = None
    extra: dict[str, Any] = msgspec.field(default_factory=dict)
    raw: str | None = None

    @classmethod
    def from_line(cls, line: str) -> "LogEntry":
        """Parse one JSON log line into a structured entry.

        Falls back to populating `raw` when the line is not a JSON object, so a
        single malformed line never fails the whole request.

        Args:
            line: A single line from the server log file.

        Returns:
            LogEntry: A structured log entry with known fields populated and
                unknown keys collected in `extra`, or with only `raw` set if
                the line is not valid JSON.
        """
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return cls(raw=line)

        if not isinstance(data, dict):
            return cls(raw=line)

        extra = {k: v for k, v in data.items() if k not in _KNOWN_KEYS}
        return cls(
            timestamp=data.get("timestamp"),
            level=data.get("level"),
            name=data.get("name"),
            message=data.get("message"),
            exception=data.get("exception") or None,
            extra=extra,
        )
