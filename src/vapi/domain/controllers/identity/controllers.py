"""Identity resolution controllers."""

from litestar import Request, delete, post
from litestar.controller import Controller
from litestar.di import Provide
from litestar.status_codes import HTTP_200_OK

from vapi.config import settings
from vapi.constants import AuditOperation, IdentityProvider, UserRole
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.developer import Developer
from vapi.db.sql_models.user import User
from vapi.domain import deps, hooks, urls
from vapi.domain.controllers.identity import docs
from vapi.domain.controllers.identity.dto import (
    IdentifyRequest,
    IdentifyResponse,
    LinkIdentityRequest,
)
from vapi.domain.controllers.user.dto import UserResponse
from vapi.domain.controllers.user.helpers import annotated_user_response
from vapi.domain.services.identity_svc import (
    PROVIDER_PROFILE_FIELDS,
    IdentityResolution,
    IdentityService,
)
from vapi.lib.exceptions import PermissionDeniedError
from vapi.lib.guards import developer_company_user_guard, user_active_guard
from vapi.lib.rate_limit_policies import USER_REGISTRATION_LIMIT
from vapi.openapi.tags import APITags
from vapi.utils.identity import verify_provider_token


def _require_self_or_admin(*, acting_user: User, target_user: User, action: str) -> None:
    """Guard identity mutations to the user themselves or a company admin.

    Args:
        acting_user: The user the request is acting on behalf of.
        target_user: The user whose identities are being changed.
        action: Verb used in the error message (e.g. "link", "unlink").

    Raises:
        PermissionDeniedError: The acting user is neither the target nor an admin.
    """
    if acting_user.id != target_user.id and acting_user.role != UserRole.ADMIN:
        raise PermissionDeniedError(
            detail=f"Only the user themselves or an admin can {action} identities"
        )


class IdentityController(Controller):
    """Identity resolution controller."""

    tags = [APITags.USERS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "target_user": Provide(deps.provide_target_user),
        "acting_user": Provide(deps.provide_acting_user),
        "developer": Provide(deps.provide_developer_from_request),
    }
    guards = [developer_company_user_guard, user_active_guard]

    @post(
        path=urls.Identity.IDENTIFY,
        status_code=HTTP_200_OK,
        summary="Identify user",
        operation_id="identifyUser",
        description=docs.IDENTIFY_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
        opt={"rate_limits": [USER_REGISTRATION_LIMIT], "allow_unapproved_user": True},
    )
    async def identify(
        self, request: Request, data: IdentifyRequest, company: Company, developer: Developer
    ) -> IdentifyResponse:
        """Resolve a verified provider login to a canonical user.

        Verifies the provider credential, then resolves the user by matching
        on provider ID, auto-linking by verified email, or creating a new
        UNAPPROVED user. Returns the resolution path and full user payload.
        """
        provider = data.provider
        store = request.app.stores.get(settings.stores.jwks_key)
        additional = (developer.provider_audiences or {}).get(provider.value, [])
        identity = await verify_provider_token(
            provider=provider,
            token=data.token,
            store=store,
            additional_audiences=additional,
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
        # Record whether the identity was newly created or matched/linked so the
        # audit log accurately reflects the operation rather than always defaulting
        # to CREATE from the HTTP POST method.
        request.state.audit_operation = (
            AuditOperation.CREATE
            if resolution is IdentityResolution.CREATED
            else AuditOperation.UPDATE
        )
        return IdentifyResponse(
            resolution=resolution,
            user=await annotated_user_response(user.id),
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
        developer: Developer,
    ) -> UserResponse:
        """Attach an additional verified provider identity to a user.

        Only the user themselves or a company admin may link identities.
        Verifies the provider credential before saving the profile.
        """
        _require_self_or_admin(acting_user=acting_user, target_user=target_user, action="link")

        provider = data.provider
        store = request.app.stores.get(settings.stores.jwks_key)
        additional = (developer.provider_audiences or {}).get(provider.value, [])
        identity = await verify_provider_token(
            provider=provider,
            token=data.token,
            store=store,
            additional_audiences=additional,
        )

        profile_field = PROVIDER_PROFILE_FIELDS[provider]
        old_profile = getattr(target_user, profile_field)

        service = IdentityService()
        user = await service.link_identity(company=company, user=target_user, identity=identity)
        request.state.audit_description = (
            f"Link {provider.value} identity to user '{user.username}'"
        )
        request.state.audit_changes = {profile_field: {"old": old_profile, "new": identity.profile}}
        return await annotated_user_response(user.id)

    @delete(
        path=urls.Identity.UNLINK,
        status_code=HTTP_200_OK,
        summary="Unlink identity",
        operation_id="unlinkUserIdentity",
        description=docs.UNLINK_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def unlink_identity(
        self,
        request: Request,
        provider: IdentityProvider,
        target_user: User,
        acting_user: User,
    ) -> UserResponse:
        """Remove a linked provider identity from a user.

        Only the user themselves or a company admin may unlink identities. The
        user's final identity is protected to keep the account authenticable.
        """
        _require_self_or_admin(acting_user=acting_user, target_user=target_user, action="unlink")

        profile_field = PROVIDER_PROFILE_FIELDS[provider]
        old_profile = getattr(target_user, profile_field)

        service = IdentityService()
        user = await service.unlink_identity(user=target_user, provider=provider)
        request.state.audit_description = (
            f"Unlink {provider.value} identity from user '{user.username}'"
        )
        request.state.audit_changes = {profile_field: {"old": old_profile, "new": None}}
        # Unlinking clears a field on the existing user; record UPDATE rather than
        # the DELETE the HTTP method would otherwise imply (the user row persists).
        request.state.audit_operation = AuditOperation.UPDATE
        return await annotated_user_response(user.id)
