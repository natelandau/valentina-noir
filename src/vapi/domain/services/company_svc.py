"""Company service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from beanie.operators import ElemMatch, In

from vapi.constants import CompanyPermission
from vapi.db.models import Company
from vapi.db.models.developer import CompanyPermissions, Developer
from vapi.lib.exceptions import PermissionDeniedError, ValidationError

from .validation_svc import GetModelByIdValidationService

if TYPE_CHECKING:
    from beanie import PydanticObjectId


class CompanyService:
    """Company service."""

    def _is_company_in_developer_companies(
        self, developer: Developer, company_id: PydanticObjectId
    ) -> bool:
        """Check if a company is in a developer's companies.

        Args:
            developer: The developer to check.
            company_id: The ID of the company to check.

        Returns:
            True if the company is in the developer's companies, False otherwise.
        """
        return any(x.company_id == company_id for x in developer.companies)

    async def _get_all_company_owners(self, company_id: PydanticObjectId) -> list[Developer]:
        """Get the owners of a company."""
        return await Developer.find(
            Developer.is_global_admin == False,
            Developer.is_archived == False,
            ElemMatch(
                Developer.companies,
                {
                    "company_id": company_id,
                    "permission": CompanyPermission.OWNER,
                },
            ),
        ).to_list()

    def _get_company_perms_from_developer(
        self, developer: Developer, company_id: PydanticObjectId
    ) -> CompanyPermissions | None:
        """Get a company from a developer's companies.

        Args:
            developer: The developer to check.
            company_id: The ID of the company to check.

        Returns:
            The company permissions if the company is in the developer's companies, None otherwise.
        """
        if self._is_company_in_developer_companies(developer=developer, company_id=company_id):
            return next(filter(lambda x: x.company_id == company_id, developer.companies), None)

        return None

    def can_developer_access_company(
        self,
        developer: Developer,
        company_id: PydanticObjectId,
        minimum_permission: CompanyPermission = CompanyPermission.USER,
    ) -> bool:
        """Check if a developer can take an action on a company. Global admins are always allowed.

        Args:
            developer: The developer to check.
            company_id: The ID of the company to check.
            minimum_permission: The minimum permission required to access the company.

        Returns:
            True if the developer can take the action on the company, False otherwise.

        Raises:
            PermissionDeniedError: If the developer does not have the minimum permission to access the company.
        """
        if developer.is_global_admin:
            return True

        permissions = self._get_company_perms_from_developer(
            developer=developer, company_id=company_id
        )
        if not permissions or permissions.permission == CompanyPermission.REVOKE:
            msg = "You are not authorized to take this action on this company."
            raise PermissionDeniedError(detail=msg)

        permission_map = {
            CompanyPermission.USER: 1,
            CompanyPermission.ADMIN: 2,
            CompanyPermission.OWNER: 3,
        }
        if permission_map[permissions.permission] < permission_map[minimum_permission]:
            msg = "You are not authorized to take this action on this company."
            raise PermissionDeniedError(detail=msg)

        return True

    async def list_companies(
        self, requesting_developer: Developer, limit: int = 10, offset: int = 0
    ) -> tuple[int, list[Company]]:
        """List all companies.

        Args:
            requesting_developer: The developer to list companies for.
            limit: The limit of companies to return.
            offset: The offset of the companies to return.

        Returns:
            A tuple containing the count of companies and the list of companies.
        """
        filters = [Company.is_archived == False]

        if not requesting_developer.is_global_admin:
            company_ids = [x.company_id for x in requesting_developer.companies]
            filters.append(In(Company.id, company_ids))  # type: ignore [arg-type]

        count = await Company.find(*filters).count()
        companies = await Company.find(*filters).sort("name").skip(offset).limit(limit).to_list()
        return count, companies

    async def control_company_permissions(
        self,
        requesting_developer: Developer,
        company: Company,
        target_developer_id: PydanticObjectId,
        new_permission: CompanyPermission,
    ) -> CompanyPermissions | None:
        """Control company permissions."""
        self.can_developer_access_company(
            developer=requesting_developer,
            company_id=company.id,
            minimum_permission=CompanyPermission.OWNER,
        )

        target_developer = await GetModelByIdValidationService().get_developer_by_id(
            target_developer_id
        )
        existing_permissions = self._get_company_perms_from_developer(
            developer=target_developer, company_id=company.id
        )

        # Be idempotent
        if existing_permissions and existing_permissions.permission == new_permission:
            return existing_permissions

        # Every company must have at least one owner.
        if existing_permissions and existing_permissions.permission == CompanyPermission.OWNER:
            num_owners = len(await self._get_all_company_owners(company_id=company.id))
            if num_owners < 2:  # noqa: PLR2004
                raise ValidationError(detail="Every company must have at least one owner.")

        if new_permission == CompanyPermission.REVOKE and existing_permissions:
            target_developer.companies = [
                x for x in target_developer.companies if x.company_id != company.id
            ]
            await target_developer.save()
            return CompanyPermissions(
                company_id=company.id, name=company.name, permission=CompanyPermission.REVOKE
            )

        if existing_permissions:
            existing_permissions.permission = new_permission
            await target_developer.save()
            return existing_permissions

        company_permissions = CompanyPermissions(
            company_id=company.id, name=company.name, permission=new_permission
        )
        target_developer.companies.append(company_permissions)
        await target_developer.save()
        return company_permissions
