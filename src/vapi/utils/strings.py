"""String utilities."""

from __future__ import annotations

import random
import re
import string
import unicodedata

__all__ = ("convert_int_to_emoji", "get_discord_avatar_url", "random_string", "slugify")

_EMOJI_MAP: tuple[tuple[str, str], ...] = (
    (":zero:", "0️⃣"),
    (":one:", "1️⃣"),
    (":two:", "2️⃣"),
    (":three:", "3️⃣"),
    (":four:", "4️⃣"),
    (":five:", "5️⃣"),
    (":six:", "6️⃣"),
    (":seven:", "7️⃣"),
    (":eight:", "8️⃣"),
    (":nine:", "9️⃣"),
    (":keycap_ten:", "🔟"),
)

_DISCORD_IMAGE_BASE_URL = "https://cdn.discordapp.com/"
_DISCORD_AVATAR_URL = _DISCORD_IMAGE_BASE_URL + "avatars/{user_id}/{avatar_hash}.{format}"
_DISCORD_DEFAULT_AVATAR_URL = _DISCORD_IMAGE_BASE_URL + "embed/avatars/{modulo5}.png"


def slugify(value: str, *, separator: str | None = None, allow_unicode: bool = False) -> str:
    """Generate an ASCII (or Unicode) slug from the given string.

    Args:
        value (str): The input string to slugify.
        separator (str, optional): The separator to use in place of spaces and hyphens.
            If `None`, hyphens are used (the default is None).
        allow_unicode (bool, optional): Whether to allow Unicode characters in the output.
            If False, non-ASCII characters are removed (the default is False).

    Returns:
        str: A slugified version of the input string.
    """
    if allow_unicode:
        value = unicodedata.normalize("NFKC", value)
    else:
        value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value.lower())
    if separator is not None:
        return re.sub(r"[-\s]+", "-", value).strip("-_").replace("-", separator)
    return re.sub(r"[-\s]+", "-", value).strip("-_")


def convert_int_to_emoji(*, num: int, as_shortcode: bool = False) -> str:
    """Convert an integer to a unicode emoji or a string.

    This method converts an integer to its corresponding emoji representation if it is between 0 and 10. For integers outside this range, it returns the number as a string. Optionally, it can wrap numbers larger than emojis within in markdown <pre> markers.

    Args:
        num (int): The integer to convert.
        as_shortcode (bool, optional): Whether to return a shortcode instead of a unicode emoji. Defaults to False.

    Returns:
        str: The emoji corresponding to the integer, or the integer as a string.

    """
    if not (0 <= num <= 10):  # noqa: PLR2004
        return f"`{num}`" if as_shortcode else str(num)

    shortcode, unicode_emoji = _EMOJI_MAP[num]
    return shortcode if as_shortcode else unicode_emoji


def random_string(length: int) -> str:
    """Generate a random string of ASCII letters with the specified length.

    Create a string by randomly selecting characters from ASCII letters (a-z, A-Z). Useful for generating random identifiers, test data, or temporary names.

    Args:
        length (int): The desired length of the generated string

    Returns:
        str: A string of random ASCII letters with the specified length

    Example:
        >>> assert len(random_string(10)) == 10
    """
    return "".join(random.choice(string.ascii_letters) for _ in range(length))


def get_discord_avatar_url(
    avatar_hash: str, discord_user_id: int, discriminator: str
) -> str | None:
    """Return the URL of the user's Discord avatar.

    Args:
        avatar_hash (str): The hash of the Discord avatar.
        discord_user_id (int): The ID of the Discord user.
        discriminator (str): The discriminator of the Discord user.

    Returns:
        str | None: The URL of the Discord avatar.
    """
    if not avatar_hash:
        if not discriminator:
            return None
        return _DISCORD_DEFAULT_AVATAR_URL.format(modulo5=int(discriminator) % 5)

    image_format = "gif" if avatar_hash.startswith("a_") else "png"
    return _DISCORD_AVATAR_URL.format(
        user_id=discord_user_id, avatar_hash=avatar_hash, format=image_format
    )
