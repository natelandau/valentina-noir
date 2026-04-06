"""Test the strings module."""

from __future__ import annotations

import re

import pytest

from vapi.utils import strings

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    ("value", "separator", "allow_unicode", "expected"),
    [
        ("Hello World", None, False, "hello-world"),
        ("Hello World", None, True, "hello-world"),
        ("Hello World", "_", False, "hello_world"),
        ("Café World", None, True, "café-world"),
        ("Café World", None, False, "cafe-world"),
    ],
)
def test_slugify(*, value: str, separator: str | None, allow_unicode: bool, expected: str) -> None:
    """Verify that the slugify function is working correctly."""
    assert (
        strings.slugify(value=value, separator=separator, allow_unicode=allow_unicode) == expected
    )


@pytest.mark.parametrize(
    ("num", "as_shortcode", "expected"),
    [
        (0, False, "0️⃣"),
        (0, True, ":zero:"),
        (10, False, "🔟"),
        (10, True, ":keycap_ten:"),
        (11, False, "11"),
        (11, True, "`11`"),
    ],
)
def test_convert_int_to_emoji(*, num: int, as_shortcode: bool, expected: str) -> None:
    """Verify that the convert_int_to_emoji function is working correctly."""
    assert strings.convert_int_to_emoji(num=num, as_shortcode=as_shortcode) == expected


def test_random_string(debug) -> None:
    """Test random_string()."""
    returned = strings.random_string(10)

    assert isinstance(returned, str)
    assert len(returned) == 10
    assert re.match(r"[a-zA-Z]{10}", returned)


class TestGetDiscordAvatarUrl:
    """Tests for get_discord_avatar_url."""

    def test_get_discord_avatar_url_png(self) -> None:
        """Verify a standard avatar hash returns a PNG URL."""
        # Given a non-animated avatar hash
        avatar_hash = "abc123"
        user_id = 12345
        discriminator = "0001"

        # When getting the avatar URL
        result = strings.get_discord_avatar_url(avatar_hash, user_id, discriminator)

        # Then a PNG avatar URL is returned
        assert result == "https://cdn.discordapp.com/avatars/12345/abc123.png"

    def test_get_discord_avatar_url_gif(self) -> None:
        """Verify an animated avatar hash returns a GIF URL."""
        # Given an animated avatar hash (starts with "a_")
        avatar_hash = "a_abc123"
        user_id = 99999
        discriminator = "1234"

        # When getting the avatar URL
        result = strings.get_discord_avatar_url(avatar_hash, user_id, discriminator)

        # Then a GIF avatar URL is returned
        assert result == "https://cdn.discordapp.com/avatars/99999/a_abc123.gif"

    @pytest.mark.parametrize(
        ("discriminator", "expected_modulo"),
        [
            ("0000", 0),
            ("0001", 1),
            ("0002", 2),
            ("0003", 3),
            ("0004", 4),
            ("0005", 0),
            ("1234", 4),
        ],
    )
    def test_get_discord_avatar_url_default_avatar(
        self, *, discriminator: str, expected_modulo: int
    ) -> None:
        """Verify a missing avatar hash falls back to the default avatar using discriminator modulo 5."""
        # Given no avatar hash
        # When getting the avatar URL
        result = strings.get_discord_avatar_url("", 12345, discriminator)

        # Then the default avatar URL is returned with correct modulo
        assert result == f"https://cdn.discordapp.com/embed/avatars/{expected_modulo}.png"

    def test_get_discord_avatar_url_no_hash_no_discriminator(self) -> None:
        """Verify None is returned when both avatar hash and discriminator are empty."""
        # Given no avatar hash and no discriminator
        # When getting the avatar URL
        result = strings.get_discord_avatar_url("", 12345, "")

        # Then None is returned
        assert result is None
