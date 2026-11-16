"""Avatar service: normalize, store, and manage user avatar assets."""

from uuid import UUID

from tortoise.transactions import in_transaction

from vapi.db.sql_models.user import User
from vapi.domain.services.aws_svc import AWSS3Service
from vapi.lib.exceptions import NotFoundError
from vapi.utils.images import normalize_avatar, run_image_decode

__all__ = ("AvatarService",)


class AvatarService:
    """Manage a user's custom avatar stored as a normalized S3 asset."""

    async def _archive_asset(self, asset_id: UUID | None) -> None:
        """Soft-archive a replaced, removed, or orphaned avatar asset, if any."""
        if asset_id is None:
            return
        # Lazy import: handlers package imports services, so a top-level import here
        # would create a circular import during package initialization.
        from vapi.domain.handlers.archive_handlers import archive_single_asset

        await archive_single_asset(asset_id)

    async def _write_avatar(
        self, user: User, *, avatar_url: str | None, avatar_asset_id: UUID | None
    ) -> None:
        """Record avatar columns on the locked, committed user row and archive the old asset.

        Callers load the user early in the request and may await slow work (decode,
        S3 upload) before writing, so a concurrent archive or role change must be
        read from the row, not overwritten from the stale copy. The replaced asset is
        archived in the same transaction so it can never stay active once unlinked.

        Args:
            user: The user whose avatar columns are written; reloaded from the row.
            avatar_url: The new avatar URL, or None to clear it.
            avatar_asset_id: The new avatar asset id, or None to clear it.

        Raises:
            NotFoundError: If the user is archived.
        """
        async with in_transaction():
            if not await user.lock_for_update(is_archived=False):
                raise NotFoundError(detail="User not found")
            previous_asset_id = user.avatar_asset_id
            user.avatar_url = avatar_url  # ty:ignore[invalid-assignment]
            user.avatar_asset_id = avatar_asset_id
            await user.save(update_fields=["avatar_url", "avatar_asset_id"])
            await self._archive_asset(previous_asset_id)

    async def set_avatar(
        self,
        *,
        user: User,
        company_id: UUID,
        acting_user_id: UUID,
        data: bytes,
    ) -> User:
        """Normalize and store an uploaded avatar, replacing any existing one.

        Normalize the bytes to a 512x512 WebP, upload as a user-owned S3 asset, record
        the new asset's id and URL on the user, and soft-archive the previous avatar
        asset (so the scheduled purge removes it from S3).

        Args:
            user: The user whose avatar is being set.
            company_id: The company the asset belongs to.
            acting_user_id: The user performing the upload (asset uploaded_by).
            data: Raw uploaded image bytes.

        Returns:
            The updated user with avatar_url and avatar_asset_id set.

        Raises:
            NotFoundError: If the user was archived before the change was recorded.
        """
        # Decoding is CPU-bound; keep it off the event loop so other requests keep flowing
        webp_bytes = await run_image_decode(normalize_avatar, data)

        asset = await AWSS3Service().upload_asset(
            company_id=company_id,
            uploaded_by_id=acting_user_id,
            parent_id=user.id,
            parent_fk_field="user_parent_id",
            data=webp_bytes,
            filename="avatar.webp",
        )

        try:
            await self._write_avatar(user, avatar_url=asset.public_url, avatar_asset_id=asset.id)
        except Exception:
            # The uploaded asset is linked to nothing, so archive it for the purge
            await self._archive_asset(asset.id)
            raise

        return user

    async def remove_avatar(self, *, user: User) -> User:
        """Remove a user's custom avatar, archiving the asset and clearing the columns.

        The avatar falls back to the OAuth-derived avatar (or none) after removal.

        Args:
            user: The user whose avatar is being removed.

        Returns:
            The updated user with avatar_url and avatar_asset_id cleared.

        Raises:
            NotFoundError: If the user was archived before the change was recorded.
        """
        await self._write_avatar(user, avatar_url=None, avatar_asset_id=None)
        return user
