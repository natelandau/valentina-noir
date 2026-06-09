"""Configuration for dev-data population."""

from dataclasses import dataclass, field

from vapi.constants import CharacterClass, CharacterType

# Character type assignment: the first three characters in each campaign are forced to
# these types to guarantee coverage; remaining characters are weighted toward PLAYER.
TYPE_COVERAGE: tuple[CharacterType, ...] = (
    CharacterType.PLAYER,
    CharacterType.NPC,
    CharacterType.STORYTELLER,
)
# Weighted pool for characters beyond the coverage set (majority PLAYER).
TYPE_WEIGHTED_POOL: tuple[CharacterType, ...] = (
    CharacterType.PLAYER,
    CharacterType.PLAYER,
    CharacterType.PLAYER,
    CharacterType.NPC,
    CharacterType.STORYTELLER,
)
# Character class assignment: the first four characters in each campaign are forced to
# these classes to guarantee a vampire/werewolf/mortal/hunter mix; the rest are random.
# Only these classes are fully realized by CharacterAutogenerationHandler — its match
# statement generates splat attributes for VAMPIRE, WEREWOLF, HUNTER, and MORTAL needs
# none. GHOUL/MAGE are intentionally excluded: the handler has no match case for them, so
# they would produce characters with missing splat attributes.
CLASS_COVERAGE: tuple[CharacterClass, ...] = (
    CharacterClass.VAMPIRE,
    CharacterClass.WEREWOLF,
    CharacterClass.MORTAL,
    CharacterClass.HUNTER,
)
CLASS_POOL: tuple[CharacterClass, ...] = CLASS_COVERAGE


@dataclass
class PopulateConfig:
    """Knobs controlling how much dev data is generated.

    Primary counts are exposed as CLI flags; the random ranges use these defaults.
    """

    num_companies: int = 2
    num_users: int = 4
    num_campaigns: int = 2
    num_characters: int = 6
    books_per_campaign: int = 2
    chapters_per_book: int = 2

    # (low, high) inclusive random ranges
    dice_rolls_per_char: tuple[int, int] = (3, 8)
    quick_rolls_per_user: tuple[int, int] = (0, 3)
    notes_per_target: tuple[int, int] = (0, 3)
    inventory_per_char: tuple[int, int] = (0, 6)

    # Traits attached to each generated quick roll (random count in this range)
    traits_per_quick_roll: tuple[int, int] = (1, 3)
    type_coverage: tuple = field(default=TYPE_COVERAGE)
    class_coverage: tuple = field(default=CLASS_COVERAGE)
