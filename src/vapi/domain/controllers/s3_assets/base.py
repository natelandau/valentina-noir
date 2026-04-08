"""Base assets controller."""

from abc import ABC, abstractmethod
from uuid import UUID

from litestar.controller import Controller
from litestar.datastructures import UploadFile

from vapi.constants import AssetType
from vapi.db.sql_models.aws import S3Asset
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import AWSS3Service
from vapi.lib.exceptions import NotFoundError
from vapi.lib.guards import developer_company_user_guard, user_active_guard

from . import dto


class BaseAssetsController(Controller, ABC):
    """Base assets controller."""

    guards = [developer_company_user_guard, user_active_guard]

    @property
    @abstractmethod
    def parent_fk_field(self) -> str:
        """Return the FK field name on S3Asset (e.g., 'character_id')."""
        ...

    async def _list_assets(
        self,
        parent_id: UUID,
        asset_type: AssetType | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> OffsetPagination[dto.S3AssetResponse]:
        """List all assets for a parent entity."""
        filters: dict = {self.parent_fk_field: parent_id, "is_archived": False}
        if asset_type:
            filters["asset_type"] = asset_type

        qs = S3Asset.filter(**filters).order_by("date_created")
        count = await qs.count()
        assets = await qs.offset(offset).limit(limit)
        return OffsetPagination(
            items=[dto.S3AssetResponse.from_model(a) for a in assets],
            limit=limit,
            offset=offset,
            total=count,
        )

    async def _get_asset(self, asset: S3Asset, parent_id: UUID) -> dto.S3AssetResponse:
        """Get an asset, verifying it belongs to the parent."""
        if getattr(asset, self.parent_fk_field) != parent_id:
            raise NotFoundError(detail="Asset not found")
        return dto.S3AssetResponse.from_model(asset)

    async def _create_asset(
        self,
        parent_id: UUID,
        company_id: UUID,
        upload_user_id: UUID,
        data: UploadFile,
    ) -> dto.S3AssetResponse:
        """Create an asset and upload to S3."""
        data_as_bytes = await data.read()
        asset = await AWSS3Service().upload_asset(
            company_id=company_id,
            uploaded_by_id=upload_user_id,
            parent_id=parent_id,
            parent_fk_field=self.parent_fk_field,
            data=data_as_bytes,
            filename=data.filename,
            mime_type=data.content_type,
        )
        return dto.S3AssetResponse.from_model(asset)

    async def _delete_asset(self, asset: S3Asset) -> None:
        """Delete an asset from S3 and the database."""
        await AWSS3Service().delete_asset(asset)
