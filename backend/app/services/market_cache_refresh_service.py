from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Final

from app.services.market_cache_service import (
    market_data_cache,
    normalize_symbol,
    normalize_timeframe,
)
from app.services.market_request_manager_service import (
    get_managed_market_data,
)


CACHE_REFRESH_SERVICE_VERSION: Final[int] = 22

DEFAULT_REFRESH_CHECK_INTERVAL_SECONDS: Final[int] = 60
DEFAULT_REFRESH_BEFORE_EXPIRY_SECONDS: Final[int] = 60

MAX_REFRESH_CHECK_INTERVAL_SECONDS: Final[int] = 86_400
MAX_REFRESH_BEFORE_EXPIRY_SECONDS: Final[int] = 86_400
MAX_REFRESH_SUBSCRIPTIONS: Final[int] = 2_000
MAX_CONCURRENT_REFRESHES: Final[int] = 10
MAX_COUNTER_VALUE: Final[int] = 9_223_372_036_854_775_000

REFRESH_STATUS_SUCCESS: Final[str] = "success"
REFRESH_STATUS_FAILED: Final[str] = "failed"
REFRESH_STATUS_SKIPPED: Final[str] = "skipped"


def utc_now() -> datetime:
    """Return one timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


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


def _safe_failure_message(
    exc: Exception,
) -> str:
    """
    Return a stable failure category without exposing exception text.
    """

    if isinstance(
        exc,
        asyncio.TimeoutError,
    ):
        return "Refresh request timed out."

    if isinstance(
        exc,
        ValueError,
    ):
        return "Refresh configuration is invalid."

    return "Market cache refresh failed."


@dataclass
class RefreshSubscription:
    symbol: str
    timeframe: str
    enabled: bool = True
    refresh_before_expiry_seconds: int = (
        DEFAULT_REFRESH_BEFORE_EXPIRY_SECONDS
    )

    last_checked_at: str | None = None
    last_refresh_at: str | None = None
    last_refresh_status: str | None = None
    last_error: str | None = None
    refresh_count: int = 0
    failure_count: int = 0

    def __post_init__(self) -> None:
        self.symbol = normalize_symbol(
            self.symbol
        )

        self.timeframe = normalize_timeframe(
            self.timeframe
        )

        self.enabled = bool(
            self.enabled
        )

        self.refresh_before_expiry_seconds = (
            _bounded_int(
                self.refresh_before_expiry_seconds,
                field_name=(
                    "Refresh-before-expiry seconds"
                ),
                minimum=0,
                maximum=(
                    MAX_REFRESH_BEFORE_EXPIRY_SECONDS
                ),
            )
        )

        self.refresh_count = max(
            0,
            int(
                self.refresh_count
                or 0
            ),
        )

        self.failure_count = max(
            0,
            int(
                self.failure_count
                or 0
            ),
        )

    @property
    def key(self) -> str:
        return (
            f"{self.symbol}:"
            f"{self.timeframe}"
        )

    def clone(self) -> RefreshSubscription:
        return deepcopy(
            self
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Return safe subscription metadata.

        Internal error details are never exposed.
        """

        return {
            "key": self.key,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "enabled": self.enabled,
            "refresh_before_expiry_seconds": (
                self.refresh_before_expiry_seconds
            ),
            "last_checked_at": (
                self.last_checked_at
            ),
            "last_refresh_at": (
                self.last_refresh_at
            ),
            "last_refresh_status": (
                self.last_refresh_status
            ),
            "error_present": bool(
                self.last_error
            ),
            "refresh_count": (
                self.refresh_count
            ),
            "failure_count": (
                self.failure_count
            ),
        }


class MarketCacheRefreshService:
    def __init__(
        self,
        *,
        check_interval_seconds: int = (
            DEFAULT_REFRESH_CHECK_INTERVAL_SECONDS
        ),
        maximum_subscriptions: int = (
            MAX_REFRESH_SUBSCRIPTIONS
        ),
        maximum_concurrent_refreshes: int = (
            MAX_CONCURRENT_REFRESHES
        ),
    ) -> None:
        self.check_interval_seconds = (
            _bounded_int(
                check_interval_seconds,
                field_name=(
                    "Refresh check interval"
                ),
                minimum=1,
                maximum=(
                    MAX_REFRESH_CHECK_INTERVAL_SECONDS
                ),
            )
        )

        self.maximum_subscriptions = (
            _bounded_int(
                maximum_subscriptions,
                field_name=(
                    "Maximum subscriptions"
                ),
                minimum=1,
                maximum=(
                    MAX_REFRESH_SUBSCRIPTIONS
                ),
            )
        )

        self.maximum_concurrent_refreshes = (
            _bounded_int(
                maximum_concurrent_refreshes,
                field_name=(
                    "Maximum concurrent refreshes"
                ),
                minimum=1,
                maximum=100,
            )
        )

        self._subscriptions: dict[
            str,
            RefreshSubscription,
        ] = {}

        self._subscription_lock = RLock()

        self._refresh_locks: dict[
            str,
            asyncio.Lock,
        ] = {}

        self._refresh_locks_guard = RLock()

        self._lifecycle_lock: (
            asyncio.Lock | None
        ) = None

        self._background_task: (
            asyncio.Task[None] | None
        ) = None

        self._stop_event: (
            asyncio.Event | None
        ) = None

        self._running = False
        self._started_at: str | None = None
        self._stopped_at: str | None = None
        self._last_cycle_at: str | None = None

        self._cycles_completed = 0
        self._refresh_attempts = 0
        self._successful_refreshes = 0
        self._failed_refreshes = 0
        self._skipped_refreshes = 0

    def _get_lifecycle_lock(
        self,
    ) -> asyncio.Lock:
        if self._lifecycle_lock is None:
            self._lifecycle_lock = (
                asyncio.Lock()
            )

        return self._lifecycle_lock

    def _build_key(
        self,
        symbol: str,
        timeframe: str,
    ) -> str:
        normalized_symbol = normalize_symbol(
            symbol
        )

        normalized_timeframe = (
            normalize_timeframe(
                timeframe
            )
        )

        return (
            f"{normalized_symbol}:"
            f"{normalized_timeframe}"
        )

    def _get_refresh_lock(
        self,
        key: str,
    ) -> asyncio.Lock:
        with self._refresh_locks_guard:
            lock = self._refresh_locks.get(
                key
            )

            if lock is None:
                lock = asyncio.Lock()

                self._refresh_locks[
                    key
                ] = lock

            return lock

    def _remove_refresh_lock(
        self,
        key: str,
        lock: asyncio.Lock,
    ) -> None:
        with self._refresh_locks_guard:
            current = (
                self._refresh_locks.get(
                    key
                )
            )

            if (
                current is lock
                and not lock.locked()
            ):
                self._refresh_locks.pop(
                    key,
                    None,
                )

    def _get_internal_subscription(
        self,
        key: str,
    ) -> RefreshSubscription | None:
        with self._subscription_lock:
            return self._subscriptions.get(
                key
            )

    def get_subscription(
        self,
        symbol: str,
        timeframe: str,
    ) -> RefreshSubscription | None:
        """
        Return an isolated subscription copy.
        """

        key = self._build_key(
            symbol,
            timeframe,
        )

        with self._subscription_lock:
            subscription = (
                self._subscriptions.get(
                    key
                )
            )

            return (
                subscription.clone()
                if subscription is not None
                else None
            )

    def register(
        self,
        symbol: str,
        timeframe: str,
        *,
        refresh_before_expiry_seconds: int = (
            DEFAULT_REFRESH_BEFORE_EXPIRY_SECONDS
        ),
        enabled: bool = True,
    ) -> RefreshSubscription:
        normalized_symbol = normalize_symbol(
            symbol
        )

        normalized_timeframe = (
            normalize_timeframe(
                timeframe
            )
        )

        resolved_refresh_before = (
            _bounded_int(
                refresh_before_expiry_seconds,
                field_name=(
                    "Refresh-before-expiry seconds"
                ),
                minimum=0,
                maximum=(
                    MAX_REFRESH_BEFORE_EXPIRY_SECONDS
                ),
            )
        )

        key = (
            f"{normalized_symbol}:"
            f"{normalized_timeframe}"
        )

        with self._subscription_lock:
            existing = (
                self._subscriptions.get(
                    key
                )
            )

            if existing is not None:
                existing.enabled = bool(
                    enabled
                )

                existing.refresh_before_expiry_seconds = (
                    resolved_refresh_before
                )

                return existing.clone()

            if (
                len(self._subscriptions)
                >= self.maximum_subscriptions
            ):
                raise ValueError(
                    "Maximum refresh subscriptions reached."
                )

            subscription = RefreshSubscription(
                symbol=normalized_symbol,
                timeframe=normalized_timeframe,
                enabled=enabled,
                refresh_before_expiry_seconds=(
                    resolved_refresh_before
                ),
            )

            self._subscriptions[
                key
            ] = subscription

            return subscription.clone()

    def unregister(
        self,
        symbol: str,
        timeframe: str,
    ) -> bool:
        key = self._build_key(
            symbol,
            timeframe,
        )

        with self._subscription_lock:
            removed = (
                self._subscriptions.pop(
                    key,
                    None,
                )
            )

        with self._refresh_locks_guard:
            lock = self._refresh_locks.get(
                key
            )

            if (
                lock is not None
                and not lock.locked()
            ):
                self._refresh_locks.pop(
                    key,
                    None,
                )

        return removed is not None

    def unregister_symbol(
        self,
        symbol: str,
    ) -> int:
        normalized_symbol = normalize_symbol(
            symbol
        )

        with self._subscription_lock:
            matching_keys = [
                key
                for (
                    key,
                    subscription,
                ) in self._subscriptions.items()
                if (
                    subscription.symbol
                    == normalized_symbol
                )
            ]

            for key in matching_keys:
                self._subscriptions.pop(
                    key,
                    None,
                )

        with self._refresh_locks_guard:
            for key in matching_keys:
                lock = self._refresh_locks.get(
                    key
                )

                if (
                    lock is not None
                    and not lock.locked()
                ):
                    self._refresh_locks.pop(
                        key,
                        None,
                    )

        return len(
            matching_keys
        )

    def enable(
        self,
        symbol: str,
        timeframe: str,
    ) -> bool:
        key = self._build_key(
            symbol,
            timeframe,
        )

        with self._subscription_lock:
            subscription = (
                self._subscriptions.get(
                    key
                )
            )

            if subscription is None:
                return False

            subscription.enabled = True

            return True

    def disable(
        self,
        symbol: str,
        timeframe: str,
    ) -> bool:
        key = self._build_key(
            symbol,
            timeframe,
        )

        with self._subscription_lock:
            subscription = (
                self._subscriptions.get(
                    key
                )
            )

            if subscription is None:
                return False

            subscription.enabled = False

            return True

    def list_subscriptions(
        self,
    ) -> list[dict[str, Any]]:
        with self._subscription_lock:
            subscriptions = [
                subscription.clone()
                for subscription
                in self._subscriptions.values()
            ]

        subscriptions.sort(
            key=lambda item: (
                item.symbol,
                item.timeframe,
            )
        )

        return [
            subscription.to_dict()
            for subscription
            in subscriptions
        ]

    def clear_subscriptions(
        self,
    ) -> int:
        with self._subscription_lock:
            removed_count = len(
                self._subscriptions
            )

            self._subscriptions.clear()

        with self._refresh_locks_guard:
            removable_keys = [
                key
                for (
                    key,
                    lock,
                ) in self._refresh_locks.items()
                if not lock.locked()
            ]

            for key in removable_keys:
                self._refresh_locks.pop(
                    key,
                    None,
                )

        return removed_count

    async def refresh_subscription(
        self,
        subscription: RefreshSubscription,
        *,
        force_refresh: bool = True,
    ) -> dict[str, Any]:
        """
        Refresh one registered subscription safely.

        The caller-provided subscription is treated only as an
        identifier. State updates are applied to the registered
        internal subscription.
        """

        key = self._build_key(
            subscription.symbol,
            subscription.timeframe,
        )

        internal = (
            self._get_internal_subscription(
                key
            )
        )

        if internal is None:
            return {
                "status": REFRESH_STATUS_FAILED,
                "key": key,
                "error_present": True,
                "refreshed_at": utc_now_iso(),
            }

        refresh_lock = (
            self._get_refresh_lock(
                key
            )
        )

        if refresh_lock.locked():
            with self._subscription_lock:
                self._skipped_refreshes = (
                    _increment_counter(
                        self._skipped_refreshes
                    )
                )

            return {
                "status": REFRESH_STATUS_SKIPPED,
                "reason": (
                    "Refresh already in progress."
                ),
                "key": key,
            }

        try:
            async with refresh_lock:
                with self._subscription_lock:
                    current = (
                        self._subscriptions.get(
                            key
                        )
                    )

                    if current is None:
                        return {
                            "status": REFRESH_STATUS_FAILED,
                            "key": key,
                            "error_present": True,
                            "refreshed_at": (
                                utc_now_iso()
                            ),
                        }

                    current.last_checked_at = (
                        utc_now_iso()
                    )

                    self._refresh_attempts = (
                        _increment_counter(
                            self._refresh_attempts
                        )
                    )

                    symbol = current.symbol
                    timeframe = current.timeframe

                try:
                    result = await (
                        get_managed_market_data(
                            symbol=symbol,
                            timeframe=timeframe,
                            force_refresh=(
                                force_refresh
                            ),
                            allow_stale_on_error=False,
                        )
                    )

                    if not isinstance(
                        result,
                        dict,
                    ):
                        raise ValueError(
                            "Refresh result is invalid."
                        )

                    refreshed_at = utc_now_iso()

                    with self._subscription_lock:
                        current = (
                            self._subscriptions.get(
                                key
                            )
                        )

                        if current is not None:
                            current.last_refresh_at = (
                                refreshed_at
                            )

                            current.last_refresh_status = (
                                REFRESH_STATUS_SUCCESS
                            )

                            current.last_error = None

                            current.refresh_count = (
                                _increment_counter(
                                    current.refresh_count
                                )
                            )

                        self._successful_refreshes = (
                            _increment_counter(
                                self._successful_refreshes
                            )
                        )

                    request_metadata = result.get(
                        "_request_manager",
                        {},
                    )

                    source = (
                        request_metadata.get(
                            "source"
                        )
                        if isinstance(
                            request_metadata,
                            dict,
                        )
                        else None
                    )

                    return {
                        "status": (
                            REFRESH_STATUS_SUCCESS
                        ),
                        "key": key,
                        "source": source,
                        "refreshed_at": (
                            refreshed_at
                        ),
                    }

                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    refreshed_at = utc_now_iso()

                    safe_error = (
                        _safe_failure_message(
                            exc
                        )
                    )

                    with self._subscription_lock:
                        current = (
                            self._subscriptions.get(
                                key
                            )
                        )

                        if current is not None:
                            current.last_refresh_at = (
                                refreshed_at
                            )

                            current.last_refresh_status = (
                                REFRESH_STATUS_FAILED
                            )

                            current.last_error = (
                                safe_error
                            )

                            current.failure_count = (
                                _increment_counter(
                                    current.failure_count
                                )
                            )

                        self._failed_refreshes = (
                            _increment_counter(
                                self._failed_refreshes
                            )
                        )

                    return {
                        "status": (
                            REFRESH_STATUS_FAILED
                        ),
                        "key": key,
                        "error_present": True,
                        "refreshed_at": (
                            refreshed_at
                        ),
                    }
        finally:
            await asyncio.sleep(
                0
            )

            self._remove_refresh_lock(
                key,
                refresh_lock,
            )

    async def refresh_if_required(
        self,
        subscription: RefreshSubscription,
    ) -> dict[str, Any]:
        key = self._build_key(
            subscription.symbol,
            subscription.timeframe,
        )

        internal = (
            self._get_internal_subscription(
                key
            )
        )

        if internal is None:
            return {
                "status": REFRESH_STATUS_FAILED,
                "key": key,
                "error_present": True,
            }

        checked_at = utc_now_iso()

        with self._subscription_lock:
            current = (
                self._subscriptions.get(
                    key
                )
            )

            if current is None:
                return {
                    "status": REFRESH_STATUS_FAILED,
                    "key": key,
                    "error_present": True,
                }

            current.last_checked_at = (
                checked_at
            )

            enabled = current.enabled

            refresh_before = (
                current.refresh_before_expiry_seconds
            )

            symbol = current.symbol
            timeframe = current.timeframe

        if not enabled:
            with self._subscription_lock:
                self._skipped_refreshes = (
                    _increment_counter(
                        self._skipped_refreshes
                    )
                )

            return {
                "status": REFRESH_STATUS_SKIPPED,
                "key": key,
                "reason": (
                    "Subscription is disabled."
                ),
            }

        cache_entry = (
            market_data_cache.get_entry(
                symbol,
                timeframe,
                allow_expired=True,
            )
        )

        if cache_entry is None:
            return await (
                self.refresh_subscription(
                    subscription,
                    force_refresh=True,
                )
            )

        remaining_seconds = (
            cache_entry.remaining_seconds
        )

        should_refresh = (
            cache_entry.is_expired
            or remaining_seconds
            <= refresh_before
        )

        if not should_refresh:
            with self._subscription_lock:
                self._skipped_refreshes = (
                    _increment_counter(
                        self._skipped_refreshes
                    )
                )

            return {
                "status": REFRESH_STATUS_SKIPPED,
                "key": key,
                "reason": (
                    "Cached data is still fresh."
                ),
                "remaining_seconds": (
                    remaining_seconds
                ),
            }

        return await (
            self.refresh_subscription(
                subscription,
                force_refresh=True,
            )
        )

    async def run_refresh_cycle(
        self,
    ) -> dict[str, Any]:
        cycle_at = utc_now_iso()

        with self._subscription_lock:
            self._last_cycle_at = cycle_at

            subscriptions = [
                subscription.clone()
                for subscription
                in self._subscriptions.values()
            ]

        semaphore = asyncio.Semaphore(
            self.maximum_concurrent_refreshes
        )

        async def run_one(
            item: RefreshSubscription,
        ) -> dict[str, Any]:
            async with semaphore:
                try:
                    return await (
                        self.refresh_if_required(
                            item
                        )
                    )
                except asyncio.CancelledError:
                    raise
                except Exception:
                    with self._subscription_lock:
                        self._failed_refreshes = (
                            _increment_counter(
                                self._failed_refreshes
                            )
                        )

                    return {
                        "status": (
                            REFRESH_STATUS_FAILED
                        ),
                        "key": item.key,
                        "error_present": True,
                    }

        results = (
            await asyncio.gather(
                *(
                    run_one(
                        subscription
                    )
                    for subscription
                    in subscriptions
                )
            )
            if subscriptions
            else []
        )

        with self._subscription_lock:
            self._cycles_completed = (
                _increment_counter(
                    self._cycles_completed
                )
            )

            cycle_number = (
                self._cycles_completed
            )

        successful = sum(
            1
            for result in results
            if (
                result.get(
                    "status"
                )
                == REFRESH_STATUS_SUCCESS
            )
        )

        failed = sum(
            1
            for result in results
            if (
                result.get(
                    "status"
                )
                == REFRESH_STATUS_FAILED
            )
        )

        skipped = sum(
            1
            for result in results
            if (
                result.get(
                    "status"
                )
                == REFRESH_STATUS_SKIPPED
            )
        )

        return {
            "status": "success",
            "cycle": cycle_number,
            "checked_at": cycle_at,
            "subscriptions_checked": len(
                results
            ),
            "successful_refreshes": (
                successful
            ),
            "failed_refreshes": failed,
            "skipped_refreshes": skipped,
            "results": results,
        }

    async def _background_loop(
        self,
    ) -> None:
        stop_event = self._stop_event

        if stop_event is None:
            return

        try:
            while not stop_event.is_set():
                try:
                    await self.run_refresh_cycle()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    with self._subscription_lock:
                        self._failed_refreshes = (
                            _increment_counter(
                                self._failed_refreshes
                            )
                        )

                try:
                    await asyncio.wait_for(
                        stop_event.wait(),
                        timeout=(
                            self.check_interval_seconds
                        ),
                    )
                except asyncio.TimeoutError:
                    continue
        finally:
            with self._subscription_lock:
                self._running = False

    async def start(
        self,
    ) -> bool:
        lifecycle_lock = (
            self._get_lifecycle_lock()
        )

        async with lifecycle_lock:
            if (
                self._running
                and self._background_task
                is not None
                and not self._background_task.done()
            ):
                return False

            self._stop_event = (
                asyncio.Event()
            )

            self._running = True
            self._started_at = utc_now_iso()
            self._stopped_at = None

            self._background_task = (
                asyncio.create_task(
                    self._background_loop(),
                    name=(
                        "blue-trading-ai-cache-refresh"
                    ),
                )
            )

            return True

    async def stop(
        self,
    ) -> bool:
        lifecycle_lock = (
            self._get_lifecycle_lock()
        )

        async with lifecycle_lock:
            task = self._background_task

            if (
                not self._running
                and (
                    task is None
                    or task.done()
                )
            ):
                return False

            self._running = False
            self._stopped_at = utc_now_iso()

            if self._stop_event is not None:
                self._stop_event.set()

            if (
                task is not None
                and not task.done()
            ):
                task.cancel()

                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass

            self._background_task = None
            self._stop_event = None

            return True

    def get_status(
        self,
    ) -> dict[str, Any]:
        with self._subscription_lock:
            running = bool(
                self._running
                and self._background_task
                is not None
                and not self._background_task.done()
            )

            subscription_count = len(
                self._subscriptions
            )

            return {
                "version": (
                    CACHE_REFRESH_SERVICE_VERSION
                ),
                "module": (
                    "Automatic Market Cache Refresh"
                ),
                "running": running,
                "check_interval_seconds": (
                    self.check_interval_seconds
                ),
                "subscription_count": (
                    subscription_count
                ),
                "maximum_subscriptions": (
                    self.maximum_subscriptions
                ),
                "maximum_concurrent_refreshes": (
                    self.maximum_concurrent_refreshes
                ),
                "active_refresh_lock_count": len(
                    self._refresh_locks
                ),
                "started_at": (
                    self._started_at
                ),
                "stopped_at": (
                    self._stopped_at
                ),
                "last_cycle_at": (
                    self._last_cycle_at
                ),
                "cycles_completed": (
                    self._cycles_completed
                ),
                "refresh_attempts": (
                    self._refresh_attempts
                ),
                "successful_refreshes": (
                    self._successful_refreshes
                ),
                "failed_refreshes": (
                    self._failed_refreshes
                ),
                "skipped_refreshes": (
                    self._skipped_refreshes
                ),
                "broker_connection_enabled": False,
                "trade_execution_enabled": False,
            }


market_cache_refresh_service = (
    MarketCacheRefreshService(
        check_interval_seconds=(
            DEFAULT_REFRESH_CHECK_INTERVAL_SECONDS
        ),
    )
)


def register_market_cache_refresh(
    symbol: str,
    timeframe: str,
    *,
    refresh_before_expiry_seconds: int = (
        DEFAULT_REFRESH_BEFORE_EXPIRY_SECONDS
    ),
    enabled: bool = True,
) -> dict[str, Any]:
    subscription = (
        market_cache_refresh_service.register(
            symbol=symbol,
            timeframe=timeframe,
            refresh_before_expiry_seconds=(
                refresh_before_expiry_seconds
            ),
            enabled=enabled,
        )
    )

    return subscription.to_dict()


def unregister_market_cache_refresh(
    symbol: str,
    timeframe: str,
) -> bool:
    return (
        market_cache_refresh_service.unregister(
            symbol=symbol,
            timeframe=timeframe,
        )
    )


def list_market_cache_refresh_subscriptions(
) -> list[dict[str, Any]]:
    return (
        market_cache_refresh_service
        .list_subscriptions()
    )


def get_market_cache_refresh_status(
) -> dict[str, Any]:
    return (
        market_cache_refresh_service
        .get_status()
    )


async def run_market_cache_refresh_cycle(
) -> dict[str, Any]:
    return await (
        market_cache_refresh_service
        .run_refresh_cycle()
    )


async def start_market_cache_refresh_service(
) -> bool:
    return await (
        market_cache_refresh_service.start()
    )


async def stop_market_cache_refresh_service(
) -> bool:
    return await (
        market_cache_refresh_service.stop()
    )


__all__ = [
    "CACHE_REFRESH_SERVICE_VERSION",
    "DEFAULT_REFRESH_BEFORE_EXPIRY_SECONDS",
    "DEFAULT_REFRESH_CHECK_INTERVAL_SECONDS",
    "MAX_CONCURRENT_REFRESHES",
    "MAX_REFRESH_BEFORE_EXPIRY_SECONDS",
    "MAX_REFRESH_SUBSCRIPTIONS",
    "MarketCacheRefreshService",
    "RefreshSubscription",
    "get_market_cache_refresh_status",
    "list_market_cache_refresh_subscriptions",
    "market_cache_refresh_service",
    "register_market_cache_refresh",
    "run_market_cache_refresh_cycle",
    "start_market_cache_refresh_service",
    "stop_market_cache_refresh_service",
    "unregister_market_cache_refresh",
    "utc_now_iso",
]