"""Session store for per-trait XP recoup floors.

A recoup floor records the value of a character trait at the start of an edit
session so the WITHIN_SESSION recoup policy can prevent lowering a trait below
where it began. Floors are namespaced per (user, character, trait) and expire
with the configured session TTL.
"""

from litestar.stores.base import Store

from vapi.constants import RECOUP_XP_SESSION_LENGTH


class RecoupFloorStore:
    """Read and write per-(user, character, trait) recoup floors in a session store."""

    def __init__(self, store: Store) -> None:
        self._store = store

    @staticmethod
    def _key(*, user_id: str, character_id: str, trait_id: str) -> str:
        """Build the Redis key for a (user, character, trait) recoup floor."""
        return f"recoup_floor:{user_id}:{character_id}:{trait_id}"

    async def get(self, *, user_id: str, character_id: str, trait_id: str) -> int | None:
        """Read the stored recoup floor for this trait, or None if absent or expired."""
        key = self._key(user_id=user_id, character_id=character_id, trait_id=trait_id)
        raw = await self._store.get(key)
        if raw is None:
            return None
        return int(raw.decode("utf-8") if isinstance(raw, bytes) else raw)

    async def set(self, *, user_id: str, character_id: str, trait_id: str, value: int) -> None:
        """Write a new floor value with the configured session TTL."""
        key = self._key(user_id=user_id, character_id=character_id, trait_id=trait_id)
        await self._store.set(key, str(value).encode("utf-8"), expires_in=RECOUP_XP_SESSION_LENGTH)
