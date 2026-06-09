"""Unit tests for the dev-data PopulateConfig."""

from scripts.dev_data.config import PopulateConfig


def test_default_config_has_demo_worthy_counts() -> None:
    """Verify PopulateConfig defaults are demo-worthy and ranges are valid."""
    # Given / When: the default config
    cfg = PopulateConfig()

    # Then: the primary counts match the spec defaults
    assert cfg.num_companies == 2
    assert cfg.num_users == 4
    assert cfg.num_campaigns == 2
    assert cfg.num_characters == 6
    assert cfg.books_per_campaign == 2
    assert cfg.chapters_per_book == 2

    # Then: the random ranges are (low, high) tuples with low <= high
    for low, high in (
        cfg.dice_rolls_per_char,
        cfg.quick_rolls_per_user,
        cfg.notes_per_target,
        cfg.inventory_per_char,
    ):
        assert 0 <= low <= high


def test_config_counts_are_overridable() -> None:
    """Verify PopulateConfig accepts overridden counts."""
    # Given / When: an overridden config
    cfg = PopulateConfig(num_companies=1, num_users=3, num_campaigns=1, num_characters=4)

    # Then: overrides take effect
    assert cfg.num_companies == 1
    assert cfg.num_users == 3
    assert cfg.num_campaigns == 1
    assert cfg.num_characters == 4
