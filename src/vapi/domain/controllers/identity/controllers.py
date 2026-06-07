"""Identity resolution controllers."""

from litestar import Request, post
from litestar.controller import Controller
from litestar.di import Provide
from litestar.status_codes import HTTP_200_OK

from vapi.config import settings
from vapi.constants import IdentityProvider, UserRole
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.user import User
from vapi.domain import deps, hooks, urls
from vapi.domain.controllers.identity import docs
from vapi.domain.controllers.identity.dto import (
    IdentifyRequest,
    IdentifyResponse,
    LinkIdentityRequest,
)
from vapi.domain.controllers.user.dto import UserResponse
from vapi.domain.services.identity_svc import IdentityService
from vapi.lib.exceptions import PermissionDeniedError, ValidationError
from vapi.lib.guards import developer_company_user_guard, user_active_guard
from vapi.lib.rate_limit_policies import USER_REGISTRATION_LIMIT
from vapi.openapi.tags import APITags
from vapi.utils.identity import verify_provider_token


def _parse_provider(value: str) -> IdentityProvider:
    """Validate and convert the provider name from the request body.

    Raises ValidationError with a 400 status so callers get a structured
    problem-details response rather than an unhandled ValueError.
    """
    try:
        return IdentityProvider(value)
    except ValueError as e:
        raise ValidationError(
            detail=f"Unknown identity provider '{value}'",
            invalid_parameters=[
                {
                    "field": "provider",
                    "message": "Must be one of: apple, google, discord, github",
                },
            ],
        ) from e


class IdentityController(Controller):
    """Identity resolution controller."""

    tags = [APITags.USERS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "target_user": Provide(deps.provide_target_user),
        "acting_user": Provide(deps.provide_acting_user),
    }
    guards = [developer_company_user_guard, user_active_guard]

    @post(
        path=urls.Identity.IDENTIFY,
        status_code=HTTP_200_OK,
        summary="Identify user",
        operation_id="identifyUser",
        description=docs.IDENTIFY_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
        opt={"rate_limits": [USER_REGISTRATION_LIMIT]},
    )
    async def identify(
        self, request: Request, data: IdentifyRequest, company: Company
    ) -> IdentifyResponse:
        """Resolve a verified provider login to a canonical user.

        Verifies the provider credential, then resolves the user by matching
        on provider ID, auto-linking by verified email, or creating a new
        UNAPPROVED user. Returns the resolution path and full user payload.
        """
        provider = _parse_provider(data.provider)
        store = request.app.stores.get(settings.stores.jwks_key)
        identity = await verify_provider_token(
            provider=provider,
            token=data.token,
            store=store,
        )

        service = IdentityService()
        user, resolution = await service.resolve(
            company=company,
            identity=identity,
            username=data.username,
            fallback_email=data.email,
        )
        request.state.audit_description = (
            f"Identify user '{user.username}' via {provider.value} ({resolution.value})"
        )
        request.state.audit_redact_fields = ["token"]
        return IdentifyResponse(
            resolution=resolution,
            user=UserResponse.from_model(user),
        )

    @post(
        path=urls.Identity.LINK,
        status_code=HTTP_200_OK,
        summary="Link identity",
        operation_id="linkUserIdentity",
        description=docs.LINK_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def link_identity(
        self,
        request: Request,
        data: LinkIdentityRequest,
        company: Company,
        target_user: User,
        acting_user: User,
    ) -> UserResponse:
        """Attach an additional verified provider identity to a user.

        Only the user themselves or a company admin may link identities.
        Verifies the provider credential before saving the profile.
        """
        if acting_user.id != target_user.id and acting_user.role != UserRole.ADMIN:
            raise PermissionDeniedError(
                detail="Only the user themselves or an admin can link identities"
            )

        provider = _parse_provider(data.provider)
        store = request.app.stores.get(settings.stores.jwks_key)
        identity = await verify_provider_token(provider=provider, token=data.token, store=store)

        profile_field = f"{provider.value}_profile"
        old_profile = getattr(target_user, profile_field)

        service = IdentityService()
        user = await service.link_identity(company=company, user=target_user, identity=identity)
        request.state.audit_description = (
            f"Link {provider.value} identity to user '{user.username}'"
        )
        request.state.audit_changes = {profile_field: {"old": old_profile, "new": identity.profile}}
        request.state.audit_redact_fields = ["token"]
        return UserResponse.from_model(user)
