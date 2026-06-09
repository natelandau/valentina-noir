"""Faker-backed text helpers that respect the database column constraints."""

from faker import Faker

_fake = Faker()


def _clamp(text: str, low: int, high: int) -> str:
    """Clamp text to [low, high] characters, padding short values deterministically."""
    text = text.strip()
    if len(text) > high:
        text = text[:high].strip()
    while len(text) < low:
        text = f"{text} x".strip()
    return text


def company_name() -> str:
    """A company name clamped to Company.name (3-50)."""
    return _clamp(_fake.company(), 3, 50)


def campaign_title() -> str:
    """A campaign title clamped to Campaign.name (3-50)."""
    return _clamp(_fake.catch_phrase(), 3, 50)


def book_title() -> str:
    """A book title clamped to CampaignBook.name (<=50)."""
    return _clamp(_fake.sentence(nb_words=3).rstrip("."), 3, 50)


def chapter_title() -> str:
    """A chapter title clamped to CampaignChapter.name (<=50)."""
    return _clamp(_fake.sentence(nb_words=3).rstrip("."), 3, 50)


def note_title() -> str:
    """A note title clamped to Note.title (3-50)."""
    return _clamp(_fake.sentence(nb_words=4).rstrip("."), 3, 50)


def note_body() -> str:
    """A note body for Note.content (min 3, no max)."""
    return _fake.paragraph(nb_sentences=3)


def quick_roll_name() -> str:
    """A quick-roll name clamped to QuickRoll.name (3-50)."""
    return _clamp(f"{_fake.word().title()} Roll", 3, 50)


def inventory_item_name() -> str:
    """An inventory item name clamped to CharacterInventory.name (<=50)."""
    return _clamp(_fake.word().title(), 3, 50)


def dice_comment() -> str:
    """An optional dice-roll comment."""
    return _fake.sentence(nb_words=6)


def person_name() -> tuple[str, str]:
    """A (first, last) name pair, each clamped to <=50 (min 2 per User validators)."""
    return _clamp(_fake.first_name(), 2, 50), _clamp(_fake.last_name(), 2, 50)


def email() -> str:
    """An email for a generated company or user (the columns are not unique-constrained)."""
    return _fake.email()


def username() -> str:
    """A username clamped to User.username (3-50)."""
    return _clamp(_fake.user_name(), 3, 50)
