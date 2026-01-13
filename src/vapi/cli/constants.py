"""Constants for the CLI."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from vapi.constants import PROJECT_ROOT_PATH

if TYPE_CHECKING:
    from pathlib import Path


DEV_FOLDER: Final[Path] = PROJECT_ROOT_PATH / ".dev"
API_KEYS_FILE: Final[Path] = DEV_FOLDER / "api_keys.txt"
BASE_URL: Final[str] = "http://127.0.0.1:8000"

dictionary_term_counts: Final[dict[str, int]] = {
    "created": 0,
    "updated": 0,
}
