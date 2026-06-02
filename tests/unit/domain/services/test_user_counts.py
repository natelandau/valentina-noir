"""Tests for user count annotations."""

import pytest

from vapi.db.sql_models.user import User
from vapi.domain.services.user_svc import annotate_user_counts

pytestmark = pytest.mark.anyio


async def test_user_counts_exact_with_fanout(
    company_factory,
    user_factory,
    quickroll_factory,
    note_factory,
    s3asset_factory,
    character_factory,
):
    """Verify user counts stay exact when quickrolls, notes, assets, and characters coexist."""
    # Given a user with 2 quickrolls, 2 notes, 2 owned assets, and 2 played characters
    company = await company_factory()
    user = await user_factory(company=company)
    uploader = await user_factory(company=company)
    await quickroll_factory(user=user)
    await quickroll_factory(user=user)
    await note_factory(company=company, user=user)
    await note_factory(company=company, user=user)
    await s3asset_factory(company=company, user_parent=user, uploaded_by=uploader)
    await s3asset_factory(company=company, user_parent=user, uploaded_by=uploader)
    await character_factory(company=company, user_player=user)
    await character_factory(company=company, user_player=user)

    # When the user counts are annotated
    annotated = await annotate_user_counts(User.filter(id=user.id)).first()

    # Then every count is exact
    assert annotated.num_quickrolls == 2
    assert annotated.num_notes == 2
    assert annotated.num_assets == 2
    assert annotated.num_characters == 2
