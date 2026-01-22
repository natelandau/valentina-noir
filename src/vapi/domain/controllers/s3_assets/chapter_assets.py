"""Chapter assets controller."""

from typing import Annotated

from litestar.datastructures import UploadFile
from litestar.di import Provide
from litestar.enums import RequestEncodingType
from litestar.handlers import delete, get, post
from litestar.params import Body, Parameter

from vapi.constants import S3AssetType
from vapi.db.models import CampaignChapter, Company, S3Asset, User
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.openapi.tags import APITags

from . import docs
from .base import BaseAssetsController


class ChapterAssetsController(BaseAssetsController):
    """Chapter assets controller."""

    tags = [APITags.CAMPAIGN_CHAPTER_ASSETS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_user_by_id_and_company),
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
            S3AssetType | None, Parameter(description="Filter assets by type.")
        ] = None,
    ) -> OffsetPagination[S3Asset]:
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
    async def get_chapter_asset(self, chapter: CampaignChapter, asset: S3Asset) -> S3Asset:
        """Get a chapter asset."""
        return await self._get_asset(asset, parent=chapter)

    @post(
        path=urls.Campaigns.CHAPTER_ASSET_UPLOAD,
        summary="Upload a chapter asset",
        operation_id="uploadChapterAsset",
        description=docs.UPLOAD_ASSET_DESCRIPTION,
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def handle_file_upload(
        self,
        company: Company,
        chapter: CampaignChapter,
        user: User,
        data: Annotated[UploadFile, Body(media_type=RequestEncodingType.MULTI_PART)],
    ) -> S3Asset:
        """Upload a chapter asset."""
        return await self._create_asset(
            parent=chapter,
            company_id=company.id,
            upload_user_id=user.id,
            data=data,
        )

    @delete(
        path=urls.Campaigns.CHAPTER_ASSET_DELETE,
        summary="Delete a chapter asset",
        operation_id="deleteChapterAsset",
        description=docs.DELETE_ASSET_DESCRIPTION,
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def delete_chapter_asset(self, asset: S3Asset) -> None:
        """Delete a chapter asset."""
        await self._delete_asset(asset=asset)
