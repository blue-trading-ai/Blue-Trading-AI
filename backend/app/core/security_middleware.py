from __future__ import annotations

import re
import secrets
import time
from collections.abc import Awaitable, Callable
from typing import Final

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import (
    ASGIApp,
    Message,
    Receive,
    Scope,
    Send,
)

from app.core.config import settings


REQUEST_ID_HEADER: Final[str] = "X-Request-ID"
PROCESS_TIME_HEADER: Final[str] = "X-Process-Time-Ms"

MAX_REQUEST_BODY_BYTES: Final[int] = (
    2 * 1024 * 1024
)

MAX_REQUEST_ID_LENGTH: Final[int] = 128

REQUEST_ID_PATTERN = re.compile(
    r"^[A-Za-z0-9._:-]+$"
)

SENSITIVE_PATH_PREFIXES: Final[
    tuple[str, ...]
] = (
    "/auth",
    "/admin",
    "/monitoring",
    "/readiness",
    "/deployment",
)


def _generate_request_id() -> str:
    """Generate one cryptographically secure request identifier."""

    return secrets.token_hex(16)


def _normalise_request_id(
    value: str | None,
) -> str:
    """
    Return one safe request identifier.

    Invalid, oversized, or control-character values are replaced
    rather than reflected into the response.
    """

    resolved = str(
        value or ""
    ).strip()

    if (
        not resolved
        or len(resolved)
        > MAX_REQUEST_ID_LENGTH
        or not REQUEST_ID_PATTERN.fullmatch(
            resolved
        )
    ):
        return _generate_request_id()

    return resolved


class SecurityHeadersMiddleware(
    BaseHTTPMiddleware
):
    """
    Add baseline security headers to every Blue-Trading-AI response.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[
            [Request],
            Awaitable[Response],
        ],
    ) -> Response:
        request_id = _normalise_request_id(
            request.headers.get(
                REQUEST_ID_HEADER
            )
        )

        request.state.request_id = (
            request_id
        )

        response = await call_next(
            request
        )

        response.headers[
            REQUEST_ID_HEADER
        ] = request_id

        response.headers[
            "X-Content-Type-Options"
        ] = "nosniff"

        response.headers[
            "X-Frame-Options"
        ] = "DENY"

        response.headers[
            "Referrer-Policy"
        ] = "no-referrer"

        response.headers[
            "Permissions-Policy"
        ] = (
            "camera=(), microphone=(), "
            "geolocation=(), payment=(), "
            "usb=(), browsing-topics=()"
        )

        response.headers[
            "Cross-Origin-Opener-Policy"
        ] = "same-origin"

        response.headers[
            "Cross-Origin-Resource-Policy"
        ] = "same-origin"

        response.headers[
            "X-Permitted-Cross-Domain-Policies"
        ] = "none"

        response.headers[
            "X-DNS-Prefetch-Control"
        ] = "off"

        if settings.is_production:
            response.headers[
                "Strict-Transport-Security"
            ] = (
                "max-age=31536000; "
                "includeSubDomains"
            )

        request_path = (
            request.url.path
        )

        if request_path.startswith(
            SENSITIVE_PATH_PREFIXES
        ):
            response.headers[
                "Cache-Control"
            ] = (
                "no-store, no-cache, "
                "must-revalidate, private"
            )
            response.headers[
                "Pragma"
            ] = "no-cache"
            response.headers[
                "Expires"
            ] = "0"
        elif (
            "Cache-Control"
            not in response.headers
        ):
            response.headers[
                "Cache-Control"
            ] = "no-cache"

        return response


class RequestBodyLimitMiddleware:
    """
    Enforce a maximum request-body size for both fixed-length and
    chunked requests.

    The body is buffered only up to the configured limit and then
    replayed to the downstream FastAPI application.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        max_body_bytes: int = (
            MAX_REQUEST_BODY_BYTES
        ),
    ) -> None:
        self.app = app

        if isinstance(
            max_body_bytes,
            bool,
        ):
            raise ValueError(
                "Maximum request body size must be an integer."
            )

        try:
            resolved_max_body_bytes = int(
                max_body_bytes
            )
        except (
            TypeError,
            ValueError,
            OverflowError,
        ) as exc:
            raise ValueError(
                "Maximum request body size must be an integer."
            ) from exc

        if resolved_max_body_bytes < 1:
            raise ValueError(
                "Maximum request body size must be positive."
            )

        self.max_body_bytes = (
            resolved_max_body_bytes
        )

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(
                scope,
                receive,
                send,
            )
            return

        headers = {
            key.decode(
                "latin-1"
            ).lower(): value.decode(
                "latin-1"
            )
            for key, value in scope.get(
                "headers",
                [],
            )
        }

        content_length = headers.get(
            "content-length"
        )

        if content_length is not None:
            if (
                not content_length
                or not content_length.isascii()
                or not content_length.isdecimal()
            ):
                await self._send_error(
                    scope,
                    receive,
                    send,
                    status_code=400,
                    content={
                        "detail": (
                            "Invalid Content-Length header."
                        ),
                    },
                )
                return

            try:
                resolved_length = int(
                    content_length,
                    10,
                )
            except (
                TypeError,
                ValueError,
                OverflowError,
            ):
                await self._send_error(
                    scope,
                    receive,
                    send,
                    status_code=400,
                    content={
                        "detail": (
                            "Invalid Content-Length header."
                        ),
                    },
                )
                return

            if (
                resolved_length
                > self.max_body_bytes
            ):
                await self._send_too_large(
                    scope,
                    receive,
                    send,
                )
                return

        body_parts: list[bytes] = []
        total_size = 0
        disconnected = False

        while True:
            message = await receive()

            message_type = message.get(
                "type"
            )

            if (
                message_type
                == "http.disconnect"
            ):
                disconnected = True
                break

            if (
                message_type
                != "http.request"
            ):
                continue

            body = message.get(
                "body",
                b"",
            )

            total_size += len(body)

            if (
                total_size
                > self.max_body_bytes
            ):
                await self._send_too_large(
                    scope,
                    receive,
                    send,
                )
                return

            if body:
                body_parts.append(
                    body
                )

            if not message.get(
                "more_body",
                False,
            ):
                break

        if disconnected:
            return

        complete_body = b"".join(
            body_parts
        )

        body_sent = False

        async def replay_receive() -> Message:
            nonlocal body_sent

            if body_sent:
                return {
                    "type": "http.request",
                    "body": b"",
                    "more_body": False,
                }

            body_sent = True

            return {
                "type": "http.request",
                "body": complete_body,
                "more_body": False,
            }

        await self.app(
            scope,
            replay_receive,
            send,
        )

    async def _send_too_large(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        await self._send_error(
            scope,
            receive,
            send,
            status_code=413,
            content={
                "detail": (
                    "Request body is too large."
                ),
                "maximum_bytes": (
                    self.max_body_bytes
                ),
            },
        )

    @staticmethod
    async def _send_error(
        scope: Scope,
        receive: Receive,
        send: Send,
        *,
        status_code: int,
        content: dict[str, object],
    ) -> None:
        response = JSONResponse(
            status_code=status_code,
            content=content,
        )

        await response(
            scope,
            receive,
            send,
        )


class RequestTimingMiddleware(
    BaseHTTPMiddleware
):
    """
    Measure request processing time without exposing internals.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[
            [Request],
            Awaitable[Response],
        ],
    ) -> Response:
        started = time.perf_counter()

        response = await call_next(
            request
        )

        elapsed_ms = (
            time.perf_counter()
            - started
        ) * 1000.0

        response.headers[
            PROCESS_TIME_HEADER
        ] = f"{elapsed_ms:.2f}"

        return response


__all__ = [
    "MAX_REQUEST_BODY_BYTES",
    "MAX_REQUEST_ID_LENGTH",
    "PROCESS_TIME_HEADER",
    "REQUEST_ID_HEADER",
    "REQUEST_ID_PATTERN",
    "RequestBodyLimitMiddleware",
    "RequestTimingMiddleware",
    "SecurityHeadersMiddleware",
]