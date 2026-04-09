"""Cross-company user lookup service."""

from tortoise.expressions import RawSQL

from vapi.constants import CompanyPermission
from vapi.db.sql_models.developer import Developer, DeveloperCompanyPermission
from vapi.db.sql_models.user import User
from vapi.domain.controllers.user_lookup.dto import UserLookupResult
from vapi.lib.exceptions import ValidationError


class UserLookupService:
    """Look up users across multiple companies for a developer."""

    async def lookup(
        self,
        *,
        developer: Developer,
        email: str | None = None,
        discord_id: str | None = None,
        google_id: str | None = None,
        github_id: str | None = None,
    ) -> list[UserLookupResult]:
        """Find users matching an identifier across the developer's permitted companies.

        Exactly one identifier must be provided. Returns one result per matching
        User record, scoped to companies where the developer has non-REVOKE access
        (or all companies if the developer is a global admin).

        Args:
            developer: The requesting developer.
            email: Exact email match.
            discord_id: Match against discord_profile->>'id'.
            google_id: Match against google_profile->>'id'.
            github_id: Match against github_profile->>'id'.

        Raises:
            ValidationError: If zero or more than one identifier is provided.
        """
        identifiers = {
            "email": email,
            "discord_id": discord_id,
            "google_id": google_id,
            "github_id": github_id,
        }
        provided = {k: v for k, v in identifiers.items() if v is not None}

        if len(provided) != 1:
            raise ValidationError(
                detail="Exactly one lookup identifier is required: email, discord_id, google_id, or github_id."
            )

        qs = User.filter(is_archived=False)

        # Scope to developer's permitted companies
        if not developer.is_global_admin:
            permitted_ids = (
                await DeveloperCompanyPermission.filter(
                    developer_id=developer.id,
                )
                .exclude(
                    permission=CompanyPermission.REVOKE,
                )
                .values_list("company_id", flat=True)
            )

            if not permitted_ids:
                return []

            qs = qs.filter(company_id__in=list(permitted_ids))

        identifier_name, identifier_value = next(iter(provided.items()))
        if identifier_name == "email":
            qs = qs.filter(email=identifier_value)
        else:
            oauth_json_fields = {
                "discord_id": "discord_profile",
                "google_id": "google_profile",
                "github_id": "github_profile",
            }
            json_column = oauth_json_fields[identifier_name]
            annotation_key = f"_{identifier_name}"
            qs = qs.annotate(**{annotation_key: RawSQL(f"{json_column}->>'id'")}).filter(
                **{annotation_key: identifier_value}
            )

        users = await qs.select_related("company")

        return [
            UserLookupResult(
                company_id=user.company.id,
                company_name=user.company.name,
                user_id=user.id,
                role=user.role.value,
            )
            for user in users
        ]
