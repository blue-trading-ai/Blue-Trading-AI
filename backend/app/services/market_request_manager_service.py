from __future__ import annotations

import asyncio
import inspect
import math
import time
from collections import defaultdict
from threading import RLock
from typing import Any, Awaitable, Callable, Final

from app.services.market_cache_service import (
    MAX_TTL_SECONDS,
    build_cache_key,
    cache_market_data,
    get_cached_market_data,
    normalize_symbol,
    normalize_timeframe,
)


REQUEST_MANAGER_VERSION: Final[int] = 22

ProviderFunction = Callable[
    [str, str],
    dict[str, Any] | Awaitable[dict[str, Any]],
]


PROVIDER_TIMEFRAME_MAP: Final[dict[str, str]] = {
    "M5": "5min",
    "M15": "15min",
    "M30": "30min",
    "H1": "1h",
    "H4": "4h",
    "D1": "1day",
    "W1": "1week",
    "MN": "1month",
}


RATE_LIMIT_ERROR_MARKERS: Final[tuple[str, ...]] = (
    "429",
    "too many requests",
    "rate limit",
    "rate-limit",
    "api limit",
    "request limit",
    "credits limit",
)


MAXIMUM_RETRIES: Final[int] = 5
MAXIMUM_REQUEST_INTERVAL_SECONDS: Final[float] = 60.0
MAXIMUM_RETRY_DELAY_SECONDS: Final[float] = 300.0
MAXIMUM_PROVIDER_TIMEOUT_SECONDS: Final[float] = 120.0
DEFAULT_PROVIDER_TIMEOUT_SECONDS: Final[float] = 30.0
MAXIMUM_TRACKED_SYMBOLS: Final[int] = 500
MAXIMUM_TRACKED_TIMEFRAMES: Final[int] = 100
MAX_PROVIDER_NAME_LENGTH: Final[int] = 80
MAX_COUNTER_VALUE: Final[int] = 9_223_372_036_854_775_000


class MarketRequestManagerError(RuntimeError):
    """Base error for managed market-data requests."""


class MarketProviderUnavailableError(
    MarketRequestManagerError
):
    pass


class MarketProviderResponseError(
    MarketRequestManagerError
):
    pass


def _increment_counter(
    value: int,
    amount: int = 1,
) -> int:
    return min(
        MAX_COUNTER_VALUE,
        max(
            0,
            int(value or 0)
            + int(amount or 0),
        ),
    )


def _bounded_float(
    value: Any,
    *,
    field_name: str,
    minimum: float,
    maximum: float,
) -> float:
    try:
        resolved = float(value)
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            f"{field_name} must be numeric."
        ) from exc

    if not math.isfinite(
        resolved
    ):
        raise ValueError(
            f"{field_name} must be finite."
        )

    if not minimum <= resolved <= maximum:
        raise ValueError(
            f"{field_name} must be between "
            f"{minimum} and {maximum}."
        )

    return resolved


def _bounded_int(
    value: Any,
    *,
    field_name: str,
    minimum: int,
    maximum: int,
) -> int:
    try:
        resolved = int(value)
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            f"{field_name} must be an integer."
        ) from exc

    if not minimum <= resolved <= maximum:
        raise ValueError(
            f"{field_name} must be between "
            f"{minimum} and {maximum}."
        )

    return resolved


def _is_rate_limit_error(
    error: Exception | str,
) -> bool:
    message = str(
        error
    ).lower()

    return any(
        marker in message
        for marker in RATE_LIMIT_ERROR_MARKERS
    )


def _safe_provider_name(
    value: str,
) -> str:
    cleaned = "".join(
        character
        if character.isprintable()
        and character not in {
            "\r",
            "\n",
            "\t",
        }
        else " "
        for character in str(
            value or ""
        )
    ).strip()

    return (
        cleaned[
            :MAX_PROVIDER_NAME_LENGTH
        ]
        or "market-provider"
    )


def _get_default_market_provider() -> ProviderFunction:
    """
    Import the provider lazily to avoid startup import cycles.
    """

    try:
        from app.market.provider import get_market_data
    except ImportError as exc:
        raise MarketProviderUnavailableError(
            "Market-data provider is unavailable."
        ) from exc

    if not callable(
        get_market_data
    ):
        raise MarketProviderUnavailableError(
            "Market-data provider is invalid."
        )

    return get_market_data


def _validate_provider_payload(
    payload: Any,
    *,
    symbol: str,
    timeframe: str,
) -> dict[str, Any]:
    del symbol, timeframe

    if payload is None:
        raise MarketProviderResponseError(
            "Market provider returned no data."
        )

    if not isinstance(
        payload,
        dict,
    ):
        raise MarketProviderResponseError(
            "Market provider response must be an object."
        )

    if not payload:
        raise MarketProviderResponseError(
            "Market provider returned an empty response."
        )

    if payload.get(
        "error"
    ):
        raise MarketProviderResponseError(
            "Market provider reported an error."
        )

    provider_status = str(
        payload.get(
            "status",
            "",
        )
    ).strip().lower()

    if provider_status in {
        "error",
        "failed",
        "failure",
        "blocked",
    }:
        raise MarketProviderResponseError(
            "Market provider request failed."
        )

    return payload


async def _execute_provider(
    provider: ProviderFunction,
    symbol: str,
    provider_timeframe: str,
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    result = provider(
        symbol,
        provider_timeframe,
    )

    if inspect.isawaitable(
        result
    ):
        try:
            result = await asyncio.wait_for(
                result,
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise MarketProviderUnavailableError(
                "Market provider request timed out."
            ) from exc

    return result


class MarketRequestManager:
    def __init__(
        self,
        *,
        minimum_request_interval_seconds: float = 1.0,
        maximum_retries: int = 2,
        retry_delay_seconds: float = 2.0,
        provider_timeout_seconds: float = (
            DEFAULT_PROVIDER_TIMEOUT_SECONDS
        ),
    ) -> None:
        self.minimum_request_interval_seconds = (
            _bounded_float(
                minimum_request_interval_seconds,
                field_name=(
                    "Minimum request interval"
                ),
                minimum=0.0,
                maximum=(
                    MAXIMUM_REQUEST_INTERVAL_SECONDS
                ),
            )
        )

        self.maximum_retries = _bounded_int(
            maximum_retries,
            field_name="Maximum retries",
            minimum=0,
            maximum=MAXIMUM_RETRIES,
        )

        self.retry_delay_seconds = _bounded_float(
            retry_delay_seconds,
            field_name="Retry delay",
            minimum=0.0,
            maximum=(
                MAXIMUM_RETRY_DELAY_SECONDS
            ),
        )

        self.provider_timeout_seconds = (
            _bounded_float(
                provider_timeout_seconds,
                field_name=(
                    "Provider timeout"
                ),
                minimum=1.0,
                maximum=(
                    MAXIMUM_PROVIDER_TIMEOUT_SECONDS
                ),
            )
        )

        self._state_lock = RLock()
        self._request_locks: dict[
            str,
            asyncio.Lock,
        ] = {}

        self._throttle_lock: (
            asyncio.Lock | None
        ) = None

        self._last_provider_request_at = 0.0

        self._cache_hits = 0
        self._provider_requests = 0
        self._successful_provider_requests = 0
        self._failed_provider_requests = 0
        self._rate_limit_errors = 0
        self._retry_attempts = 0

        self._symbol_requests: dict[
            str,
            int,
        ] = defaultdict(int)

        self._timeframe_requests: dict[
            str,
            int,
        ] = defaultdict(int)

    def _get_throttle_lock(
        self,
    ) -> asyncio.Lock:
        with self._state_lock:
            if self._throttle_lock is None:
                self._throttle_lock = (
                    asyncio.Lock()
                )

            return self._throttle_lock

    def _get_request_lock(
        self,
        cache_key: str,
    ) -> asyncio.Lock:
        with self._state_lock:
            existing_lock = (
                self._request_locks.get(
                    cache_key
                )
            )

            if existing_lock is None:
                existing_lock = (
                    asyncio.Lock()
                )

                self._request_locks[
                    cache_key
                ] = existing_lock

            return existing_lock

    def _remove_request_lock(
        self,
        cache_key: str,
        lock: asyncio.Lock,
    ) -> None:
        with self._state_lock:
            current = (
                self._request_locks.get(
                    cache_key
                )
            )

            if (
                current is lock
                and not lock.locked()
            ):
                self._request_locks.pop(
                    cache_key,
                    None,
                )

    def _increment_named_counter(
        self,
        mapping: dict[str, int],
        key: str,
        *,
        maximum_keys: int,
    ) -> None:
        if key in mapping:
            mapping[key] = (
                _increment_counter(
                    mapping[key]
                )
            )

            return

        if len(mapping) < maximum_keys:
            mapping[key] = 1
            return

        mapping["__OTHER__"] = (
            _increment_counter(
                mapping.get(
                    "__OTHER__",
                    0,
                )
            )
        )

    async def _apply_request_throttle(
        self,
    ) -> None:
        """
        Serialize the sleep and timestamp update globally.

        This prevents concurrent provider calls from passing the
        configured minimum interval together.
        """

        lock = self._get_throttle_lock()

        async with lock:
            elapsed = (
                time.monotonic()
                - self._last_provider_request_at
            )

            remaining_delay = (
                self.minimum_request_interval_seconds
                - elapsed
            )

            if remaining_delay > 0:
                await asyncio.sleep(
                    remaining_delay
                )

            self._last_provider_request_at = (
                time.monotonic()
            )

    def _cache_result(
        self,
        payload: dict[str, Any],
        *,
        source: str,
        symbol: str,
        timeframe: str,
        stale: bool = False,
    ) -> dict[str, Any]:
        return {
            **payload,
            "_request_manager": {
                "source": source,
                "symbol": symbol,
                "timeframe": timeframe,
                "stale": stale,
            },
        }

    async def get_market_data(
        self,
        symbol: str,
        timeframe: str,
        *,
        force_refresh: bool = False,
        allow_stale_on_error: bool = True,
        provider: ProviderFunction | None = None,
        provider_name: str = "TwelveData",
        ttl_seconds: int | None = None,
    ) -> dict[str, Any]:
        normalized_symbol = normalize_symbol(
            symbol
        )

        normalized_timeframe = (
            normalize_timeframe(
                timeframe
            )
        )

        cache_key = build_cache_key(
            normalized_symbol,
            normalized_timeframe,
        )

        if ttl_seconds is not None:
            _bounded_int(
                ttl_seconds,
                field_name="Cache TTL",
                minimum=1,
                maximum=MAX_TTL_SECONDS,
            )

        if not force_refresh:
            cached_payload = (
                get_cached_market_data(
                    normalized_symbol,
                    normalized_timeframe,
                )
            )

            if cached_payload is not None:
                with self._state_lock:
                    self._cache_hits = (
                        _increment_counter(
                            self._cache_hits
                        )
                    )

                return self._cache_result(
                    cached_payload,
                    source="cache",
                    symbol=normalized_symbol,
                    timeframe=(
                        normalized_timeframe
                    ),
                )

        request_lock = (
            self._get_request_lock(
                cache_key
            )
        )

        try:
            async with request_lock:
                if not force_refresh:
                    cached_payload = (
                        get_cached_market_data(
                            normalized_symbol,
                            normalized_timeframe,
                        )
                    )

                    if cached_payload is not None:
                        with self._state_lock:
                            self._cache_hits = (
                                _increment_counter(
                                    self._cache_hits
                                )
                            )

                        return self._cache_result(
                            cached_payload,
                            source=(
                                "cache_after_wait"
                            ),
                            symbol=(
                                normalized_symbol
                            ),
                            timeframe=(
                                normalized_timeframe
                            ),
                        )

                stale_payload = (
                    get_cached_market_data(
                        normalized_symbol,
                        normalized_timeframe,
                        allow_expired=True,
                    )
                )

                selected_provider = (
                    provider
                    if provider is not None
                    else _get_default_market_provider()
                )

                if not callable(
                    selected_provider
                ):
                    raise ValueError(
                        "Market provider must be callable."
                    )

                resolved_provider_name = (
                    _safe_provider_name(
                        provider_name
                    )
                )

                provider_timeframe = (
                    PROVIDER_TIMEFRAME_MAP.get(
                        normalized_timeframe
                    )
                )

                if provider_timeframe is None:
                    raise ValueError(
                        "Provider timeframe mapping is unavailable."
                    )

                last_error: (
                    Exception | None
                ) = None

                total_attempts = (
                    self.maximum_retries
                    + 1
                )

                for attempt_number in range(
                    1,
                    total_attempts + 1,
                ):
                    try:
                        await (
                            self._apply_request_throttle()
                        )

                        with self._state_lock:
                            self._provider_requests = (
                                _increment_counter(
                                    self._provider_requests
                                )
                            )

                            self._increment_named_counter(
                                self._symbol_requests,
                                normalized_symbol,
                                maximum_keys=(
                                    MAXIMUM_TRACKED_SYMBOLS
                                ),
                            )

                            self._increment_named_counter(
                                self._timeframe_requests,
                                normalized_timeframe,
                                maximum_keys=(
                                    MAXIMUM_TRACKED_TIMEFRAMES
                                ),
                            )

                        provider_payload = (
                            await _execute_provider(
                                selected_provider,
                                normalized_symbol,
                                provider_timeframe,
                                timeout_seconds=(
                                    self.provider_timeout_seconds
                                ),
                            )
                        )

                        validated_payload = (
                            _validate_provider_payload(
                                provider_payload,
                                symbol=(
                                    normalized_symbol
                                ),
                                timeframe=(
                                    normalized_timeframe
                                ),
                            )
                        )

                        cache_market_data(
                            symbol=(
                                normalized_symbol
                            ),
                            timeframe=(
                                normalized_timeframe
                            ),
                            payload=(
                                validated_payload
                            ),
                            provider=(
                                resolved_provider_name
                            ),
                            ttl_seconds=(
                                ttl_seconds
                            ),
                            metadata={
                                "provider_timeframe": (
                                    provider_timeframe
                                ),
                                "request_attempt": (
                                    attempt_number
                                ),
                            },
                        )

                        with self._state_lock:
                            self._successful_provider_requests = (
                                _increment_counter(
                                    self._successful_provider_requests
                                )
                            )

                        return {
                            **validated_payload,
                            "_request_manager": {
                                "source": (
                                    "provider"
                                ),
                                "symbol": (
                                    normalized_symbol
                                ),
                                "timeframe": (
                                    normalized_timeframe
                                ),
                                "attempt": (
                                    attempt_number
                                ),
                                "cached": True,
                                "stale": False,
                            },
                        }

                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        last_error = exc

                        is_rate_limited = (
                            _is_rate_limit_error(
                                exc
                            )
                        )

                        if is_rate_limited:
                            with self._state_lock:
                                self._rate_limit_errors = (
                                    _increment_counter(
                                        self._rate_limit_errors
                                    )
                                )

                        has_more_attempts = (
                            attempt_number
                            < total_attempts
                        )

                        if has_more_attempts:
                            with self._state_lock:
                                self._retry_attempts = (
                                    _increment_counter(
                                        self._retry_attempts
                                    )
                                )

                            delay = min(
                                MAXIMUM_RETRY_DELAY_SECONDS,
                                self.retry_delay_seconds
                                * attempt_number
                                * (
                                    2
                                    if is_rate_limited
                                    else 1
                                ),
                            )

                            if delay > 0:
                                await asyncio.sleep(
                                    delay
                                )

                            continue

                        with self._state_lock:
                            self._failed_provider_requests = (
                                _increment_counter(
                                    self._failed_provider_requests
                                )
                            )

                if (
                    allow_stale_on_error
                    and stale_payload is not None
                ):
                    return self._cache_result(
                        stale_payload,
                        source="stale_cache",
                        symbol=normalized_symbol,
                        timeframe=(
                            normalized_timeframe
                        ),
                        stale=True,
                    )

                raise MarketProviderUnavailableError(
                    "Managed market data is temporarily unavailable."
                ) from last_error
        finally:
            await asyncio.sleep(
                0
            )

            self._remove_request_lock(
                cache_key,
                request_lock,
            )

    def get_statistics(
        self,
    ) -> dict[str, Any]:
        with self._state_lock:
            total_completed = (
                self._successful_provider_requests
                + self._failed_provider_requests
            )

            provider_success_rate = (
                round(
                    (
                        self._successful_provider_requests
                        / total_completed
                    )
                    * 100,
                    2,
                )
                if total_completed > 0
                else 0.0
            )

            return {
                "version": (
                    REQUEST_MANAGER_VERSION
                ),
                "module": (
                    "Smart Market Request Manager"
                ),
                "cache_hits": (
                    self._cache_hits
                ),
                "provider_requests": (
                    self._provider_requests
                ),
                "successful_provider_requests": (
                    self._successful_provider_requests
                ),
                "failed_provider_requests": (
                    self._failed_provider_requests
                ),
                "provider_success_rate_percentage": (
                    provider_success_rate
                ),
                "rate_limit_errors": (
                    self._rate_limit_errors
                ),
                "retry_attempts": (
                    self._retry_attempts
                ),
                "minimum_request_interval_seconds": (
                    self.minimum_request_interval_seconds
                ),
                "maximum_retries": (
                    self.maximum_retries
                ),
                "retry_delay_seconds": (
                    self.retry_delay_seconds
                ),
                "provider_timeout_seconds": (
                    self.provider_timeout_seconds
                ),
                "tracked_symbol_count": len(
                    self._symbol_requests
                ),
                "tracked_timeframe_count": len(
                    self._timeframe_requests
                ),
                "active_request_lock_count": len(
                    self._request_locks
                ),
                "requests_by_symbol": dict(
                    self._symbol_requests
                ),
                "requests_by_timeframe": dict(
                    self._timeframe_requests
                ),
                "broker_connection_enabled": False,
                "trade_execution_enabled": False,
            }

    def reset_statistics(
        self,
    ) -> None:
        with self._state_lock:
            self._cache_hits = 0
            self._provider_requests = 0
            self._successful_provider_requests = 0
            self._failed_provider_requests = 0
            self._rate_limit_errors = 0
            self._retry_attempts = 0

            self._symbol_requests.clear()
            self._timeframe_requests.clear()


market_request_manager = MarketRequestManager(
    minimum_request_interval_seconds=1.0,
    maximum_retries=2,
    retry_delay_seconds=2.0,
    provider_timeout_seconds=(
        DEFAULT_PROVIDER_TIMEOUT_SECONDS
    ),
)


async def get_managed_market_data(
    symbol: str,
    timeframe: str,
    *,
    force_refresh: bool = False,
    allow_stale_on_error: bool = True,
    provider: ProviderFunction | None = None,
    provider_name: str = "TwelveData",
    ttl_seconds: int | None = None,
) -> dict[str, Any]:
    return await (
        market_request_manager.get_market_data(
            symbol=symbol,
            timeframe=timeframe,
            force_refresh=force_refresh,
            allow_stale_on_error=(
                allow_stale_on_error
            ),
            provider=provider,
            provider_name=provider_name,
            ttl_seconds=ttl_seconds,
        )
    )


def get_market_request_statistics() -> dict[str, Any]:
    return (
        market_request_manager.get_statistics()
    )


def reset_market_request_statistics() -> None:
    market_request_manager.reset_statistics()


__all__ = [
    "DEFAULT_PROVIDER_TIMEOUT_SECONDS",
    "MAXIMUM_PROVIDER_TIMEOUT_SECONDS",
    "MAXIMUM_RETRIES",
    "MarketProviderResponseError",
    "MarketProviderUnavailableError",
    "MarketRequestManager",
    "MarketRequestManagerError",
    "PROVIDER_TIMEFRAME_MAP",
    "ProviderFunction",
    "REQUEST_MANAGER_VERSION",
    "get_managed_market_data",
    "get_market_request_statistics",
    "market_request_manager",
    "reset_market_request_statistics",
]