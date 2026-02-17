"""Options controllers."""

from __future__ import annotations

import logging
import re

from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import get

from vapi.config import settings
from vapi.constants import (
    AssetParentType,
    AssetType,
    CharacterClass,
    CharacterStatus,
    CharacterType,
    CompanyPermission,
    DiceSize,
    GameVersion,
    HunterCreed,
    HunterEdgeType,
    InventoryItemType,
    PermissionManageCampaign,
    PermissionsFreeTraitChanges,
    PermissionsGrantXP,
    RollResultType,
    SpecialtyType,
    TraitModifyCurrency,
    UserRole,
    WerewolfRenown,
)
from vapi.domain import deps, urls
from vapi.domain.handlers.character_autogeneration.constants import (
    AbilityFocus,
    AutoGenExperienceLevel,
)
from vapi.domain.handlers.character_autogeneration.utils import (
    get_character_class_percentile_lookup_table,
)
from vapi.lib.guards import developer_company_user_guard
from vapi.openapi.tags import APITags

from . import docs

logger = logging.getLogger("vapi")


def _build_url(url: str) -> str:
    # Remove any dynamic parameter types from the URL
    url = re.sub(r":[a-z]+}", "}", url, flags=re.IGNORECASE)

    # Add the base URL to the URL
    return settings.server.url + url


class OptionsController(Controller):
    """Options controller."""

    tags = [APITags.OPTIONS.name]
    dependencies = {"company": Provide(deps.provide_company_by_id)}
    guards = [developer_company_user_guard]

    @get(
        path=urls.Options.LIST,
        summary="Get available options",
        operation_id="getCompanyOptions",
        description=docs.GET_OPTIONS_DESCRIPTION,
        cache=600,
    )
    async def get_company_options(self) -> dict[str, dict[str, list[str | int] | dict[str, str]]]:
        """Get options for a company."""
        return {
            "companies": {
                "CompanyPermission": [x.value for x in CompanyPermission],
                "PermissionManageCampaign": [x.value for x in PermissionManageCampaign],
                "PermissionsGrantXP": [x.value for x in PermissionsGrantXP],
                "PermissionsFreeTraitChanges": [x.value for x in PermissionsFreeTraitChanges],
            },
            "characters": {
                "AbilityFocus": [x.value for x in AbilityFocus],
                "AutoGenExperienceLevel": [x.value for x in AutoGenExperienceLevel],
                "CharacterClass": [x.value for x in CharacterClass],
                "CharacterStatus": [x.value for x in CharacterStatus],
                "CharacterType": [x.value for x in CharacterType],
                "GameVersion": [x.value for x in GameVersion],
                "HunterCreed": [x.value for x in HunterCreed],
                "HunterEdgeType": [x.value for x in HunterEdgeType],
                "InventoryItemType": [x.value for x in InventoryItemType],
                "SpecialtyType": [x.value for x in SpecialtyType],
                "TraitModifyCurrency": [x.value for x in TraitModifyCurrency],
                "WerewolfRenown": [x.value for x in WerewolfRenown],
                "_related": {
                    "concepts": _build_url(urls.CharacterBlueprints.CONCEPTS),
                    "hunter_edges": _build_url(urls.CharacterBlueprints.HUNTER_EDGES),
                    "hunter_edge_perks": _build_url(urls.CharacterBlueprints.HUNTER_EDGE_PERKS),
                    "traits": _build_url(urls.CharacterBlueprints.TRAITS),
                    "trait_sections": _build_url(urls.CharacterBlueprints.SECTIONS),
                    "trait_categories": _build_url(urls.CharacterBlueprints.CATEGORIES),
                    "vampire_clans": _build_url(urls.CharacterBlueprints.VAMPIRE_CLANS),
                    "werewolf_tribes": _build_url(urls.CharacterBlueprints.WEREWOLF_TRIBES),
                    "werewolf_auspices": _build_url(urls.CharacterBlueprints.WEREWOLF_AUSPICES),
                    "werewolf_gifts": _build_url(urls.CharacterBlueprints.WEREWOLF_GIFTS),
                    "vampire_clan_detail": _build_url(urls.CharacterBlueprints.VAMPIRE_CLAN_DETAIL),
                    "werewolf_auspice_detail": _build_url(
                        urls.CharacterBlueprints.WEREWOLF_AUSPICE_DETAIL
                    ),
                    "werewolf_gift_detail": _build_url(
                        urls.CharacterBlueprints.WEREWOLF_GIFT_DETAIL
                    ),
                    "werewolf_rite_detail": _build_url(
                        urls.CharacterBlueprints.WEREWOLF_RITE_DETAIL
                    ),
                    "werewolf_tribe_detail": _build_url(
                        urls.CharacterBlueprints.WEREWOLF_TRIBE_DETAIL
                    ),
                },
            },
            "character_autogeneration": {
                "CharacterClassPercentileChance": [
                    f"{x.value}: {lower_bound}-{upper_bound}"
                    for x, (
                        lower_bound,
                        upper_bound,
                    ) in get_character_class_percentile_lookup_table().items()
                ],
            },
            "users": {
                "UserRole": [x.value for x in UserRole],
            },
            "gameplay": {
                "DiceSize": [x.value for x in DiceSize],
                "RollResultType": [x.value for x in RollResultType],
            },
            "assets": {
                "AssetType": [x.value for x in AssetType],
                "AssetParentType": [x.value for x in AssetParentType],
            },
        }
