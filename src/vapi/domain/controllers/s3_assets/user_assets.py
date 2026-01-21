"""User assets controller."""

from typing import Annotated

from litestar.datastructures import UploadFile
from litestar.di import Provide
from litestar.enums import RequestEncodingType
from litestar.handlers import delete, get, post
from litestar.params import Body, Parameter

from vapi.constants import S3AssetType
from vapi.db.models import Company, S3Asset, User
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.openapi.tags import APITags

from .base import BaseAssetsController


class UserAssetsController(BaseAssetsController):
    """User assets controller."""

    tags = [APITags.USERS_ASSETS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_user_by_id_and_company),
        "asset": Provide(deps.provide_s3_asset_by_id),
    }

    @get(
        path=urls.Users.ASSETS,
        summary="List user assets",
        operation_id="listUserAssets",
        description="List all assets for a user.",
        cache=True,
    )
    async def list_user_assets(
        self,
        user: User,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        asset_type: Annotated[
            S3AssetType | None, Parameter(description="Filter assets by type.")
        ] = None,
    ) -> OffsetPagination[S3Asset]:
        """List all user assets."""
        return await self._list_assets(
            parent_id=user.id,
            asset_type=asset_type,
            limit=limit,
            offset=offset,
        )

    @get(
        path=urls.Users.ASSET_DETAIL,
        summary="Get a user asset",
        operation_id="getUserAsset",
        description="Get an asset for a user.",
        cache=True,
    )
    async def get_user_asset(self, user: User, asset: S3Asset) -> S3Asset:
        """Get a user asset."""
        return await self._get_asset(asset, parent=user)

    @post(
        path=urls.Users.ASSET_UPLOAD,
        summary="Upload a user asset",
        operation_id="uploadUserAsset",
        description="Upload an asset for a user.",
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def handle_file_upload(
        self,
        company: Company,
        user: User,
        data: Annotated[UploadFile, Body(media_type=RequestEncodingType.MULTI_PART)],
    ) -> S3Asset:
        """Upload a user asset."""
        return await self._create_asset(
            parent=user,
            company_id=company.id,
            upload_user_id=user.id,
            data=data,
        )

    @delete(
        path=urls.Users.ASSET_DELETE,
        summary="Delete a user asset",
        operation_id="deleteUserAsset",
        description="Delete an asset for a user.",
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def delete_user_asset(self, asset: S3Asset) -> None:
        """Delete a user asset."""
        await self._delete_asset(asset=asset)
