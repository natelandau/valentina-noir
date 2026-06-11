"""Faker-backed text helpers that respect the database column constraints."""

import random

from faker import Faker

_fake = Faker()

# Curated gothic, World-of-Darkness-flavored word pools. Faker's company/catch_phrase
# generators read like corporations, which is confusing for a tabletop-RPG domain where
# a Company is a gaming group and a Campaign is a chronicle.
_COTERIE_ADJECTIVES: tuple[str, ...] = (
    "Crimson",
    "Ashen",
    "Sundered",
    "Hollow",
    "Pale",
    "Silent",
    "Broken",
    "Shrouded",
    "Obsidian",
    "Withered",
    "Gilded",
    "Forsaken",
    "Veiled",
    "Dread",
)
_COTERIE_GROUPS: tuple[str, ...] = (
    "Court",
    "Circle",
    "Covenant",
    "Coterie",
    "Order",
    "Cabal",
    "Conclave",
    "Assembly",
    "Chapter",
    "Fellowship",
)
_COTERIE_NOUNS: tuple[str, ...] = (
    "Long Night",
    "Veil",
    "Requiem",
    "Dusk",
    "Eclipse",
    "Ashes",
    "Silence",
    "Hunger",
    "Final Hour",
)
_COTERIE_PLACES: tuple[str, ...] = (
    "Hollow Street",
    "Ravenscroft",
    "Blackmoor",
    "Ash Lane",
    "Gallows Hill",
    "The Old Quarter",
    "Mourner's Row",
    "Saint Gall",
)
# Real, evocative cities for "<place> by Night"-style chronicle titles.
_CHRONICLE_CITIES: tuple[str, ...] = (
    "Chicago",
    "New Orleans",
    "Vienna",
    "Berlin",
    "Prague",
    "London",
    "Venice",
    "Cairo",
    "Lisbon",
    "Montreal",
    "New York",
    "Seattle",
    "Detroit",
    "Marseille",
    "Edinburgh",
    "Budapest",
    "Istanbul",
    "Buenos Aires",
    "Brooklyn",
    "Queens",
    "Staten Island",
    "Bronx",
    "Manhattan",
    "Boston",
)


def _sentences(low: int, high: int) -> str:
    """A block of [low, high] sentences for short prose fields (bios, descriptions)."""
    return _fake.paragraph(nb_sentences=random.randint(low, high), variable_nb_sentences=False)


def _paragraphs(low: int, high: int) -> str:
    """A block of [low, high] blank-line-separated paragraphs for long-form body text."""
    text = ""
    for _ in range(random.randint(low, high)):
        text += (
            _fake.paragraph(nb_sentences=random.randint(9, 16), variable_nb_sentences=False)
            + "\n\n"
        )
    return text.removesuffix("\n\n")


def _clamp(text: str, low: int, high: int) -> str:
    """Clamp text to [low, high] characters, padding short values deterministically."""
    text = text.strip()
    if len(text) > high:
        text = text[:high].strip()
    while len(text) < low:
        text = f"{text} x".strip()
    return text


def company_name() -> str:
    """A gothic coterie / gaming-group name clamped to Company.name (3-50)."""
    group = random.choice(_COTERIE_GROUPS)
    name = random.choice(
        (
            f"The {random.choice(_COTERIE_ADJECTIVES)} {group}",
            f"Children of the {random.choice(_COTERIE_NOUNS)}",
            f"Covenant of {random.choice(_COTERIE_PLACES)}",
            f"{group} of the {random.choice(_COTERIE_NOUNS)}",
        )
    )
    return _clamp(name, 3, 50)


def campaign_title() -> str:
    """A "<place> by Night"-style chronicle title clamped to Campaign.name (3-50)."""
    city = random.choice(_CHRONICLE_CITIES)
    adjective = random.choice(_COTERIE_ADJECTIVES)
    place = random.choice(_COTERIE_PLACES)
    name = random.choice(
        (
            f"{adjective.title()} {random.choice([city, place])} by Night",
            f"{random.choice([city, place])} by Night",
            f"The Fall of {random.choice([city, place])}",
            f"The Fall of {adjective.title()} {random.choice([city, place])}",
            f"{random.choice([city, place])} {adjective.title()} Nights",
            f"{random.choice([city, place])} Nights",
            f"{adjective.title()} {random.choice([city, place])} Unbound",
            f"{random.choice([city, place])} Unbound",
            f"Veil over {random.choice([city, place])}",
            f"{adjective.title()} Veil over {random.choice([city, place])}",
            f"{random.choice([city, place])} Unleashed",
            f"{adjective.title()} {city} Unleashed",
            f"The {adjective.title()} Cry of {random.choice([city, place])}",
            f"The Cry of {random.choice([city, place])}",
            f"A Requiem for {random.choice([city, place])}",
            f"The Hunger of {random.choice([city, place])}",
            f"{random.choice([city, place])} Undying",
            f"Who mourns for {random.choice([city, place])}",
            f"The Dusk of {random.choice([city, place])}",
        )
    )
    return _clamp(name, 3, 50)


def campaign_description() -> str:
    """A campaign description for Campaign.description (2-4 sentences)."""
    return _sentences(1, 3)


def book_title() -> str:
    """A book title clamped to CampaignBook.name (<=50)."""
    return _clamp(_fake.sentence(nb_words=3).rstrip("."), 3, 50)


def book_text() -> str:
    """Book body text for CampaignBook.description (2-4 paragraphs)."""
    return _paragraphs(3, 8)


def chapter_title() -> str:
    """A chapter title clamped to CampaignChapter.name (<=50)."""
    return _clamp(_fake.sentence(nb_words=3).rstrip("."), 3, 50)


def chapter_text() -> str:
    """Chapter body text for CampaignChapter.description (2-4 paragraphs)."""
    return _paragraphs(3, 8)


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


def inventory_item_description() -> str:
    """An inventory item description for CharacterInventory.description (2-4 sentences)."""
    return _paragraphs(1, 2)


def character_biography() -> str:
    """A character biography for Character.biography (2-4 sentences)."""
    return _paragraphs(1, 3)


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


def picsum_url(*, width: int, height: int, seed: int) -> str:
    """A picsum.photos image URL. The seed keeps each generated image distinct.

    These point at an external placeholder service; no file is ever uploaded to S3.
    """
    return f"https://picsum.photos/{width}/{height}?random={seed}"
