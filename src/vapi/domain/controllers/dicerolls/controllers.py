"""Gameplay controllers."""

from typing import Annotated
from uuid import UUID

from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import get, post
from litestar.params import Parameter

from vapi.db.sql_models.company import Company
from vapi.db.sql_models.diceroll import DiceRoll
from vapi.db.sql_models.user import User
from vapi.domain import deps, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import DiceRollService
from vapi.lib.exceptions import NotFoundError
from vapi.lib.guards import developer_company_user_guard, user_active_guard
from vapi.openapi.tags import APITags

from . import docs, dto


class DiceRollController(Controller):
    """Dice roll controller."""

    tags = [APITags.GAMEPLAY.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_target_user),
    }
    guards = [developer_company_user_guard, user_active_guard]

    @get(
        path=urls.DiceRolls.LIST,
        summary="List dice rolls",
        operation_id="listDiceRolls",
        description=docs.LIST_DICEROLLS_DESCRIPTION,
    )
    async def list_dicerolls(
        self,
        company: Company,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        userid: Annotated[
            UUID | None, Parameter(description="Show dice rolls for this user.")
        ] = None,
        characterid: Annotated[
            UUID | None, Parameter(description="Show dice rolls for this character.")
        ] = None,
        campaignid: Annotated[
            UUID | None, Parameter(description="Show dice rolls for this campaign.")
        ] = None,
    ) -> OffsetPagination[dto.DiceRollResponse]:
        """List all dice rolls."""
        filters: dict = {"company_id": company.id, "is_archived": False}
        if userid:
            filters["user_id"] = userid
        if characterid:
            filters["character_id"] = characterid
        if campaignid:
            filters["campaign_id"] = campaignid

        qs = DiceRoll.filter(**filters)
        count = await qs.count()
        dice_rolls = await qs.offset(offset).limit(limit).prefetch_related("roll_result", "traits")
        return OffsetPagination(
            items=[dto.DiceRollResponse.from_model(dr) for dr in dice_rolls],
            limit=limit,
            offset=offset,
            total=count,
        )

    @get(
        path=urls.DiceRolls.DETAIL,
        summary="Get dice roll",
        operation_id="getDiceRoll",
        description=docs.GET_DICEROLL_DESCRIPTION,
    )
    async def get_diceroll(self, company: Company, diceroll_id: UUID) -> dto.DiceRollResponse:
        """Get a dice roll by ID."""
        dice_roll = (
            await DiceRoll.filter(
                id=diceroll_id,
                is_archived=False,
                company_id=company.id,
            )
            .prefetch_related("roll_result", "traits")
            .first()
        )
        if not dice_roll:
            raise NotFoundError(detail=f"Dice roll {diceroll_id} not found")
        return dto.DiceRollResponse.from_model(dice_roll)

    @post(
        path=urls.DiceRolls.CREATE,
        operation_id="createDiceRoll",
        cache=False,
        summary="Roll dice",
        description=docs.CREATE_DICEROLL_DESCRIPTION,
    )
    async def create_diceroll(
        self, company: Company, user: User, data: dto.DiceRollCreate
    ) -> dto.DiceRollResponse:
        """Create a dice roll."""
        service = DiceRollService()
        dice_roll = await service.create_complete_dice_roll(
            data=data, company_id=company.id, user_id=user.id
        )
        return dto.DiceRollResponse.from_model(dice_roll)

    @post(
        path=urls.DiceRolls.QUICKROLL,
        operation_id="createQuickRoll",
        cache=False,
        summary="Execute quick roll",
        description=docs.QUICKROLL_DESCRIPTION,
    )
    async def create_from_quickroll(
        self,
        company: Company,
        user: User,
        data: dto.QuickRollRequest,
    ) -> dto.DiceRollResponse:
        """Create a dice roll from a quick roll."""
        service = DiceRollService()
        dice_roll = await service.roll_quickroll(company=company, user=user, data=data)
        return dto.DiceRollResponse.from_model(dice_roll)
