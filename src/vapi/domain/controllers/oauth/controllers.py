"""OAuth2 controllers."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import unquote_plus

from httpx_oauth.oauth2 import RefreshTokenError
from litestar import get
from litestar.controller import Controller
from litestar.di import Provide
from litestar.response import Redirect

from vapi.config.oauth import get_discord_oauth_client
from vapi.db.models.user import User
from vapi.domain import deps, urls
from vapi.domain.controllers.oauth import lib
from vapi.lib.exceptions import ImproperlyConfiguredError, InternalServerError
from vapi.openapi.tags import APITags
from vapi.server.oauth import AccessTokenState, OAuth2AuthorizeCallback

oauth2_authorize_callback = OAuth2AuthorizeCallback(
    client=get_discord_oauth_client(),
    route_name="discord-callback",
)


class OAuth2Controller(Controller):
    """OAuth2 controller."""

    tags = [APITags.OAUTH.name]
    dependencies = {
        "user": Provide(deps.provide_user_by_id),
    }

    @get(
        path=urls.OAuth.DISCORD_LOGIN_REDIRECT,
        exclude_from_auth=True,
        summary="Redirect to Discord login",
        operation_id="redirectToDiscordLogin",
        description="Initiate the Discord OAuth flow by redirecting the user to Discord's authorization page. Use this for browser-based authentication flows.",
    )
    async def discord_login_redirect(
        self,
        user: User,
    ) -> Redirect | dict[str, Any]:
        """Login via provider."""
        auth_url = await lib.get_discord_oauth_url(user.id)
        return Redirect(path=auth_url, status_code=302)

    @get(
        path=urls.OAuth.DISCORD_LOGIN_URL,
        exclude_from_auth=True,
        summary="Get Discord login URL",
        operation_id="getDiscordLoginUrl",
        description="Retrieve the Discord authorization URL for a user. Use this when you need to handle the redirect manually or display a login button.",
    )
    async def discord_login(
        self,
        user: User,
    ) -> Redirect | dict[str, Any]:
        """Login via provider."""
        auth_url = await lib.get_discord_oauth_url(user.id)

        return {"url": auth_url}

    @get(
        path=urls.OAuth.DISCORD_CALLBACK,
        name="discord-callback",
        dependencies={"access_token_state": Provide(oauth2_authorize_callback, use_cache=False)},
        exclude_from_auth=True,
        include_in_schema=False,
    )
    async def discord_callback(self, access_token_state: AccessTokenState) -> dict[str, Any]:
        """OAuth callback."""
        token, state = access_token_state

        state = json.loads(unquote_plus(state))

        user = await User.get(state["user_id"])
        user = await lib.discord_oauth_token_to_user(user, token)
        user = await lib.discord_profile_to_user(user)
        return {"success": True}

    @get(
        path=urls.OAuth.DISCORD_REFRESH,
        exclude_from_auth=True,
        summary="Refresh Discord connection",
        operation_id="refreshDiscordConnection",
        description="Refresh an expired Discord OAuth token and update the user's Discord profile data. Call this when the token has expired to maintain the Discord integration.",
    )
    async def discord_refresh(self, user: User) -> dict[str, Any]:
        """Refresh the Discord OAuth token."""
        if user.is_discord_oauth_expired():
            try:
                response = await get_discord_oauth_client().refresh_token(
                    user.discord_oauth.refresh_token
                )
            except RefreshTokenError as e:
                raise InternalServerError from e

            user = await lib.discord_oauth_token_to_user(user, response)

        await user.sync()
        if user.discord_oauth.access_token is None:
            raise ImproperlyConfiguredError(
                detail="Discord OAuth token is not set. User must login again."
            )

        user = await lib.discord_profile_to_user(user)
        return {"success": True}
