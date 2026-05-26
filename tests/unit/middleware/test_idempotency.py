"""Unit tests for idempotency middleware scope-state behavior."""

from litestar import Litestar, Request, post
from litestar.testing import TestClient

from vapi.constants import IDEMPOTENCY_KEY_HEADER, IDEMPOTENCY_KEY_STATE_KEY
from vapi.middleware.idempotency import idempotency_middleware


@post("/thing")
async def _create(data: dict, request: Request) -> dict:
    """Echo back whatever idempotency key the middleware stashed on scope state."""
    return {"stashed": request.scope["state"].get(IDEMPOTENCY_KEY_STATE_KEY)}


def _build_app() -> Litestar:
    return Litestar(route_handlers=[_create], middleware=[idempotency_middleware])


def test_idempotency_key_stashed_on_scope_state() -> None:
    """Verify the idempotency key is written to scope state for downstream logging."""
    # Given an app with the idempotency middleware and a route that reads scope state
    app = _build_app()

    # When a POST carries an Idempotency-Key header
    with TestClient(app=app) as client:
        response = client.post("/thing", json={"x": 1}, headers={IDEMPOTENCY_KEY_HEADER: "idem-1"})

    # Then the key is present on scope state during handler execution
    assert response.json()["stashed"] == "idem-1"


def test_idempotency_key_absent_when_header_missing() -> None:
    """Verify scope state has no idempotency key when the header is absent."""
    # Given an app with the idempotency middleware
    app = _build_app()

    # When a POST carries no Idempotency-Key header
    with TestClient(app=app) as client:
        response = client.post("/thing", json={"x": 1})

    # Then no idempotency key is stashed
    assert response.json()["stashed"] is None
