"""Tests for the archivable-model registry."""

import pytest

from vapi.db.archivable import PURGE_MODELS, archivable_models

pytestmark = pytest.mark.anyio


def test_purge_models_are_cascade_tree_tops() -> None:
    """Verify PURGE_MODELS contains the FK-CASCADE-tree top models only."""
    # Given the purge model names
    names = {m.__name__ for m in PURGE_MODELS}

    # Then the tree tops are present and CASCADE-removed children are absent
    assert {"Company", "User", "Campaign", "Character", "Note"} <= names
    assert "Specialty" not in names
    assert "CharacterTrait" not in names


async def test_archivable_models_includes_cascade_children() -> None:
    """Verify the restore registry covers children that the cascade stamps."""
    # Given the discovered archivable models
    names = {m.__name__ for m in archivable_models()}

    # Then both tops and stamped children are present
    assert {"Specialty", "CharacterTrait", "S3Asset", "CampaignExperience"} <= names
