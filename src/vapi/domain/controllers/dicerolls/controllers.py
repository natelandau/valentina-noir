"""Gameplay controllers."""

from __future__ import annotations

from typing import Annotated

from beanie import PydanticObjectId  # noqa: TC002
from litestar.controller import Controller
from litestar.di import Provide
from litestar.dto import DTOData  # noqa: TC002
from litestar.handlers import get, post
from litestar.params import Parameter

from vapi.db.models import Company, DiceRoll, User
from vapi.domain import deps, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import DiceRollService
from vapi.lib.exceptions import NotFoundError
from vapi.lib.guards import developer_company_user_guard
from vapi.openapi.tags import APITags

from . import dto


class DiceRollController(Controller):
    """Dice roll controller."""

    tags = [APITags.GAMEPLAY.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_user_by_id_and_company),
    }
    guards = [developer_company_user_guard]
    return_dto = dto.ReturnDTO

    @get(
        path=urls.DiceRolls.LIST,
        summary="List dice rolls",
        operation_id="listDiceRolls",
        description="Retrieve a paginated list of dice roll records. Filter by user, character, or campaign to view specific roll history.",
    )
    async def list_dicerolls(
        self,
        company: Company,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        userid: Annotated[PydanticObjectId, Parameter(description="Show dice rolls for this user.")]
        | None = None,
        characterid: Annotated[
            PydanticObjectId, Parameter(description="Show dice rolls for this character.")
        ]
        | None = None,
        campaignid: Annotated[
            PydanticObjectId, Parameter(description="Show dice rolls for this campaign.")
        ]
        | None = None,
    ) -> OffsetPagination[DiceRoll]:
        """List all dice rolls."""
        query = {"company_id": company.id, "is_archived": False}
        if userid:
            query["user_id"] = userid
        if characterid:
            query["character_id"] = characterid
        if campaignid:
            query["campaign_id"] = campaignid
        count = await DiceRoll.find(query).count()
        dice_rolls = await DiceRoll.find(query).skip(offset).limit(limit).to_list()
        return OffsetPagination(items=dice_rolls, limit=limit, offset=offset, total=count)

    @get(
        path=urls.DiceRolls.DETAIL,
        summary="Get dice roll",
        operation_id="getDiceRoll",
        description="Retrieve details of a specific dice roll including the result, dice pool, and difficulty.",
    )
    async def get_diceroll(self, company: Company, diceroll_id: PydanticObjectId) -> DiceRoll:
        """Get a dice roll by ID."""
        dice_roll = await DiceRoll.find_one(
            DiceRoll.id == diceroll_id,
            DiceRoll.is_archived == False,
            DiceRoll.company_id == company.id,
        )
        if not dice_roll:
            raise NotFoundError(detail=f"Dice roll {diceroll_id} not found")
        return dice_roll

    @post(
        path=urls.DiceRolls.CREATE,
        operation_id="createDiceRoll",
        dto=dto.PostDTO,
        cache=False,
        summary="Roll dice",
        description="Execute a dice roll with the specified pool size, difficulty, and optional desperation dice. Optionally associate the roll with a character and campaign.",
    )
    async def create_diceroll(
        self, company: Company, user: User, data: DTOData[DiceRoll]
    ) -> DiceRoll:
        """Create a dice roll."""
        dice_roll_data = data.create_instance(company_id=company.id, user_id=user.id)

        service = DiceRollService()
        return await service.create_complete_dice_roll(dice_roll_data)

    @post(
        path=urls.DiceRolls.QUICKROLL,
        operation_id="createQuickRoll",
        cache=False,
        summary="Execute quick roll",
        description="Roll dice using a saved quick roll configuration. The dice pool is calculated from the character's trait values for the traits defined in the quick roll.",
    )
    async def create_quickroll(
        self,
        company: Company,
        user: User,
        data: dto.QuickRollDTO,
    ) -> DiceRoll:
        """Create a quick roll."""
        service = DiceRollService()
        return await service.roll_quickroll(company=company, user=user, data=data)
