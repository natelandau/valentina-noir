"""ID map registry for tracking old→new ID relationships during migration."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


class IDMap:
    """Track old ID → new UUID mappings across entity types.

    Users are keyed by (old_user_id, old_guild_id) to handle users in multiple guilds.
    All other entities are keyed by their old ID (str or int).
    """

    def __init__(self) -> None:
        self._maps: dict[str, dict] = {
            "guild": {},
            "user": {},
            "campaign": {},
            "character": {},
            "book": {},
            "chapter": {},
            "trait": {},
        }

    def add(self, entity_type: str, old_id: str | int | tuple, new_id: UUID) -> None:
        """Register an old→new ID mapping.

        Args:
            entity_type: The entity type (guild, user, campaign, etc.).
            old_id: The old ID. For users, pass (user_id, guild_id) tuple.
            new_id: The new UUID.
        """
        self._maps[entity_type][old_id] = new_id

    def get(self, entity_type: str, old_id: str | int | tuple) -> UUID | None:
        """Look up a new ID by entity type and old ID.

        Args:
            entity_type: The entity type.
            old_id: The old ID.

        Returns:
            The new UUID, or None if not found.
        """
        return self._maps[entity_type].get(old_id)

    def get_all(self, entity_type: str) -> dict:
        """Get all mappings for an entity type.

        Args:
            entity_type: The entity type.

        Returns:
            Dictionary of old_id → new_id mappings.
        """
        return self._maps[entity_type]

    def contains(self, entity_type: str, old_id: str | int | tuple) -> bool:
        """Check if an old ID has been mapped.

        Args:
            entity_type: The entity type.
            old_id: The old ID.

        Returns:
            True if the old ID has been mapped.
        """
        return old_id in self._maps[entity_type]

    def find_entity_type(self, old_id: str) -> str | None:
        """Find which entity type an old ID belongs to (for notes parent_id resolution).

        Searches campaign, book, chapter, character maps in that order.

        Args:
            old_id: The old ID to search for.

        Returns:
            The entity type name, or None if not found.
        """
        for entity_type in ("campaign", "book", "chapter", "character"):
            if old_id in self._maps[entity_type]:
                return entity_type
        return None
