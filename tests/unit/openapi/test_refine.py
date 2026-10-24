"""Test the OpenAPI schema refinements."""

import pytest

from vapi.asgi import create_app
from vapi.openapi.refine import refine_openapi_schema

pytestmark = pytest.mark.anyio

_TRACKER_MAPPING = {
    "COUNTER": "#/components/schemas/CounterTrackerResponse",
    "DAMAGE": "#/components/schemas/DamageTrackResponse",
    "STAINS": "#/components/schemas/StainsTrackerResponse",
}
_TRACKER_PATH = (
    "/api/v1/companies/{company_id}/characters/{character_id}/traits/{character_trait_id}/tracker"
)


@pytest.fixture(name="schema", scope="module")
async def fx_schema() -> dict:
    """Build the app's OpenAPI schema once with the refinements applied."""
    app = create_app()
    await refine_openapi_schema(app)
    return app.openapi_schema.to_schema()


async def test_tracker_response_has_discriminator(schema: dict) -> None:
    """Verify tracker responses name the variant by its `type` tag."""
    # Given the refined schema
    response = schema["paths"][_TRACKER_PATH]["get"]["responses"]["200"]

    # When reading the response body schema
    body = response["content"]["application/json"]["schema"]

    # Then the union is discriminated on `type`
    assert body["discriminator"] == {"propertyName": "type", "mapping": _TRACKER_MAPPING}


async def test_nullable_tracker_field_has_discriminator(schema: dict) -> None:
    """Verify the nullable `tracker` field keeps null outside the discriminated union."""
    # Given the refined schema
    components = schema["components"]["schemas"]

    # When reading the tracker field of a character trait
    tracker = components["CharacterTraitResponse"]["properties"]["tracker"]

    # Then it is a discriminated union or null
    union, null = tracker["oneOf"]
    assert union["discriminator"] == {"propertyName": "type", "mapping": _TRACKER_MAPPING}
    assert null == {"type": "null"}


async def test_optional_constrained_fields_keep_minimum(schema: dict) -> None:
    """Verify nullable tracker state fields still document `minimum: 0`."""
    # Given the refined schema
    properties = schema["components"]["schemas"]["TrackerStateSet"]["properties"]

    # When reading the integer branch of each field
    minimums = {
        name: next(b for b in prop["oneOf"] if b.get("type") == "integer").get("minimum")
        for name, prop in properties.items()
    }

    # Then every field has a minimum of 0
    assert minimums == dict.fromkeys(("current", "superficial", "aggravated", "stains"), 0.0)


def test_app_registers_refine_hook() -> None:
    """Verify the app factory runs the schema refinement on startup."""
    # Given the app factory
    # When the app is created
    app = create_app()

    # Then the refinement hook is registered as a startup handler
    assert refine_openapi_schema in app.on_startup
