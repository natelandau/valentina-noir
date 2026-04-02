"""Book assets controller."""

from typing import Annotated

from litestar.datastructures import UploadFile
from litestar.di import Provide
from litestar.enums import RequestEncodingType
from litestar.handlers import delete, get, post
from litestar.params import Body, Parameter

from vapi.constants import AssetType
from vapi.db.sql_models.aws import S3Asset
from vapi.db.sql_models.campaign import CampaignBook
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.user import User
from vapi.domain import hooks, pg_deps, urls
from vapi.domain.controllers.s3_assets import dto
from vapi.domain.paginator import OffsetPagination
from vapi.openapi.tags import APITags

from . import docs
from .base import BaseAssetsController


class BookAssetsController(BaseAssetsController):
    """Book assets controller."""

    parent_fk_field = "book_id"
    tags = [APITags.CAMPAIGN_BOOK_ASSETS.name]
    dependencies = {
        "company": Provide(pg_deps.provide_pg_company_by_id),
        "user": Provide(pg_deps.provide_user_by_id_and_company),
        "campaign": Provide(pg_deps.provide_campaign_by_id),
        "book": Provide(pg_deps.provide_campaign_book_by_id),
        "asset": Provide(pg_deps.provide_s3_asset_by_id),
    }

    @get(
        path=urls.Campaigns.BOOK_ASSETS,
        summary="List book assets",
        operation_id="listBookAssets",
        description=docs.LIST_ASSETS_DESCRIPTION,
        cache=True,
    )
    async def list_book_assets(
        self,
        book: CampaignBook,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        asset_type: Annotated[
            AssetType | None, Parameter(description="Filter assets by type.")
        ] = None,
    ) -> OffsetPagination[dto.S3AssetResponse]:
        """List all book assets."""
        return await self._list_assets(
            parent_id=book.id,
            asset_type=asset_type,
            limit=limit,
            offset=offset,
        )

    @get(
        path=urls.Campaigns.BOOK_ASSET_DETAIL,
        summary="Get a book asset",
        operation_id="getBookAsset",
        description=docs.GET_ASSET_DESCRIPTION,
        cache=True,
    )
    async def get_book_asset(self, book: CampaignBook, asset: S3Asset) -> dto.S3AssetResponse:
        """Get a book asset."""
        return await self._get_asset(asset, parent_id=book.id)

    @post(
        path=urls.Campaigns.BOOK_ASSET_UPLOAD,
        summary="Upload a book asset",
        operation_id="uploadBookAsset",
        description=docs.UPLOAD_ASSET_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def handle_file_upload(
        self,
        company: Company,
        book: CampaignBook,
        user: User,
        data: Annotated[UploadFile, Body(media_type=RequestEncodingType.MULTI_PART)],
    ) -> dto.S3AssetResponse:
        """Upload a book asset."""
        return await self._create_asset(
            parent_id=book.id,
            company_id=company.id,
            upload_user_id=user.id,
            data=data,
        )

    @delete(
        path=urls.Campaigns.BOOK_ASSET_DELETE,
        summary="Delete a book asset",
        operation_id="deleteBookAsset",
        description=docs.DELETE_ASSET_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def delete_book_asset(self, asset: S3Asset) -> None:
        """Delete a book asset."""
        await self._delete_asset(asset=asset)
