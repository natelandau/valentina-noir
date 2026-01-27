"""Base assets controller."""

from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING

from beanie import PydanticObjectId  # noqa: TC002
from litestar.controller import Controller
from litestar.datastructures import UploadFile  # noqa: TC002

from vapi.db.models import Campaign, CampaignBook, CampaignChapter, Character, S3Asset, User
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import AWSS3Service
from vapi.lib.exceptions import NotFoundError
from vapi.lib.guards import developer_company_user_guard

from . import dto

if TYPE_CHECKING:
    from vapi.constants import AssetType


class BaseAssetsController(Controller, ABC):
    """Base assets controller."""

    guards = [developer_company_user_guard]
    return_dto = dto.AssetResponseDTO

    async def _list_assets(
        self,
        parent_id: PydanticObjectId,
        asset_type: AssetType | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> OffsetPagination[S3Asset]:
        """List all assets for a parent entity.

        Args:
            parent_id: The ID of the parent entity.
            asset_type: The type of assets to filter by.
            limit: The maximum number of assets to return.
            offset: The number of assets to skip.

        Returns:
            OffsetPagination[S3Asset]: The assets.
        """
        filters = [
            S3Asset.parent_id == parent_id,
            S3Asset.is_archived == False,
        ]

        if asset_type:
            filters.append(S3Asset.asset_type == asset_type)

        count = await S3Asset.find(*filters).count()
        assets = (
            await S3Asset.find(*filters).sort("date_created").skip(offset).limit(limit).to_list()
        )
        return OffsetPagination(items=assets, limit=limit, offset=offset, total=count)

    async def _get_asset(
        self, asset: S3Asset, parent: Character | User | Campaign | CampaignBook | CampaignChapter
    ) -> S3Asset:
        """Get an asset by its ID.

        Args:
            asset: The asset to get.
            parent: The parent to check the asset against.

        Returns:
            The asset.
        """
        if asset.parent_id != parent.id:
            raise NotFoundError(detail="Asset not found")
        return asset

    async def _create_asset(
        self,
        parent: Character | User | Campaign | CampaignBook | CampaignChapter,
        company_id: PydanticObjectId,
        upload_user_id: PydanticObjectId,
        data: UploadFile,
    ) -> S3Asset:
        """Create an asset and add it to the parent.

        Args:
            parent: The parent to add the asset to.
            company_id: The ID of the company.
            upload_user_id: The ID of the user uploading the asset.
            data: The data to create the asset with.
        """
        data_as_bytes = await data.read()
        return await AWSS3Service().upload_asset(
            parent=parent,
            company_id=company_id,
            upload_user_id=upload_user_id,
            data=data_as_bytes,
            filename=data.filename,
            mime_type=data.content_type,
        )

    async def _delete_asset(self, asset: S3Asset) -> None:
        """Delete an asset and remove it from the parent.

        Args:
            asset: The asset to delete.

        Returns:
            None.
        """
        service = AWSS3Service()
        await service.delete_asset(asset)
