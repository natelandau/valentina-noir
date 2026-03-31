"""Company service."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from beanie.operators import ElemMatch, In

from vapi.constants import CompanyPermission
from vapi.db.models import Company
from vapi.db.models.developer import CompanyPermissions, Developer
from vapi.lib.exceptions import PermissionDeniedError, ValidationError

from .validation_svc import GetModelByIdValidationService

if TYPE_CHECKING:
    from beanie import PydanticObjectId

_PERMISSION_RANK: dict[CompanyPermission, int] = {
    CompanyPermission.USER: 1,
    CompanyPermission.ADMIN: 2,
    CompanyPermission.OWNER: 3,
}

_ACCESS_DENIED_MSG = "You are not authorized to take this action on this company."


class CompanyService:
    """Company service."""

    async def _count_company_owners(self, company_id: PydanticObjectId) -> int:
        """Count the owners of a company."""
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
        ).count()

    @staticmethod
    def _get_company_perms_from_developer(
        developer: Developer, company_id: PydanticObjectId
    ) -> CompanyPermissions | None:
        """Find a developer's permissions for a specific company.

        Args:
            developer: The developer to check.
            company_id: The ID of the company to check.

        Returns:
            The company permissions if found, None otherwise.
        """
        return next(
            (x for x in developer.companies if x.company_id == company_id),
            None,
        )

    def can_developer_access_company(
        self,
        developer: Developer,
        company_id: PydanticObjectId,
        minimum_permission: CompanyPermission = CompanyPermission.USER,
    ) -> bool:
        """Verify a developer has sufficient permission for a company action.

        Global admins bypass all permission checks.

        Args:
            developer: The developer to check.
            company_id: The ID of the company to check.
            minimum_permission: The minimum permission required to access the company.

        Returns:
            True if the developer can take the action on the company.

        Raises:
            PermissionDeniedError: If the developer does not have the minimum permission.
        """
        if developer.is_global_admin:
            return True

        permissions = self._get_company_perms_from_developer(
            developer=developer, company_id=company_id
        )
        if not permissions or permissions.permission == CompanyPermission.REVOKE:
            raise PermissionDeniedError(detail=_ACCESS_DENIED_MSG)

        if _PERMISSION_RANK[permissions.permission] < _PERMISSION_RANK[minimum_permission]:
            raise PermissionDeniedError(detail=_ACCESS_DENIED_MSG)

        return True

    async def list_companies(
        self, requesting_developer: Developer, limit: int = 10, offset: int = 0
    ) -> tuple[int, list[Company]]:
        """List all companies visible to the requesting developer.

        Args:
            requesting_developer: The developer to list companies for.
            limit: The maximum number of companies to return.
            offset: The number of companies to skip.

        Returns:
            A tuple of (total count, paginated companies).
        """
        filters = [Company.is_archived == False]

        if not requesting_developer.is_global_admin:
            company_ids = [x.company_id for x in requesting_developer.companies]
            filters.append(In(Company.id, company_ids))  # type: ignore [arg-type]

        query = Company.find(*filters)
        count, companies = await asyncio.gather(
            query.count(),
            query.sort("name").skip(offset).limit(limit).to_list(),
        )
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

        if existing_permissions and existing_permissions.permission == new_permission:
            return existing_permissions

        if existing_permissions and existing_permissions.permission == CompanyPermission.OWNER:
            num_owners = await self._count_company_owners(company_id=company.id)
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
