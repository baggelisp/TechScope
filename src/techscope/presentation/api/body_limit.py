"""Refusing an oversized request before it is read, rather than after.

A cap that runs inside the endpoint is not a cap: by the time the route can count domains, the
whole body has arrived, been decoded and been built into a list. Measured, an 8.3 MB body of
400,000 entries costs about 69 MB of resident memory before the 50-domain guard rejects it, and
nothing here or in the server bounds the body by default. On the one endpoint feature 10 exists
to make safe to expose, that is the wrong way round.

So the bound sits outside the application, where it can see the declared length before a byte is
read. A body that declares too much is refused without being read at all; one that declares
nothing — a chunked request — is read here, up to the bound, and refused the moment it passes it.
Reading it here rather than letting it through and counting on the way costs a buffer of at most
the bound and buys one answer for both cases: a caller that sends too much is told the same thing
whether or not it announced how much that was. Nothing served here streams a request body, so
there is nothing to lose by holding it.

The refusal is the same shape every other refusal takes, because a caller should not have to
learn a second error format to discover it sent too much.
"""

import logging

from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from techscope.presentation.api.errors import (
    INVALID_REQUEST,
    STATUS_INVALID_REQUEST,
    build_error_body,
)
from techscope.presentation.api.schemas import MAXIMUM_DOMAIN_LENGTH, MAXIMUM_SUBMITTED_DOMAINS

logger = logging.getLogger(__name__)

HTTP_SCOPE_TYPE = "http"
REQUEST_MESSAGE_TYPE = "http.request"
DISCONNECT_MESSAGE_TYPE = "http.disconnect"
CONTENT_LENGTH_HEADER = b"content-length"

# Quotes, a comma and room for whitespace around each entry in the JSON array.
JSON_OVERHEAD_PER_DOMAIN = 8
# Derived rather than chosen, so the bound cannot drift away from what the endpoint accepts:
# every domain at its maximum length, plus a kilobyte for the object around them.
MAXIMUM_REQUEST_BYTES = (
    MAXIMUM_SUBMITTED_DOMAINS * (MAXIMUM_DOMAIN_LENGTH + JSON_OVERHEAD_PER_DOMAIN) + 1024
)

TOO_LARGE_MESSAGE = f"the request body may be at most {MAXIMUM_REQUEST_BYTES} bytes"


class BodySizeLimitMiddleware:
    """Bounds every request body, by its declared length and by what actually arrives."""

    def __init__(self, app: ASGIApp, maximum_bytes: int = MAXIMUM_REQUEST_BYTES) -> None:
        self._app = app
        self._maximum_bytes = maximum_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != HTTP_SCOPE_TYPE:
            await self._app(scope, receive, send)

            return

        declared = _decide_declared_length_or_none(scope)

        if declared is not None and declared > self._maximum_bytes:
            await _send_refusal(scope, receive, send)

            return

        await self._serve_bounded(scope, receive, send)

    async def _serve_bounded(self, scope: Scope, receive: Receive, send: Send) -> None:
        """No declared length, or one within it: read the body here, then hand it on."""
        body_messages = await _read_bounded_body_or_none(receive, self._maximum_bytes)

        if body_messages is None:
            await _send_refusal(scope, receive, send)

            return

        await self._app(scope, _build_replay(body_messages), send)


async def _read_bounded_body_or_none(receive: Receive, maximum_bytes: int) -> list[Message] | None:
    """Every message of one request body, or ``None`` once it has gone past the bound."""
    messages: list[Message] = []
    received_bytes = 0

    while True:
        message = await receive()
        messages.append(message)

        if message["type"] != REQUEST_MESSAGE_TYPE:
            return messages

        received_bytes += _decide_body_length(message)

        if received_bytes > maximum_bytes:
            return None

        if not message.get("more_body", False):
            return messages


def _build_replay(messages: list[Message]) -> Receive:
    """Hands the application the body that was already read, one message at a time."""
    remaining = list(messages)

    async def replay() -> Message:
        if len(remaining) > 0:
            return remaining.pop(0)

        return {"type": DISCONNECT_MESSAGE_TYPE}

    return replay


def _decide_body_length(message: Message) -> int:
    body = message.get("body", b"")

    if not isinstance(body, bytes):
        return 0

    return len(body)


def _decide_declared_length_or_none(scope: Scope) -> int | None:
    """What the caller says it is about to send, which is a bound before anything is read."""
    for name, value in scope.get("headers", []):
        if name.lower() != CONTENT_LENGTH_HEADER:
            continue

        try:
            return int(value)
        except ValueError:
            return None

    return None


async def _send_refusal(scope: Scope, receive: Receive, send: Send) -> None:
    logger.info("refusing a request body larger than %d bytes", MAXIMUM_REQUEST_BYTES)
    response = JSONResponse(
        status_code=STATUS_INVALID_REQUEST,
        content=build_error_body(INVALID_REQUEST, TOO_LARGE_MESSAGE),
    )

    await response(scope, receive, send)
