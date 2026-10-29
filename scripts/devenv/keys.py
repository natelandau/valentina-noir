"""Store for raw developer API keys.

The database keeps only hashed keys, so the raw value is saved here when a dev tool mints it.
"""

import json
from uuid import UUID

from scripts.dev_data.api_keys import DevApiKey
from scripts.devenv.files import write_private
from vapi.constants import PROJECT_ROOT_PATH

DEV_DIR = PROJECT_ROOT_PATH / ".dev"
KEYS_FILE = DEV_DIR / "api-keys.json"


def load_keys() -> dict[UUID, str]:
    """Return the recorded raw keys.

    Returns:
        Developer ID to raw API key. Empty when nothing was recorded.
    """
    if not KEYS_FILE.exists():
        return {}
    try:
        raw = json.loads(KEYS_FILE.read_text())
        return {UUID(developer_id): key for developer_id, key in raw.items()}
    except (ValueError, AttributeError) as error:
        msg = f"{KEYS_FILE} is corrupt ({error}); fix or delete it"
        raise ValueError(msg) from error


def record_keys(keys: list[DevApiKey], *, replace: bool) -> None:
    """Save raw keys to the key file, readable only by the owner.

    Args:
        keys: Freshly minted keys.
        replace: Drop every existing entry first (a whole new set was minted). Otherwise merge
            by developer ID, the newest key winning.
    """
    merged = {} if replace else load_keys()
    merged.update({key.developer_id: key.api_key for key in keys})
    payload = json.dumps({str(developer_id): key for developer_id, key in merged.items()}, indent=2)

    write_private(KEYS_FILE, payload)
