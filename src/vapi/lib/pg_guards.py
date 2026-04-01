"""Tortoise-based guards for migrated controllers.

Parallel to guards.py (Beanie-based) during the migration. Once all domains
are migrated (Session 11), delete guards.py and rename this file.

Note: connection.user is still a Beanie Developer (set by auth middleware).
These guards only read .id and .is_global_admin from it.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from vapi.constants import CompanyPermission
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.developer import DeveloperCompanyPermission
from vapi.lib.exceptions import NotFoundError, PermissionDeniedError, ValidationError

if TYPE_CHECKING:
    from litestar.connection import ASGIConnection
    from litestar.handlers.base import BaseRouteHandler

__all__ = (
    "pg_developer_company_admin_guard",
    "pg_developer_company_owner_guard",
    "pg_developer_company_user_guard",
)


async def _pg_is_valid_company(company_id: str) -> Company:
    """Check if a company is valid via Tortoise."""
    if not company_id:
        raise ValidationError(
            detail="Company ID is required",
            invalid_parameters=[{"field": "company_id", "message": "Company ID is required"}],
        )
    company = await Company.filter(id=UUID(company_id), is_archived=False).first()
    if not company:
        raise NotFoundError(detail=f"Company '{company_id}' not found")
    return company


async def _pg_check_developer_company_permission(
    connection: "ASGIConnection",
    *,
    allowed_permissions: set[CompanyPermission] | None = None,
) -> None:
    """Verify the developer has the required permission via Tortoise."""
    developer = connection.user
    if developer.is_global_admin:
        return

    await _pg_is_valid_company(connection.path_params.get("company_id"))

    perm = await DeveloperCompanyPermission.filter(
        developer_id=developer.id,
        company_id=UUID(connection.path_params.get("company_id")),
    ).first()

    if perm and (allowed_permissions is None or perm.permission in allowed_permissions):
        return

    raise PermissionDeniedError(detail="No rights to access this resource")


async def pg_developer_company_user_guard(
    connection: "ASGIConnection", _: "BaseRouteHandler"
) -> None:
    """Guard requiring any company membership (Tortoise)."""
    await _pg_check_developer_company_permission(connection)


async def pg_developer_company_admin_guard(
    connection: "ASGIConnection", _: "BaseRouteHandler"
) -> None:
    """Guard requiring admin or owner permission (Tortoise)."""
    await _pg_check_developer_company_permission(
        connection,
        allowed_permissions={CompanyPermission.ADMIN, CompanyPermission.OWNER},
    )


async def pg_developer_company_owner_guard(
    connection: "ASGIConnection", _: "BaseRouteHandler"
) -> None:
    """Guard requiring owner permission (Tortoise)."""
    await _pg_check_developer_company_permission(
        connection,
        allowed_permissions={CompanyPermission.OWNER},
    )
