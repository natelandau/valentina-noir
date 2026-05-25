"""Server log entry response DTO and JSON-line parser."""

import json
from typing import Any

import msgspec

# Keys produced by LitestarJsonFormatter that map to dedicated LogEntry fields.
_KNOWN_KEYS = frozenset({"level", "timestamp", "message", "name", "exception"})


def _as_str(value: Any) -> str | None:
    """Coerce a JSON value to a string, preserving None.

    The standard fields are not guaranteed to be strings on disk: a logged
    message containing `level=42` makes the JSON formatter emit a numeric
    `level`. Coercing keeps the `str | None` response contract and prevents a
    non-string `level` from crashing `.upper()` during tail filtering.
    """
    return None if value is None else str(value)


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
        exception = data.get("exception")
        return cls(
            timestamp=_as_str(data.get("timestamp")),
            level=_as_str(data.get("level")),
            name=_as_str(data.get("name")),
            message=_as_str(data.get("message")),
            exception=str(exception) if exception else None,
            extra=extra,
        )
