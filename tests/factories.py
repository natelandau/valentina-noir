"""Factories for beanie models.

Read more at https://polyfactory.litestar.dev/latest/index.html
"""

from beanie import PydanticObjectId
from faker import Faker
from polyfactory.decorators import post_generated
from polyfactory.factories.beanie_odm_factory import BeanieDocumentFactory

from vapi.constants import CharacterClass, CharacterStatus, DiceSize, GameVersion
from vapi.db.models import (
    Character,
    CharacterTrait,
    DiceRoll,
    Trait,
    TraitCategory,
)
from vapi.db.models.character import (
    HunterAttributes,
    MageAttributes,
    VampireAttributes,
    WerewolfAttributes,
)
from vapi.db.models.diceroll import DiceRollResultSchema
from vapi.domain.handlers.diceroll_handler import roll_dice

fake = Faker()


def generate_word_with_min_length(*, min_length: int = 3, part_of_speech: str = "noun") -> str:
    """Generate a word with a minimum length."""
    word = fake.word(part_of_speech=part_of_speech)
    while len(word) < min_length:
        word = fake.word(part_of_speech="noun")
    return word


class CharacterFactory(BeanieDocumentFactory[Character]):
    """Factory to create a character object in the database."""

    __model__ = Character
    __set_as_default_factory_for_type__ = True
    __min_collection_length__ = 1
    __max_collection_length__ = 5
    __randomize_collection_length__ = True

    @classmethod
    def model_version(cls) -> int:
        return 1

    @classmethod
    def is_archived(cls) -> bool:
        return False

    @classmethod
    def name_first(cls) -> str:
        word = fake.first_name()
        while len(word) < 3:
            word = fake.first_name()
        return word

    @classmethod
    def name_last(cls) -> str:
        word = fake.last_name()
        while len(word) < 3:
            word = fake.last_name()
        return word

    @classmethod
    def name_nick(cls) -> str:
        return f"The {fake.word(part_of_speech='noun')}"

    @classmethod
    def age(cls) -> int:
        return fake.random_int(min=18, max=100)

    @classmethod
    def biography(cls) -> str:
        return fake.text()

    @classmethod
    def traits(cls) -> list:
        return []

    @classmethod
    def status(cls) -> CharacterStatus:
        return CharacterStatus.ALIVE

    @classmethod
    def concept_id(cls) -> None:
        return None

    @classmethod
    def demeanor(cls) -> str:
        return generate_word_with_min_length(min_length=3, part_of_speech="adjective")

    @classmethod
    def nature(cls) -> str:
        return generate_word_with_min_length(min_length=3, part_of_speech="noun")

    @classmethod
    def character_trait_ids(cls) -> list:
        return []

    @classmethod
    def is_temporary(cls) -> bool:
        return False

    @classmethod
    def is_chargen(cls) -> bool:
        return False

    @classmethod
    def chargen_session_id(cls) -> None:
        return None

    @classmethod
    def starting_points(cls) -> int:
        return 0

    @classmethod
    def asset_ids(cls) -> list:
        return []

    @post_generated
    @classmethod
    def vampire_attributes(cls) -> VampireAttributes:
        return VampireAttributes()

    @post_generated
    @classmethod
    def werewolf_attributes(cls) -> WerewolfAttributes:
        return WerewolfAttributes()

    @post_generated
    @classmethod
    def mage_attributes(cls) -> MageAttributes:
        return None

    @post_generated
    @classmethod
    def hunter_attributes(cls) -> HunterAttributes:
        return None


class CharacterTraitFactory(BeanieDocumentFactory[CharacterTrait]):
    """Factory to create a character trait object in the database."""

    __model__ = CharacterTrait
    __set_as_default_factory_for_type__ = True
    __min_collection_length__ = 1
    __max_collection_length__ = 5
    __randomize_collection_length__ = True

    @classmethod
    def name(cls) -> str:
        return (
            generate_word_with_min_length(min_length=3, part_of_speech="verb")
            + " "
            + generate_word_with_min_length(min_length=3, part_of_speech="noun")
        )

    @classmethod
    def is_archived(cls) -> bool:
        return False

    @classmethod
    def character_id(cls) -> PydanticObjectId:
        return PydanticObjectId()

    @classmethod
    def trait(cls) -> Trait:
        return TraitFactory()

    @classmethod
    def value(cls) -> int:
        return fake.random_int(min=0, max=5)


class DiceRollFactory(BeanieDocumentFactory[DiceRoll]):
    """Factory to create a dice roll object in the database."""

    __model__ = DiceRoll
    __set_as_default_factory_for_type__ = True
    __min_collection_length__ = 1
    __max_collection_length__ = 5
    __randomize_collection_length__ = True

    @classmethod
    def model_version(cls) -> int:
        return 1

    @classmethod
    def is_archived(cls) -> bool:
        return False

    @classmethod
    def traits(cls) -> list:
        return []

    @classmethod
    def difficulty(cls) -> int:
        return fake.random_int(min=2, max=7)

    @classmethod
    def dice_size(cls) -> DiceSize:
        return DiceSize.D10

    @classmethod
    def num_dice(cls) -> int:
        return fake.random_int(min=1, max=6)

    @classmethod
    def num_desperation_dice(cls) -> int:
        return fake.random_int(min=0, max=6)

    @classmethod
    def result(cls) -> DiceRollResultSchema:
        return roll_dice(
            num_dice=cls.num_dice(),
            num_desperation_dice=cls.num_desperation_dice(),
            difficulty=cls.difficulty(),
            dice_size=cls.dice_size(),
        )


class TraitCategoryFactory(BeanieDocumentFactory[TraitCategory]):
    """Factory to create a trait category object in the database."""

    __model__ = TraitCategory
    __set_as_default_factory_for_type__ = True
    __min_collection_length__ = 1
    __max_collection_length__ = 5
    __randomize_collection_length__ = True

    @classmethod
    def is_archived(cls) -> bool:
        return False

    @classmethod
    def name(cls) -> str:
        return generate_word_with_min_length(min_length=3, part_of_speech="noun")

    @classmethod
    def description(cls) -> str:
        return fake.text()

    @classmethod
    def character_classes(cls) -> list:
        return [CharacterClass.VAMPIRE, CharacterClass.WEREWOLF]

    @classmethod
    def game_versions(cls) -> list:
        return [GameVersion.V4, GameVersion.V5]

    @classmethod
    def show_when_empty(cls) -> bool:
        return True

    @classmethod
    def order(cls) -> int:
        return fake.random_int(min=0, max=20)

    @classmethod
    def parent_sheet_section_id(cls) -> PydanticObjectId:
        return PydanticObjectId()


class TraitFactory(BeanieDocumentFactory[Trait]):
    """Factory to create a trait object in the database."""

    __model__ = Trait
    __set_as_default_factory_for_type__ = True
    __min_collection_length__ = 1
    __max_collection_length__ = 5
    __randomize_collection_length__ = True

    @classmethod
    def is_archived(cls) -> bool:
        return False

    @classmethod
    def name(cls) -> str:
        return fake.word(part_of_speech="verb") + " " + fake.word(part_of_speech="noun")

    @classmethod
    def description(cls) -> str:
        return fake.text()

    @classmethod
    def character_classes(cls) -> list:
        return [CharacterClass.VAMPIRE, CharacterClass.WEREWOLF]

    @classmethod
    def game_versions(cls) -> list:
        return [GameVersion.V4, GameVersion.V5]

    @classmethod
    def show_when_empty(cls) -> bool:
        return False

    @classmethod
    def max_value(cls) -> int:
        return 5

    @classmethod
    def min_value(cls) -> int:
        return 0

    @classmethod
    def is_custom(cls) -> bool:
        return False

    @classmethod
    def custom_for_character_id(cls) -> PydanticObjectId | None:
        return None

    @classmethod
    def initial_cost(cls) -> int:
        return 1

    @classmethod
    def upgrade_cost(cls) -> int:
        return 2

    @classmethod
    def advantage_category_id(cls) -> PydanticObjectId | None:
        return None

    @classmethod
    def advantage_category_name(cls) -> str | None:
        return None

    @classmethod
    def sheet_section_id(cls) -> PydanticObjectId | None:
        return None

    @classmethod
    def sheet_section_name(cls) -> str | None:
        return None
