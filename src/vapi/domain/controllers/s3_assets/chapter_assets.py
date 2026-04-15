"""Chapter assets controller."""

from typing import Annotated

from litestar.datastructures import UploadFile
from litestar.di import Provide
from litestar.enums import RequestEncodingType
from litestar.handlers import delete, get, post
from litestar.params import Body, Parameter

from vapi.constants import AssetType
from vapi.db.sql_models.aws import S3Asset
from vapi.db.sql_models.campaign import CampaignChapter
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.user import User
from vapi.domain import deps, hooks, urls
from vapi.domain.controllers.s3_assets import dto
from vapi.domain.paginator import OffsetPagination
from vapi.lib.guards import user_can_manage_campaign
from vapi.lib.rate_limit_policies import ASSET_UPLOAD_LIMIT
from vapi.openapi.tags import APITags

from . import docs
from .base import BaseAssetsController


class ChapterAssetsController(BaseAssetsController):
    """Chapter assets controller."""

    parent_fk_field = "chapter_id"
    tags = [APITags.CAMPAIGN_CHAPTER_ASSETS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "acting_user": Provide(deps.provide_acting_user),
        "campaign": Provide(deps.provide_campaign_by_id),
        "book": Provide(deps.provide_campaign_book_by_id),
        "chapter": Provide(deps.provide_campaign_chapter_by_id),
        "asset": Provide(deps.provide_s3_asset_by_id),
    }

    @get(
        path=urls.Campaigns.CHAPTER_ASSETS,
        summary="List chapter assets",
        operation_id="listChapterAssets",
        description=docs.LIST_ASSETS_DESCRIPTION,
        cache=True,
    )
    async def list_chapter_assets(
        self,
        chapter: CampaignChapter,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        asset_type: Annotated[
            AssetType | None, Parameter(description="Filter assets by type.")
        ] = None,
    ) -> OffsetPagination[dto.S3AssetResponse]:
        """List all chapter assets."""
        return await self._list_assets(
            parent_id=chapter.id,
            asset_type=asset_type,
            limit=limit,
            offset=offset,
        )

    @get(
        path=urls.Campaigns.CHAPTER_ASSET_DETAIL,
        summary="Get a chapter asset",
        operation_id="getChapterAsset",
        description=docs.GET_ASSET_DESCRIPTION,
        cache=True,
    )
    async def get_chapter_asset(
        self, chapter: CampaignChapter, asset: S3Asset
    ) -> dto.S3AssetResponse:
        """Get a chapter asset."""
        return await self._get_asset(asset, parent_id=chapter.id)

    @post(
        path=urls.Campaigns.CHAPTER_ASSET_UPLOAD,
        summary="Upload a chapter asset",
        operation_id="uploadChapterAsset",
        description=docs.UPLOAD_ASSET_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
        guards=[user_can_manage_campaign],
        opt={"rate_limits": [ASSET_UPLOAD_LIMIT]},
    )
    async def handle_file_upload(
        self,
        company: Company,
        chapter: CampaignChapter,
        acting_user: User,
        data: Annotated[UploadFile, Body(media_type=RequestEncodingType.MULTI_PART)],
    ) -> dto.S3AssetResponse:
        """Upload a chapter asset."""
        return await self._create_asset(
            parent_id=chapter.id,
            company_id=company.id,
            upload_user_id=acting_user.id,
            data=data,
        )

    @delete(
        path=urls.Campaigns.CHAPTER_ASSET_DELETE,
        summary="Delete a chapter asset",
        operation_id="deleteChapterAsset",
        description=docs.DELETE_ASSET_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
        guards=[user_can_manage_campaign],
    )
    async def delete_chapter_asset(self, asset: S3Asset, acting_user: User) -> None:  # noqa: ARG002
        """Delete a chapter asset."""
        await self._delete_asset(asset=asset)
