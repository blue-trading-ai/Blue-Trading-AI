from __future__ import annotations

import math
import threading
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


RATE_LIMIT_HEADER_LIMIT: Final[str] = "X-RateLimit-Limit"
RATE_LIMIT_HEADER_REMAINING: Final[str] = "X-RateLimit-Remaining"
RATE_LIMIT_HEADER_RESET: Final[str] = "X-RateLimit-Reset"
RATE_LIMIT_HEADER_RULE: Final[str] = "X-RateLimit-Rule"
RETRY_AFTER_HEADER: Final[str] = "Retry-After"

MAX_CLIENT_KEY_LENGTH: Final[int] = 128
MAX_RATE_LIMIT_BUCKETS: Final[int] = 100_000
BUCKET_CLEANUP_INTERVAL_SECONDS: Final[int] = 60


@dataclass(frozen=True)
class RateLimitRule:
    """
    Define one sliding-window request limit.
    """

    name: str
    requests: int
    window_seconds: int

    def __post_init__(self) -> None:
        resolved_name = str(
            self.name or ""
        ).strip()

        if not resolved_name:
            raise ValueError(
                "Rate-limit rule name cannot be empty."
            )

        if ":" in resolved_name:
            raise ValueError(
                "Rate-limit rule name cannot contain ':'."
            )

        if isinstance(
            self.requests,
            bool,
        ):
            raise ValueError(
                "Rate-limit request count must be an integer."
            )

        if isinstance(
            self.window_seconds,
            bool,
        ):
            raise ValueError(
                "Rate-limit window must be an integer."
            )

        try:
            resolved_requests = int(
                self.requests
            )
            resolved_window_seconds = int(
                self.window_seconds
            )
        except (
            TypeError,
            ValueError,
            OverflowError,
        ) as exc:
            raise ValueError(
                "Rate-limit values must be integers."
            ) from exc

        if resolved_requests < 1:
            raise ValueError(
                "Rate-limit request count must be positive."
            )

        if resolved_window_seconds < 1:
            raise ValueError(
                "Rate-limit window must be positive."
            )

        object.__setattr__(
            self,
            "name",
            resolved_name,
        )
        object.__setattr__(
            self,
            "requests",
            resolved_requests,
        )
        object.__setattr__(
            self,
            "window_seconds",
            resolved_window_seconds,
        )


GENERAL_API_RULE = RateLimitRule(
    name="general",
    requests=120,
    window_seconds=60,
)

LOGIN_RULE = RateLimitRule(
    name="login",
    requests=10,
    window_seconds=60,
)

REGISTER_RULE = RateLimitRule(
    name="register",
    requests=5,
    window_seconds=300,
)

PASSWORD_CHANGE_RULE = RateLimitRule(
    name="password-change",
    requests=5,
    window_seconds=300,
)

ACCOUNT_RECOVERY_RULE = RateLimitRule(
    name="account-recovery",
    requests=5,
    window_seconds=300,
)

ADMIN_RULE = RateLimitRule(
    name="admin",
    requests=60,
    window_seconds=60,
)


class InMemoryRateLimiter:
    """
    Thread-safe in-memory sliding-window rate limiter.

    Suitable for one backend process. A shared Redis-backed limiter
    is required when multiple backend instances are deployed.
    """

    def __init__(
        self,
        *,
        max_buckets: int = MAX_RATE_LIMIT_BUCKETS,
        cleanup_interval_seconds: int = (
            BUCKET_CLEANUP_INTERVAL_SECONDS
        ),
    ) -> None:
        self._requests: dict[
            str,
            deque[float],
        ] = defaultdict(deque)

        self._lock = threading.Lock()

        if isinstance(
            max_buckets,
            bool,
        ):
            raise ValueError(
                "Maximum rate-limit buckets must be an integer."
            )

        if isinstance(
            cleanup_interval_seconds,
            bool,
        ):
            raise ValueError(
                "Cleanup interval must be an integer."
            )

        try:
            resolved_max_buckets = int(
                max_buckets
            )
            resolved_cleanup_interval = int(
                cleanup_interval_seconds
            )
        except (
            TypeError,
            ValueError,
            OverflowError,
        ) as exc:
            raise ValueError(
                "Rate-limiter configuration must use integers."
            ) from exc

        if resolved_max_buckets < 1:
            raise ValueError(
                "Maximum rate-limit buckets must be positive."
            )

        if resolved_cleanup_interval < 1:
            raise ValueError(
                "Cleanup interval must be positive."
            )

        self._max_buckets = resolved_max_buckets
        self._cleanup_interval_seconds = (
            resolved_cleanup_interval
        )

        self._last_cleanup = time.monotonic()

    def check(
        self,
        *,
        key: str,
        rule: RateLimitRule,
    ) -> tuple[bool, int, int]:
        """
        Return:
        - whether the request is allowed
        - remaining requests
        - reset or retry time in seconds
        """

        now = time.monotonic()
        cutoff = now - rule.window_seconds

        resolved_key = self._normalise_key(
            key
        )

        bucket_key = (
            f"{rule.name}:{resolved_key}"
        )

        with self._lock:
            self._cleanup_if_due(
                now
            )

            if (
                bucket_key
                not in self._requests
                and len(self._requests)
                >= self._max_buckets
            ):
                self._evict_oldest_bucket()

            bucket = self._requests[
                bucket_key
            ]

            while (
                bucket
                and bucket[0] <= cutoff
            ):
                bucket.popleft()

            if (
                len(bucket)
                >= rule.requests
            ):
                oldest_request = bucket[0]

                retry_after = max(
                    math.ceil(
                        rule.window_seconds
                        - (
                            now
                            - oldest_request
                        )
                    ),
                    1,
                )

                return (
                    False,
                    0,
                    retry_after,
                )

            bucket.append(now)

            remaining = max(
                rule.requests
                - len(bucket),
                0,
            )

            reset_after = max(
                math.ceil(
                    rule.window_seconds
                    - (
                        now
                        - bucket[0]
                    )
                ),
                1,
            )

            return (
                True,
                remaining,
                reset_after,
            )

    def clear(self) -> None:
        """
        Clear all in-memory rate-limit state.
        """

        with self._lock:
            self._requests.clear()
            self._last_cleanup = (
                time.monotonic()
            )

    @staticmethod
    def _normalise_key(
        key: str,
    ) -> str:
        resolved = str(
            key or "unknown"
        ).strip()

        if not resolved:
            resolved = "unknown"

        return resolved[
            :MAX_CLIENT_KEY_LENGTH
        ]

    def _cleanup_if_due(
        self,
        now: float,
    ) -> None:
        if (
            now - self._last_cleanup
            < self._cleanup_interval_seconds
        ):
            return

        empty_keys: list[str] = []

        for bucket_key, bucket in (
            self._requests.items()
        ):
            rule_window = (
                self._window_for_bucket(
                    bucket_key
                )
            )

            cutoff = now - rule_window

            while (
                bucket
                and bucket[0] <= cutoff
            ):
                bucket.popleft()

            if not bucket:
                empty_keys.append(
                    bucket_key
                )

        for bucket_key in empty_keys:
            self._requests.pop(
                bucket_key,
                None,
            )

        self._last_cleanup = now

    @staticmethod
    def _window_for_bucket(
        bucket_key: str,
    ) -> int:
        rule_name = bucket_key.split(
            ":",
            1,
        )[0]

        windows = {
            GENERAL_API_RULE.name: (
                GENERAL_API_RULE.window_seconds
            ),
            LOGIN_RULE.name: (
                LOGIN_RULE.window_seconds
            ),
            REGISTER_RULE.name: (
                REGISTER_RULE.window_seconds
            ),
            PASSWORD_CHANGE_RULE.name: (
                PASSWORD_CHANGE_RULE.window_seconds
            ),
            ACCOUNT_RECOVERY_RULE.name: (
                ACCOUNT_RECOVERY_RULE.window_seconds
            ),
            ADMIN_RULE.name: (
                ADMIN_RULE.window_seconds
            ),
        }

        return windows.get(
            rule_name,
            GENERAL_API_RULE.window_seconds,
        )

    def _evict_oldest_bucket(
        self,
    ) -> None:
        oldest_key: str | None = None
        oldest_timestamp = float("inf")

        for bucket_key, bucket in (
            self._requests.items()
        ):
            if not bucket:
                oldest_key = bucket_key
                break

            if (
                bucket[0]
                < oldest_timestamp
            ):
                oldest_timestamp = (
                    bucket[0]
                )
                oldest_key = bucket_key

        if oldest_key is not None:
            self._requests.pop(
                oldest_key,
                None,
            )


rate_limiter = InMemoryRateLimiter()


def _client_ip(
    request: Request,
) -> str:
    """
    Resolve the direct ASGI client address.

    X-Forwarded-For is intentionally not trusted here. A production
    reverse proxy must be configured so the ASGI server receives the
    trusted client address.
    """

    if request.client is not None:
        resolved = str(
            request.client.host or ""
        ).strip()

        if resolved:
            return resolved[
                :MAX_CLIENT_KEY_LENGTH
            ]

    return "unknown"


def _select_rule(
    request: Request,
) -> RateLimitRule:
    """
    Select the strictest matching route rule.
    """

    path = (
        request.url.path.rstrip("/")
        or "/"
    )

    method = request.method.upper()

    if (
        path == "/auth/login"
        and method == "POST"
    ):
        return LOGIN_RULE

    if (
        path == "/auth/register"
        and method == "POST"
    ):
        return REGISTER_RULE

    if (
        path
        == "/auth/change-password"
        and method == "POST"
    ):
        return PASSWORD_CHANGE_RULE

    if (
        method == "POST"
        and path in {
            "/auth/request-email-verification",
            "/auth/forgot-password",
            "/auth/verify-email",
            "/auth/reset-password",
        }
    ):
        return ACCOUNT_RECOVERY_RULE

    if path.startswith(
        "/admin"
    ):
        return ADMIN_RULE

    return GENERAL_API_RULE


def _rate_limit_headers(
    *,
    rule: RateLimitRule,
    remaining: int,
    reset_after: int,
    include_retry_after: bool = False,
) -> dict[str, str]:
    """
    Build consistent rate-limit response headers.
    """

    headers = {
        RATE_LIMIT_HEADER_LIMIT: str(
            rule.requests
        ),
        RATE_LIMIT_HEADER_REMAINING: str(
            max(
                int(remaining),
                0,
            )
        ),
        RATE_LIMIT_HEADER_RESET: str(
            max(
                int(reset_after),
                1,
            )
        ),
        RATE_LIMIT_HEADER_RULE: (
            rule.name
        ),
    }

    if include_retry_after:
        headers[
            RETRY_AFTER_HEADER
        ] = str(
            max(
                int(reset_after),
                1,
            )
        )

    return headers


class RateLimitMiddleware(
    BaseHTTPMiddleware
):
    """
    Apply route-aware IP rate limiting.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[
            [Request],
            Awaitable[Response],
        ],
    ) -> Response:
        if request.method.upper() == "OPTIONS":
            return await call_next(
                request
            )

        rule = _select_rule(
            request
        )

        client_ip = _client_ip(
            request
        )

        (
            allowed,
            remaining,
            reset_after,
        ) = rate_limiter.check(
            key=client_ip,
            rule=rule,
        )

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        "Too many requests. "
                        "Please try again later."
                    ),
                    "rate_limit_rule": (
                        rule.name
                    ),
                    "retry_after_seconds": (
                        reset_after
                    ),
                },
                headers=(
                    _rate_limit_headers(
                        rule=rule,
                        remaining=0,
                        reset_after=(
                            reset_after
                        ),
                        include_retry_after=True,
                    )
                ),
            )

        response = await call_next(
            request
        )

        headers = _rate_limit_headers(
            rule=rule,
            remaining=remaining,
            reset_after=reset_after,
        )

        for (
            header_name,
            header_value,
        ) in headers.items():
            response.headers[
                header_name
            ] = header_value

        return response


__all__ = [
    "ACCOUNT_RECOVERY_RULE",
    "ADMIN_RULE",
    "BUCKET_CLEANUP_INTERVAL_SECONDS",
    "GENERAL_API_RULE",
    "InMemoryRateLimiter",
    "LOGIN_RULE",
    "MAX_CLIENT_KEY_LENGTH",
    "MAX_RATE_LIMIT_BUCKETS",
    "PASSWORD_CHANGE_RULE",
    "RATE_LIMIT_HEADER_LIMIT",
    "RATE_LIMIT_HEADER_REMAINING",
    "RATE_LIMIT_HEADER_RESET",
    "RATE_LIMIT_HEADER_RULE",
    "REGISTER_RULE",
    "RETRY_AFTER_HEADER",
    "RateLimitMiddleware",
    "RateLimitRule",
    "rate_limiter",
]