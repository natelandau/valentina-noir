"""Company service."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from vapi.constants import CompanyPermission
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.developer import Developer, DeveloperCompanyPermission
from vapi.lib.exceptions import PermissionDeniedError, ValidationError

if TYPE_CHECKING:
    from uuid import UUID

_PERMISSION_RANK: dict[CompanyPermission, int] = {
    CompanyPermission.USER: 1,
    CompanyPermission.ADMIN: 2,
    CompanyPermission.OWNER: 3,
}

_ACCESS_DENIED_MSG = "You are not authorized to take this action on this company."


class CompanyService:
    """Company service."""

    async def _count_company_owners(self, company_id: UUID) -> int:
        """Count non-global-admin, non-archived owners of a company."""
        return await DeveloperCompanyPermission.filter(
            company_id=company_id,
            permission=CompanyPermission.OWNER,
            developer__is_global_admin=False,
            developer__is_archived=False,
        ).count()

    async def _get_developer_permission(
        self, developer_id: UUID, company_id: UUID
    ) -> DeveloperCompanyPermission | None:
        """Find a developer's permission for a specific company."""
        return await DeveloperCompanyPermission.filter(
            developer_id=developer_id, company_id=company_id
        ).first()

    async def can_developer_access_company(
        self,
        developer: Developer,
        company_id: UUID,
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
            PermissionDeniedError: If the developer does not have sufficient permission.
        """
        if developer.is_global_admin:
            return True

        permission = await self._get_developer_permission(
            developer_id=developer.id, company_id=company_id
        )
        if not permission or permission.permission == CompanyPermission.REVOKE:
            raise PermissionDeniedError(detail=_ACCESS_DENIED_MSG)

        if _PERMISSION_RANK[permission.permission] < _PERMISSION_RANK[minimum_permission]:
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
        qs = Company.filter(is_archived=False)

        if not requesting_developer.is_global_admin:
            qs = qs.filter(developer_permissions__developer_id=requesting_developer.id)

        count, companies = await asyncio.gather(
            qs.count(),
            qs.order_by("name").offset(offset).limit(limit).prefetch_related("settings"),
        )
        return count, list(companies)

    async def control_company_permissions(
        self,
        requesting_developer: Developer,
        company: Company,
        target_developer_id: UUID,
        new_permission: CompanyPermission,
    ) -> DeveloperCompanyPermission:
        """Control company permissions.

        Args:
            requesting_developer: The developer requesting the permission change.
            company: The company to update permissions for.
            target_developer_id: The ID of the developer whose permissions will change.
            new_permission: The new permission to assign.

        Returns:
            The updated or created DeveloperCompanyPermission record.

        Raises:
            PermissionDeniedError: If the requesting developer lacks owner access.
            ValidationError: If the target developer is not found or removing the last owner.
        """
        await self.can_developer_access_company(
            developer=requesting_developer,
            company_id=company.id,
            minimum_permission=CompanyPermission.OWNER,
        )

        target_developer = await Developer.filter(id=target_developer_id, is_archived=False).first()
        if not target_developer:
            raise ValidationError(detail=f"Developer {target_developer_id} not found")

        existing = await self._get_developer_permission(
            developer_id=target_developer_id, company_id=company.id
        )

        # Idempotent
        if existing and existing.permission == new_permission:
            await existing.fetch_related("company")
            return existing

        # Guard: cannot demote/revoke the last owner
        if existing and existing.permission == CompanyPermission.OWNER:
            num_owners = await self._count_company_owners(company_id=company.id)
            if num_owners < 2:  # noqa: PLR2004
                raise ValidationError(detail="Every company must have at least one owner.")

        # Revoke
        if new_permission == CompanyPermission.REVOKE and existing:
            await existing.delete()
            return DeveloperCompanyPermission(
                developer=target_developer,
                company=company,
                permission=CompanyPermission.REVOKE,
            )

        # Update
        if existing:
            existing.permission = new_permission
            await existing.save()
            await existing.fetch_related("company")
            return existing

        # Create
        new_perm = await DeveloperCompanyPermission.create(
            developer=target_developer,
            company=company,
            permission=new_permission,
        )
        await new_perm.fetch_related("company")
        return new_perm
