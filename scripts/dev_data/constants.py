"""Filesystem paths for generated dev-data artifacts."""

from pathlib import Path
from typing import Final

from vapi.constants import PROJECT_ROOT_PATH

DEV_FOLDER: Final[Path] = PROJECT_ROOT_PATH / ".dev"
API_KEYS_FILE: Final[Path] = DEV_FOLDER / "api_keys.txt"
