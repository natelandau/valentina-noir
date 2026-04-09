"""User lookup controller."""

from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import get

from vapi.db.sql_models.developer import Developer
from vapi.domain import deps, urls
from vapi.domain.services import UserLookupService
from vapi.openapi.tags import APITags

from . import docs
from .dto import UserLookupResult


class UserLookupController(Controller):
    """Cross-company user lookup."""

    tags = [APITags.USERS_LOOKUP.name]
    dependencies = {"developer": Provide(deps.provide_developer_from_request)}

    @get(
        path=urls.UserLookup.LOOKUP,
        summary="Look up a user across companies",
        operation_id="lookupUser",
        description=docs.LOOKUP_DESCRIPTION,
    )
    async def lookup(
        self,
        *,
        developer: Developer,
        email: str | None = None,
        discord_id: str | None = None,
        google_id: str | None = None,
        github_id: str | None = None,
    ) -> list[UserLookupResult]:
        """Look up a user by identifier across the developer's permitted companies."""
        return await UserLookupService().lookup(
            developer=developer,
            email=email,
            discord_id=discord_id,
            google_id=google_id,
            github_id=github_id,
        )
