"""Tests for company count annotations (fan-out correctness)."""

import pytest

from vapi.db.sql_models.company import Company
from vapi.domain.services.company_svc import annotate_company_counts

pytestmark = pytest.mark.anyio


async def test_company_counts_no_fanout(company_factory, campaign_factory, user_factory):
    """num_campaigns and num_users stay exact when multiple relations coexist."""
    # Given a company with 2 campaigns AND 2 users (fan-out would multiply them)
    company = await company_factory()
    await campaign_factory(company=company)
    await campaign_factory(company=company)
    await user_factory(company=company)
    await user_factory(company=company)

    # When the counts are annotated
    annotated = await annotate_company_counts(Company.filter(id=company.id)).first()

    # Then each count is exact, not inflated by the cross join
    assert annotated.num_campaigns == 2
    assert annotated.num_users == 2
