"""Integration smoke test for dev-data population generators."""

import pytest
from scripts.dev_data.config import PopulateConfig
from scripts.dev_data.generators import populate_data

from vapi.constants import AssetType, CharacterClass, CharacterType, CompanyPermission, UserRole
from vapi.db.sql_models.aws import S3Asset
from vapi.db.sql_models.campaign import Campaign, CampaignBook
from vapi.db.sql_models.character import Character, CharacterInventory
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.developer import Developer, DeveloperCompanyPermission
from vapi.db.sql_models.diceroll import DiceRoll, DiceRollResult
from vapi.db.sql_models.notes import Note
from vapi.db.sql_models.quickroll import QuickRoll
from vapi.db.sql_models.user import User

pytestmark = pytest.mark.anyio


class TestPopulateData:
    """The generators produce believable, varied, fully-linked data."""

    async def test_populate_data_generates_full_dataset(self) -> None:  # noqa: PLR0915
        # Given: a small but coverage-guaranteeing config. notes_per_target floor is 1 so
        # the per-target note assertions below are deterministic (default floor is 0).
        cfg = PopulateConfig(
            num_companies=1,
            num_users=3,
            num_campaigns=1,
            num_characters=4,
            notes_per_target=(1, 3),
            inventory_per_char=(1, 3),
            quick_rolls_per_user=(1, 3),
        )

        # Baseline counts: under the parallel suite this test shares a worker database
        # where session-scoped fixtures (company, user, campaign, book, developer) are
        # preserved across per-test cleanup, so assert on deltas, not absolute counts.
        company_ids_before = {str(c.id) for c in await Company.all()}
        companies_before = len(company_ids_before)
        users_before = await User.all().count()
        campaigns_before = await Campaign.all().count()
        books_before = await CampaignBook.all().count()
        characters_before = await Character.all().count()
        global_admins_before = await Developer.filter(is_global_admin=True).count()
        non_global_before = await Developer.filter(is_global_admin=False).count()

        # When: running the generators against the seeded test database
        developers = await populate_data(cfg)

        # Then: the three developer tiers exist and are returned
        assert len(developers) == 3
        assert sum(1 for d in developers if d.is_global_admin) == 1
        assert await Developer.filter(is_global_admin=True).count() - global_admins_before == 1
        assert await Developer.filter(is_global_admin=False).count() - non_global_before == 2
        dev_ids = [d.id for d in developers]
        granted = await DeveloperCompanyPermission.filter(developer_id__in=dev_ids)
        permissions = {p.permission for p in granted}
        assert CompanyPermission.ADMIN in permissions
        assert CompanyPermission.USER in permissions

        # Then: the backbone entities are created in the expected counts
        assert await Company.all().count() - companies_before == 1
        assert await User.all().count() - users_before == 3
        assert await Campaign.all().count() - campaigns_before == 1
        assert await CampaignBook.all().count() - books_before == cfg.books_per_campaign

        # Then: the created company's users cover all three roles (scope to the new
        # company so session-fixture users from other tests can't satisfy the assertion).
        new_companies = [c for c in await Company.all() if str(c.id) not in company_ids_before]
        assert len(new_companies) == 1
        new_users = await User.filter(company_id=new_companies[0].id)
        roles = {u.role for u in new_users}
        assert {UserRole.ADMIN, UserRole.STORYTELLER, UserRole.PLAYER} <= roles

        # Then: characters cover every type and include a vampire and a werewolf
        assert await Character.all().count() - characters_before == 4
        chars = await Character.all()
        char_types = {c.type for c in chars}
        assert {CharacterType.PLAYER, CharacterType.NPC, CharacterType.STORYTELLER} <= char_types
        char_classes = {c.character_class for c in chars}
        assert CharacterClass.VAMPIRE in char_classes
        assert CharacterClass.WEREWOLF in char_classes

        # Then: content entities are present (floors pinned to 1 in cfg above)
        assert await CharacterInventory.all().count() >= 1
        assert await DiceRoll.all().count() >= 1
        assert await DiceRollResult.all().count() == await DiceRoll.all().count()
        assert await QuickRoll.all().count() >= 1

        # Then: notes attach to all three target types
        assert await Note.filter(campaign_id__isnull=False).count() >= 1
        assert await Note.filter(book_id__isnull=False).count() >= 1
        assert await Note.filter(character_id__isnull=False).count() >= 1

        # Then: fake image assets attach to characters, books, and chapters
        assert await S3Asset.filter(character_id__isnull=False).count() >= 1
        assert await S3Asset.filter(book_id__isnull=False).count() >= 1
        assert await S3Asset.filter(chapter_id__isnull=False).count() >= 1
        # Then: every asset is an image pointing at picsum.photos (no real S3 upload)
        assets = await S3Asset.all()
        assert all(a.asset_type == AssetType.IMAGE for a in assets)
        assert all(a.public_url.startswith("https://picsum.photos/") for a in assets)

        # Then: every generated row is active (no archived rows)
        assert await Company.filter(is_archived=True).count() == 0
        assert await Character.filter(is_archived=True).count() == 0
        assert await Note.filter(is_archived=True).count() == 0
