"""Campaign assets controller."""

from typing import Annotated

from litestar.datastructures import UploadFile
from litestar.di import Provide
from litestar.enums import RequestEncodingType
from litestar.handlers import delete, get, post
from litestar.params import Body, Parameter

from vapi.constants import AssetType
from vapi.db.models import Campaign, Company, S3Asset, User
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.openapi.tags import APITags

from . import docs
from .base import BaseAssetsController


class CampaignAssetsController(BaseAssetsController):
    """Campaign assets controller."""

    tags = [APITags.CAMPAIGNS_ASSETS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_user_by_id_and_company),
        "campaign": Provide(deps.provide_campaign_by_id),
        "asset": Provide(deps.provide_s3_asset_by_id),
    }

    @get(
        path=urls.Campaigns.ASSETS,
        summary="List campaign assets",
        operation_id="listCampaignAssets",
        description=docs.LIST_ASSETS_DESCRIPTION,
        cache=True,
    )
    async def list_campaign_assets(
        self,
        campaign: Campaign,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        asset_type: Annotated[
            AssetType | None, Parameter(description="Filter assets by type.")
        ] = None,
    ) -> OffsetPagination[S3Asset]:
        """List all campaign assets."""
        return await self._list_assets(
            parent_id=campaign.id,
            asset_type=asset_type,
            limit=limit,
            offset=offset,
        )

    @get(
        path=urls.Campaigns.ASSET_DETAIL,
        summary="Get a campaign asset",
        operation_id="getCampaignAsset",
        description=docs.GET_ASSET_DESCRIPTION,
        cache=True,
    )
    async def get_campaign_asset(self, campaign: Campaign, asset: S3Asset) -> S3Asset:
        """Get a campaign asset."""
        return await self._get_asset(asset, parent=campaign)

    @post(
        path=urls.Campaigns.ASSET_UPLOAD,
        summary="Upload a campaign asset",
        operation_id="uploadCampaignAsset",
        description=docs.UPLOAD_ASSET_DESCRIPTION,
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def handle_file_upload(
        self,
        company: Company,
        campaign: Campaign,
        user: User,
        data: Annotated[UploadFile, Body(media_type=RequestEncodingType.MULTI_PART)],
    ) -> S3Asset:
        """Upload a campaign asset."""
        return await self._create_asset(
            parent=campaign,
            company_id=company.id,
            upload_user_id=user.id,
            data=data,
        )

    @delete(
        path=urls.Campaigns.ASSET_DELETE,
        summary="Delete a campaign asset",
        operation_id="deleteCampaignAsset",
        description=docs.DELETE_ASSET_DESCRIPTION,
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def delete_campaign_asset(self, asset: S3Asset) -> None:
        """Delete a campaign asset."""
        await self._delete_asset(asset=asset)
