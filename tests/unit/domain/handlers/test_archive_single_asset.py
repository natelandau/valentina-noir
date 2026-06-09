"""Tests for archive_single_asset."""

from typing import Any

import pytest

from vapi.db.sql_models.aws import S3Asset
from vapi.domain.handlers.archive_handlers import archive_single_asset

pytestmark = pytest.mark.anyio


async def test_archive_single_asset_sets_archive_fields(
    company_factory: Any,
    user_factory: Any,
    s3asset_factory: Any,
) -> None:
    """Verify archiving one asset sets is_archived, archive_date, and batch id."""
    # Given an active S3 asset
    company = await company_factory()
    uploader = await user_factory(company=company)
    asset = await s3asset_factory(company=company, uploaded_by=uploader)

    # When archiving it as a single unit
    ctx = await archive_single_asset(asset)

    # Then the row is archived with a date and batch id matching the context
    refreshed = await S3Asset.filter(id=asset.id).first()
    assert refreshed is not None
    assert refreshed.is_archived is True
    assert refreshed.archive_date == ctx.now
    assert refreshed.archive_batch_id == ctx.batch_id
