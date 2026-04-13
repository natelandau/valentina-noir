"""Unit tests for vapi.lib.patch.apply_patch."""

from __future__ import annotations

import msgspec

from vapi.lib.patch import apply_patch


class _Target:
    """Minimal stand-in for a Tortoise model instance."""

    def __init__(self, **kwargs: object) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


class _Patch(msgspec.Struct):
    """Patch DTO with UNSET defaults."""

    name: str | msgspec.UnsetType = msgspec.UNSET
    description: str | None | msgspec.UnsetType = msgspec.UNSET
    count: int | msgspec.UnsetType = msgspec.UNSET


class _PatchWithExtra(msgspec.Struct):
    """Patch DTO that has a field the target doesn't."""

    name: str | msgspec.UnsetType = msgspec.UNSET
    nonexistent_field: str | msgspec.UnsetType = msgspec.UNSET


class TestBuildChanges:
    """Test the apply_patch utility."""

    def test_applies_changed_fields(self) -> None:
        """Verify changed fields are applied and returned in the diff."""
        # Given a target with known values
        target = _Target(name="Old", description="Desc", count=1)

        # When patching name and count
        changes = apply_patch(target, _Patch(name="New", count=5))

        # Then the target is updated
        assert target.name == "New"
        assert target.count == 5
        assert target.description == "Desc"

        # And the diff records both changes
        assert changes == {
            "name": {"old": "Old", "new": "New"},
            "count": {"old": 1, "new": 5},
        }

    def test_no_op_returns_empty_dict(self) -> None:
        """Verify setting a field to its current value produces no diff."""
        # Given a target
        target = _Target(name="Same", description=None, count=0)

        # When patching to the same values
        changes = apply_patch(target, _Patch(name="Same", count=0))

        # Then no changes are recorded
        assert changes == {}

    def test_unset_fields_are_skipped(self) -> None:
        """Verify UNSET fields are not applied."""
        # Given a target
        target = _Target(name="Keep", description="Keep", count=1)

        # When patching only name (others are UNSET)
        changes = apply_patch(target, _Patch(name="Changed"))

        # Then only name is changed
        assert target.name == "Changed"
        assert target.description == "Keep"
        assert target.count == 1
        assert changes == {"name": {"old": "Keep", "new": "Changed"}}

    def test_empty_patch_returns_empty_dict(self) -> None:
        """Verify an all-UNSET patch produces no changes."""
        # Given a target
        target = _Target(name="Keep", description="Keep", count=1)

        # When applying an empty patch
        changes = apply_patch(target, _Patch())

        # Then nothing changes
        assert changes == {}
        assert target.name == "Keep"

    def test_nullable_field_to_none(self) -> None:
        """Verify nullable fields can be set to None."""
        # Given a target with a description
        target = _Target(name="X", description="Has desc", count=0)

        # When patching description to None
        changes = apply_patch(target, _Patch(description=None))

        # Then the diff is recorded
        assert target.description is None
        assert changes == {"description": {"old": "Has desc", "new": None}}

    def test_prefix_applied_to_keys(self) -> None:
        """Verify prefix is prepended to change keys."""
        # Given a target
        target = _Target(name="Old", description=None, count=0)

        # When patching with a prefix
        changes = apply_patch(target, _Patch(name="New"), prefix="nested.")

        # Then the key uses the prefix
        assert changes == {"nested.name": {"old": "Old", "new": "New"}}

    def test_exclude_skips_fields(self) -> None:
        """Verify excluded fields are not applied."""
        # Given a target
        target = _Target(name="Old", description="Old", count=0)

        # When patching with name excluded
        changes = apply_patch(
            target,
            _Patch(name="New", description="New"),
            exclude=frozenset({"name"}),
        )

        # Then name is untouched but description is changed
        assert target.name == "Old"
        assert target.description == "New"
        assert changes == {"description": {"old": "Old", "new": "New"}}

    def test_missing_target_attribute_skipped(self) -> None:
        """Verify fields not on the target are silently skipped."""
        # Given a target that lacks 'nonexistent_field'
        target = _Target(name="Old")

        # When patching with a field the target doesn't have
        changes = apply_patch(target, _PatchWithExtra(name="New", nonexistent_field="X"))

        # Then the valid field is applied and the missing one is skipped
        assert target.name == "New"
        assert not hasattr(target, "nonexistent_field")
        assert changes == {"name": {"old": "Old", "new": "New"}}

    def test_prefix_and_exclude_combined(self) -> None:
        """Verify prefix and exclude work together."""
        # Given a target
        target = _Target(name="Old", description="Old", count=0)

        # When using both prefix and exclude
        changes = apply_patch(
            target,
            _Patch(name="New", description="New", count=99),
            prefix="item.",
            exclude=frozenset({"count"}),
        )

        # Then excluded field is skipped and prefix is applied to the rest
        assert target.count == 0
        assert changes == {
            "item.name": {"old": "Old", "new": "New"},
            "item.description": {"old": "Old", "new": "New"},
        }
