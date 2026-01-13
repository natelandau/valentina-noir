"""Factories for beanie models.

Read more at https://polyfactory.litestar.dev/latest/index.html
"""

from faker import Faker
from polyfactory.factories.beanie_odm_factory import BeanieDocumentFactory

from vapi.db.models import (
    Campaign,
    CampaignBook,
    CampaignChapter,
    Company,
    Developer,
    User,
)
from vapi.db.models.company import CompanySettings

fake = Faker()

__all__ = ("CompanyFactory", "DeveloperFactory", "UserFactory")


def generate_word_with_min_length(*, min_length: int = 3, part_of_speech: str = "noun") -> str:
    """Generate a word with a minimum length."""
    word = fake.word(part_of_speech=part_of_speech)
    while len(word) < min_length:
        word = fake.word(part_of_speech="noun")
    return word


class DeveloperFactory(BeanieDocumentFactory[Developer]):
    """Factory to create a Developer object in the database."""

    __model__ = Developer
    __set_as_default_factory_for_type__ = True
    __min_collection_length__ = 1
    __max_collection_length__ = 3
    __randomize_collection_length__ = True

    @classmethod
    def name(cls) -> str:
        return fake.name()

    @classmethod
    def email(cls) -> str:
        return fake.email()

    @classmethod
    def companies(cls) -> list:
        return []

    @classmethod
    def is_archived(cls) -> bool:
        return False

    @classmethod
    def model_version(cls) -> int:
        return 1


class CompanyFactory(BeanieDocumentFactory[Company]):
    """Factory to create a company object in the database."""

    __model__ = Company
    __set_as_default_factory_for_type__ = True
    __min_collection_length__ = 1
    __max_collection_length__ = 12
    __randomize_collection_length__ = True

    @classmethod
    def name(cls) -> str:
        return fake.company()

    @classmethod
    def description(cls) -> str:
        return fake.catch_phrase()

    @classmethod
    def developer_permissions(cls) -> list:
        return []

    @classmethod
    def is_archived(cls) -> bool:
        return False

    @classmethod
    def model_version(cls) -> int:
        return 1

    @classmethod
    def user_ids(cls) -> list:
        return []

    @classmethod
    def settings(cls) -> CompanySettings:
        return CompanySettings()


class UserFactory(BeanieDocumentFactory[User]):
    """Factory to create a user object in the database."""

    __model__ = User
    __set_as_default_factory_for_type__ = True
    __min_collection_length__ = 2
    __max_collection_length__ = 12
    __randomize_collection_length__ = True

    @classmethod
    def name(cls) -> str:
        return fake.name()

    @classmethod
    def is_archived(cls) -> bool:
        return False

    @classmethod
    def model_version(cls) -> int:
        return 1

    @classmethod
    def player_characters(cls) -> list:
        return []

    @classmethod
    def campaign_experience(cls) -> list:
        return []

    @classmethod
    def asset_ids(cls) -> list:
        return []


class CampaignFactory(BeanieDocumentFactory[Campaign]):
    """Factory to create a campaign object in the database."""

    __model__ = Campaign
    __set_as_default_factory_for_type__ = True
    __min_collection_length__ = 1
    __max_collection_length__ = 5
    __randomize_collection_length__ = True

    @classmethod
    def name(cls) -> str:
        return fake.company()

    @classmethod
    def description(cls) -> str:
        return fake.catch_phrase()

    @classmethod
    def is_archived(cls) -> bool:
        return False

    @classmethod
    def model_version(cls) -> int:
        return 1

    @classmethod
    def books(cls) -> list:
        return []

    @classmethod
    def danger(cls) -> int:
        return 0

    @classmethod
    def desperation(cls) -> int:
        return 0

    @classmethod
    def asset_ids(cls) -> list:
        return []


class CampaignBookFactory(BeanieDocumentFactory[CampaignBook]):
    """Factory to create a campaign book object in the database."""

    __model__ = CampaignBook
    __set_as_default_factory_for_type__ = True
    __min_collection_length__ = 1
    __max_collection_length__ = 5
    __randomize_collection_length__ = True

    @classmethod
    def name(cls) -> str:
        return fake.company()

    @classmethod
    def description(cls) -> str:
        return fake.catch_phrase()

    @classmethod
    def chapters(cls) -> list:
        return []

    @classmethod
    def is_archived(cls) -> bool:
        return False

    @classmethod
    def model_version(cls) -> int:
        return 1

    @classmethod
    def asset_ids(cls) -> list:
        return []


class CampaignChapterFactory(BeanieDocumentFactory[CampaignChapter]):
    """Factory to create a campaign chapter object in the database."""

    __model__ = CampaignChapter
    __set_as_default_factory_for_type__ = True
    __min_collection_length__ = 1
    __max_collection_length__ = 5
    __randomize_collection_length__ = True

    @classmethod
    def name(cls) -> str:
        return fake.company()

    @classmethod
    def description(cls) -> str:
        return fake.catch_phrase()

    @classmethod
    def is_archived(cls) -> bool:
        return False

    @classmethod
    def model_version(cls) -> int:
        return 1

    @classmethod
    def asset_ids(cls) -> list:
        return []
