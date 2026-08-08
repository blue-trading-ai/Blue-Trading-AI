from __future__ import annotations

import time
import uuid
from functools import partial
from typing import Any, Final

from anyio import to_thread
from fastapi import Request
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.responses import Response

from app.core.security_middleware import (
    MAX_REQUEST_ID_LENGTH,
    REQUEST_ID_HEADER,
    REQUEST_ID_PATTERN,
)
from app.database.connection import SessionLocal
from app.models.application_event_log import (
    EVENT_TYPE_APPLICATION,
    LOG_LEVEL_ERROR,
)
from app.services.application_logging_service import (
    create_application_event,
    log_http_request,
)


RESPONSE_TIME_HEADER: Final[str] = "X-Response-Time-Ms"

MAX_SAFE_PATH_LENGTH: Final[int] = 500
MAX_QUERY_KEY_LENGTH: Final[int] = 100
MAX_QUERY_VALUE_LENGTH: Final[int] = 200
MAX_QUERY_ITEMS: Final[int] = 50
MAX_CLIENT_IP_LENGTH: Final[int] = 64

EXCLUDED_PATHS: Final[set[str]] = {
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
}

SENSITIVE_QUERY_KEYS: Final[
    tuple[str, ...]
] = (
    "password",
    "passphrase",
    "token",
    "secret",
    "authorization",
    "cookie",
    "api_key",
    "apikey",
    "key",
    "credential",
    "session",
    "jwt",
    "code",
)


def generate_request_id() -> str:
    """Generate one safe request identifier."""

    return (
        "REQ-"
        + uuid.uuid4().hex.upper()
    )


def normalise_request_id(
    value: Any,
) -> str:
    """
    Return one safe request identifier.

    Invalid or oversized values are replaced so untrusted header
    content is never reflected into logs or response headers.
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
        return generate_request_id()

    return resolved


def get_client_ip(
    request: Request,
) -> str | None:
    """
    Resolve the direct ASGI client address.

    X-Forwarded-For and X-Real-IP are intentionally not trusted.
    A production reverse proxy should be configured so the ASGI
    server receives the trusted client address.
    """

    if request.client is None:
        return None

    resolved = str(
        request.client.host or ""
    ).strip()

    if not resolved:
        return None

    return resolved[
        :MAX_CLIENT_IP_LENGTH
    ]


def _is_sensitive_query_key(
    key: str,
) -> bool:
    normalized = str(
        key or ""
    ).strip().lower()

    return any(
        sensitive in normalized
        for sensitive in SENSITIVE_QUERY_KEYS
    )


def _safe_query_component(
    value: Any,
    *,
    maximum_length: int,
) -> str:
    """
    Return one log-safe query component.

    Control characters are removed to prevent log injection.
    """

    resolved = str(
        value or ""
    )

    cleaned = "".join(
        character
        if character.isprintable()
        and character not in {
            "\r",
            "\n",
            "\t",
        }
        else " "
        for character in resolved
    ).strip()

    return cleaned[
        :maximum_length
    ]


def sanitise_path(
    request: Request,
) -> str:
    """
    Build a safe path with redacted sensitive query values.
    """

    base_path = _safe_query_component(
        request.url.path,
        maximum_length=(
            MAX_SAFE_PATH_LENGTH
        ),
    )

    if not request.query_params:
        return base_path

    safe_pairs: list[str] = []

    for key, value in (
        request.query_params.multi_items()
    ):
        safe_key = _safe_query_component(
            key,
            maximum_length=(
                MAX_QUERY_KEY_LENGTH
            ),
        )

        if _is_sensitive_query_key(
            safe_key
        ):
            safe_value = "[REDACTED]"
        else:
            safe_value = (
                _safe_query_component(
                    value,
                    maximum_length=(
                        MAX_QUERY_VALUE_LENGTH
                    ),
                )
            )

        safe_pairs.append(
            f"{safe_key}={safe_value}"
        )

        if (
            len(safe_pairs)
            >= MAX_QUERY_ITEMS
        ):
            break

    if (
        len(request.query_params)
        > MAX_QUERY_ITEMS
    ):
        safe_pairs.append(
            "_truncated=true"
        )

    query_string = "&".join(
        safe_pairs
    )

    full_path = (
        f"{base_path}?{query_string}"
        if query_string
        else base_path
    )

    return full_path[
        :MAX_SAFE_PATH_LENGTH
    ]


def _write_unhandled_exception_event(
    *,
    request_id: str,
    method: str,
    path: str,
    duration_ms: float,
    client_ip: str | None,
    exception_type: str,
    query_count: int,
) -> None:
    """
    Persist one sanitized unhandled-exception event.

    The raw exception message is intentionally excluded because it
    may contain credentials, SQL values, tokens, or provider secrets.
    """

    db = SessionLocal()

    try:
        create_application_event(
            db,
            level=LOG_LEVEL_ERROR,
            event_type=(
                EVENT_TYPE_APPLICATION
            ),
            event_name=(
                "unhandled_http_exception"
            ),
            message=(
                "Unhandled HTTP exception recorded."
            ),
            source=(
                "application_monitoring_middleware"
            ),
            request_id=request_id,
            method=method,
            path=path,
            status_code=500,
            duration_ms=duration_ms,
            client_ip=client_ip,
            exception_type=(
                exception_type
            ),
            exception_message=None,
            metadata={
                "query_count": (
                    query_count
                ),
                "request_body_logged": False,
                "sensitive_headers_logged": False,
                "raw_exception_message_logged": False,
            },
            commit=True,
        )
    except Exception:
        db.rollback()
    finally:
        db.close()


def _write_http_request_event(
    *,
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    client_ip: str | None,
    content_type: str | None,
    query_count: int,
) -> None:
    """Persist one sanitized HTTP request event."""

    db = SessionLocal()

    try:
        log_http_request(
            db,
            request_id=request_id,
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
            client_ip=client_ip,
            metadata={
                "content_type": (
                    _safe_query_component(
                        content_type,
                        maximum_length=200,
                    )
                    or None
                ),
                "query_count": (
                    query_count
                ),
                "request_body_logged": False,
                "authorization_header_logged": False,
                "cookie_header_logged": False,
                "proxy_headers_trusted": False,
            },
            commit=True,
        )
    except Exception:
        db.rollback()
    finally:
        db.close()


class ApplicationMonitoringMiddleware(
    BaseHTTPMiddleware
):
    """
    Production request monitoring.

    Captures:
    - Request ID
    - HTTP method and safe path
    - Response status
    - Response duration
    - Hashed client IP
    - Unhandled exception type

    Never captures:
    - Request body
    - Authorization header
    - Cookie header
    - Passwords or tokens
    - Raw exception messages
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        existing_state_request_id = (
            getattr(
                request.state,
                "request_id",
                None,
            )
        )

        request_id = normalise_request_id(
            existing_state_request_id
            or request.headers.get(
                REQUEST_ID_HEADER
            )
        )

        request.state.request_id = (
            request_id
        )

        started = time.perf_counter()

        safe_path = sanitise_path(
            request
        )

        client_ip = get_client_ip(
            request
        )

        method = str(
            request.method
        ).upper()[:16]

        query_count = len(
            request.query_params
        )

        try:
            response = await call_next(
                request
            )
        except Exception as exc:
            duration_ms = max(
                0.0,
                (
                    time.perf_counter()
                    - started
                )
                * 1000.0,
            )

            try:
                await to_thread.run_sync(
                    partial(
                        _write_unhandled_exception_event,
                        request_id=request_id,
                        method=method,
                        path=safe_path,
                        duration_ms=duration_ms,
                        client_ip=client_ip,
                        exception_type=(
                            type(exc).__name__
                        )[:200],
                        query_count=query_count,
                    )
                )
            except Exception:
                # Monitoring failure must never replace the original
                # application exception.
                pass

            raise

        duration_ms = max(
            0.0,
            (
                time.perf_counter()
                - started
            )
            * 1000.0,
        )

        response.headers[
            REQUEST_ID_HEADER
        ] = request_id

        response.headers[
            RESPONSE_TIME_HEADER
        ] = f"{duration_ms:.2f}"

        if (
            request.url.path
            not in EXCLUDED_PATHS
        ):
            try:
                await to_thread.run_sync(
                    partial(
                        _write_http_request_event,
                        request_id=request_id,
                        method=method,
                        path=safe_path,
                        status_code=int(
                            response.status_code
                        ),
                        duration_ms=duration_ms,
                        client_ip=client_ip,
                        content_type=(
                            response.headers.get(
                                "content-type"
                            )
                        ),
                        query_count=query_count,
                    )
                )
            except Exception:
                # Request processing must not fail because monitoring
                # persistence is unavailable.
                pass

        return response


__all__ = [
    "ApplicationMonitoringMiddleware",
    "EXCLUDED_PATHS",
    "MAX_CLIENT_IP_LENGTH",
    "MAX_QUERY_ITEMS",
    "MAX_REQUEST_ID_LENGTH",
    "REQUEST_ID_HEADER",
    "REQUEST_ID_PATTERN",
    "RESPONSE_TIME_HEADER",
    "SENSITIVE_QUERY_KEYS",
    "generate_request_id",
    "get_client_ip",
    "normalise_request_id",
    "sanitise_path",
]