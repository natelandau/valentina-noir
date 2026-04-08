"""Tests for UserRole enum."""

from vapi.constants import UserRole


def test_userrole_has_deactivated_variant():
    """Test that UserRole enum has DEACTIVATED variant."""
    assert UserRole.DEACTIVATED.value == "DEACTIVATED"
    assert UserRole("DEACTIVATED") is UserRole.DEACTIVATED
