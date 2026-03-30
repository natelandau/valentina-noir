"""Request ID middleware.

Generate a unique request ID for every HTTP request and inject it as an
X-Request-Id response header. The ID is also stored on the ASGI scope state
so other middleware, error handlers, and application code can access it.
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

from litestar.datastructures import MutableScopeHeaders
from litestar.enums import ScopeType
from litestar.middleware import ASGIMiddleware

from vapi.constants import REQUEST_ID_HEADER, REQUEST_ID_STATE_KEY

if TYPE_CHECKING:
    from litestar.types import ASGIApp, Message, Receive, Scope, Send

__all__ = ("RequestIdMiddleware", "request_id_middleware")


class RequestIdMiddleware(ASGIMiddleware):
    """Assign a unique request ID to every HTTP request.

    The ID is stored in ``scope["state"]["request_id"]`` and returned to the
    client via the ``X-Request-Id`` response header.
    """

    scopes = (ScopeType.HTTP,)

    async def handle(self, scope: Scope, receive: Receive, send: Send, next_app: ASGIApp) -> None:
        """Generate a request ID, store it on scope, and inject it into the response.

        Args:
            scope: The ASGI connection scope.
            receive: The ASGI receive function.
            send: The ASGI send function.
            next_app: The next ASGI application in the middleware stack to call.
        """
        request_id = f"req_{secrets.token_urlsafe(16)}"
        scope.setdefault("state", {})[REQUEST_ID_STATE_KEY] = request_id

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                headers = MutableScopeHeaders(message)
                headers[REQUEST_ID_HEADER] = request_id

            await send(message)

        await next_app(scope, receive, send_wrapper)


request_id_middleware = RequestIdMiddleware()
