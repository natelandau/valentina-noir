"""Avatar service: normalize, store, and manage user avatar assets."""

from uuid import UUID

from vapi.db.sql_models.aws import S3Asset
from vapi.db.sql_models.user import User
from vapi.domain.services.aws_service import AWSS3Service
from vapi.utils.images import normalize_avatar

__all__ = ("AvatarService",)


class AvatarService:
    """Manage a user's custom avatar stored as a normalized S3 asset."""

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
        """
        # Lazy import: handlers package imports services, so a top-level import here
        # would create a circular import during package initialization.
        from vapi.domain.handlers.archive_handlers import archive_single_asset

        webp_bytes = normalize_avatar(data)

        asset = await AWSS3Service().upload_asset(
            company_id=company_id,
            uploaded_by_id=acting_user_id,
            parent_id=user.id,
            parent_fk_field="user_parent_id",
            data=webp_bytes,
            filename="avatar.webp",
            mime_type="image/webp",
        )

        previous_asset_id = user.avatar_asset_id
        user.avatar_url = asset.public_url
        user.avatar_asset_id = asset.id
        await user.save()

        if previous_asset_id is not None:
            previous = await S3Asset.filter(id=previous_asset_id).first()
            if previous is not None:
                await archive_single_asset(previous)

        return user

    async def remove_avatar(self, *, user: User) -> User:
        """Remove a user's custom avatar, archiving the asset and clearing the columns.

        The avatar falls back to the OAuth-derived avatar (or none) after removal.

        Args:
            user: The user whose avatar is being removed.

        Returns:
            The updated user with avatar_url and avatar_asset_id cleared.
        """
        # Lazy import: handlers package imports services, so a top-level import here
        # would create a circular import during package initialization.
        from vapi.domain.handlers.archive_handlers import archive_single_asset

        previous_asset_id = user.avatar_asset_id
        user.avatar_url = None
        user.avatar_asset_id = None
        await user.save()

        if previous_asset_id is not None:
            previous = await S3Asset.filter(id=previous_asset_id).first()
            if previous is not None:
                await archive_single_asset(previous)

        return user
