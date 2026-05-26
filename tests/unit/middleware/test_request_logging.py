"""Tests for the combined request/response logging middleware and its config."""

from vapi.constants import LOG_FIELD_ROUTING, LOG_FIELDS_CATALOG

# Public log-field names that carry a request_/response_ prefix because their
# litestar extractor field (body, headers) exists on both the request and response.
_PREFIXED_COLLISION_FIELDS = {
    "request_body",
    "request_headers",
    "response_body",
    "response_headers",
}


def test_catalog_is_derived_from_routing() -> None:
    """Ensure the catalog stays in lockstep with the routing table."""
    # Given the routing table is the single source of truth
    # When the catalog is derived from it
    # Then the catalog matches the routing keys and includes known fields
    assert frozenset(LOG_FIELD_ROUTING) == LOG_FIELDS_CATALOG
    assert "path" in LOG_FIELDS_CATALOG
    assert "duration_ms" in LOG_FIELDS_CATALOG


def test_routing_targets_are_well_formed() -> None:
    """Verify every routing entry has a valid target and the key fields route correctly."""
    # Given the set of valid routing targets
    valid_targets = {"request", "response", "synthetic"}

    # When inspecting each (target, extractor_field) pair
    # Then every target is known and the key fields route as expected
    assert all(target in valid_targets for target, _ in LOG_FIELD_ROUTING.values())
    assert LOG_FIELD_ROUTING["duration_ms"] == ("synthetic", "duration_ms")
    assert LOG_FIELD_ROUTING["request_body"] == ("request", "body")
    assert LOG_FIELD_ROUTING["response_body"] == ("response", "body")
    assert LOG_FIELD_ROUTING["status_code"] == ("response", "status_code")


def test_only_collision_fields_are_prefixed() -> None:
    """Confirm only the body/headers collision fields carry a request_/response_ prefix."""
    # Given the routing table
    # When comparing each public name to its litestar extractor field
    # Then a name differs from its extractor field only for the prefixed collision fields
    renamed = {
        name for name, (_, extractor_field) in LOG_FIELD_ROUTING.items() if name != extractor_field
    }
    assert renamed == _PREFIXED_COLLISION_FIELDS
