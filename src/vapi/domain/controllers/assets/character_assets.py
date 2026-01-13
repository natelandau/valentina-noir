"""Character assets controller."""

from typing import Annotated

from litestar.datastructures import UploadFile
from litestar.di import Provide
from litestar.enums import RequestEncodingType
from litestar.handlers import delete, get, post
from litestar.params import Body, Parameter

from vapi.constants import AssetType
from vapi.db.models import Character, Company, S3Asset, User
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.lib.guards import user_character_player_or_storyteller_guard
from vapi.openapi.tags import APITags

from .base import BaseAssetsController


class CharacterAssetsController(BaseAssetsController):
    """Character assets controller."""

    tags = [APITags.CHARACTERS_ASSETS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_user_by_id_and_company),
        "character": Provide(deps.provide_character_by_id_and_company),
        "asset": Provide(deps.provide_s3_asset_by_id),
    }

    @get(
        path=urls.Characters.ASSETS,
        summary="List character assets",
        operation_id="listCharacterAssets",
        description="List all assets for a character.",
        cache=True,
    )
    async def list_character_assets(
        self,
        character: Character,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        asset_type: Annotated[
            AssetType | None, Parameter(description="Filter assets by type.")
        ] = None,
    ) -> OffsetPagination[S3Asset]:
        """List all character assets."""
        return await self._list_assets(
            parent_id=character.id,
            asset_type=asset_type,
            limit=limit,
            offset=offset,
        )

    @get(
        path=urls.Characters.ASSET_DETAIL,
        summary="Get a character asset",
        operation_id="getCharacterAsset",
        description="Get an asset for a character.",
        cache=True,
    )
    async def get_character_asset(self, character: Character, asset: S3Asset) -> S3Asset:
        """Get a character asset."""
        return await self._get_asset(asset, parent=character)

    @post(
        path=urls.Characters.ASSET_UPLOAD,
        summary="Upload a character asset",
        operation_id="uploadCharacterAsset",
        description="Upload an asset for a character.",
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
        guards=[user_character_player_or_storyteller_guard],
    )
    async def handle_file_upload(
        self,
        company: Company,
        character: Character,
        user: User,
        data: Annotated[UploadFile, Body(media_type=RequestEncodingType.MULTI_PART)],
    ) -> S3Asset:
        """Upload a character asset."""
        return await self._create_asset(
            parent=character,
            company_id=company.id,
            upload_user_id=user.id,
            data=data,
        )

    @delete(
        path=urls.Characters.ASSET_DELETE,
        summary="Delete a character asset",
        operation_id="deleteCharacterAsset",
        description="Delete an asset for a character.",
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def delete_character_asset(self, character: Character, asset: S3Asset) -> None:
        """Delete a character asset."""
        return await self._delete_asset(asset, parent=character)
