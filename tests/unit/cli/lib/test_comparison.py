"""Unit tests for fixture comparison helpers."""

from __future__ import annotations

from vapi.cli.lib.comparison import fixture_key_error


class TestFixtureKeyError:
    """Unit tests for fixture_key_error."""

    def test_names_file_entry_and_missing_key(self) -> None:
        """Verify the error names the fixture file, the entry, and the missing key."""
        # Given: a fixture entry missing a required key
        item = {"name": "Ahroun"}

        # When: building the error for a KeyError on the missing key
        error = fixture_key_error("werewolf_auspices.json", item, KeyError("description"))

        # Then: the message points at the file, the entry name, and the key
        message = str(error)
        assert isinstance(error, ValueError)
        assert "werewolf_auspices.json" in message
        assert "Ahroun" in message
        assert "description" in message

    def test_falls_back_to_entry_repr_when_unnamed(self) -> None:
        """Verify an entry without a name is described by its own contents."""
        # Given: a fixture entry with no name key
        item = {"renown": "glory"}

        # When: building the error
        error = fixture_key_error("traits.json", item, KeyError("name"))

        # Then: the entry contents appear in the message
        assert "renown" in str(error)
