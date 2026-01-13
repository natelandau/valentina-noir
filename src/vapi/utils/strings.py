"""String utilities."""

from __future__ import annotations

import random
import re
import string
import unicodedata

__all__ = ("convert_int_to_emoji", "slugify")


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

    emoji_map = {
        0: (":zero:", "0️⃣"),
        1: (":one:", "1️⃣"),
        2: (":two:", "2️⃣"),
        3: (":three:", "3️⃣"),
        4: (":four:", "4️⃣"),
        5: (":five:", "5️⃣"),
        6: (":six:", "6️⃣"),
        7: (":seven:", "7️⃣"),
        8: (":eight:", "8️⃣"),
        9: (":nine:", "9️⃣"),
        10: (":keycap_ten:", "🔟"),
    }

    shortcode, unicode_emoji = emoji_map[num]
    if as_shortcode:
        return shortcode if num == 10 else f"{shortcode}"  # noqa: PLR2004
    return unicode_emoji


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
