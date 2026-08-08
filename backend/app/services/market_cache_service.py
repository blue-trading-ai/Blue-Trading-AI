from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any, Final


CACHE_SERVICE_VERSION: Final[int] = 22

MAX_SYMBOL_LENGTH: Final[int] = 40
MAX_PROVIDER_LENGTH: Final[int] = 80
MAX_CACHE_ENTRIES: Final[int] = 2_000
MAX_TTL_SECONDS: Final[int] = 31 * 24 * 60 * 60
MAX_PAYLOAD_KEYS: Final[int] = 250
MAX_METADATA_KEYS: Final[int] = 50
MAX_COUNTER_VALUE: Final[int] = 9_223_372_036_854_775_000


TIMEFRAME_CACHE_SECONDS: Final[dict[str, int]] = {
    "M5": 5 * 60,
    "M15": 15 * 60,
    "M30": 30 * 60,
    "H1": 60 * 60,
    "H4": 4 * 60 * 60,
    "D1": 24 * 60 * 60,
    "W1": 7 * 24 * 60 * 60,
    "MN": 30 * 24 * 60 * 60,
}


TIMEFRAME_ALIASES: Final[dict[str, str]] = {
    "5M": "M5",
    "M5": "M5",
    "5MIN": "M5",
    "15M": "M15",
    "M15": "M15",
    "15MIN": "M15",
    "30M": "M30",
    "M30": "M30",
    "30MIN": "M30",
    "1H": "H1",
    "H1": "H1",
    "60MIN": "H1",
    "4H": "H4",
    "H4": "H4",
    "1D": "D1",
    "D1": "D1",
    "DAY": "D1",
    "DAILY": "D1",
    "1W": "W1",
    "W1": "W1",
    "WEEK": "W1",
    "WEEKLY": "W1",
    "1MO": "MN",
    "MN": "MN",
    "MONTH": "MN",
    "MONTHLY": "MN",
}


def utc_now() -> datetime:
    """Return one timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def _as_utc(
    value: datetime,
) -> datetime:
    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


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


def _safe_deepcopy(
    value: Any,
    *,
    field_name: str,
) -> Any:
    try:
        return deepcopy(
            value
        )
    except Exception as exc:
        raise TypeError(
            f"{field_name} must contain copyable values."
        ) from exc


def _validate_mapping(
    value: dict[str, Any] | None,
    *,
    field_name: str,
    maximum_keys: int,
) -> dict[str, Any]:
    if value is None:
        return {}

    if not isinstance(
        value,
        dict,
    ):
        raise TypeError(
            f"{field_name} must be a dictionary."
        )

    if len(value) > maximum_keys:
        raise ValueError(
            f"{field_name} contains too many fields."
        )

    return _safe_deepcopy(
        value,
        field_name=field_name,
    )


def normalize_symbol(
    symbol: str,
) -> str:
    raw = str(
        symbol or ""
    ).strip().upper()

    normalized = "".join(
        character
        for character in raw
        if character.isalnum()
    )

    if not normalized:
        raise ValueError(
            "Symbol cannot be empty."
        )

    if len(normalized) > MAX_SYMBOL_LENGTH:
        raise ValueError(
            "Symbol is too long."
        )

    return normalized


def normalize_timeframe(
    timeframe: str,
) -> str:
    normalized = str(
        timeframe or ""
    ).strip().upper()

    if not normalized:
        raise ValueError(
            "Timeframe cannot be empty."
        )

    resolved = TIMEFRAME_ALIASES.get(
        normalized
    )

    if resolved is None:
        raise ValueError(
            "Unsupported timeframe."
        )

    return resolved


def build_cache_key(
    symbol: str,
    timeframe: str,
) -> str:
    normalized_symbol = normalize_symbol(
        symbol
    )

    normalized_timeframe = normalize_timeframe(
        timeframe
    )

    return (
        f"{normalized_symbol}:"
        f"{normalized_timeframe}"
    )


@dataclass
class MarketCacheEntry:
    key: str
    symbol: str
    timeframe: str
    payload: dict[str, Any]
    created_at: datetime
    expires_at: datetime
    provider: str | None = None
    access_count: int = 0
    last_accessed_at: datetime | None = None
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.key = str(
            self.key or ""
        ).strip()

        self.symbol = normalize_symbol(
            self.symbol
        )

        self.timeframe = normalize_timeframe(
            self.timeframe
        )

        self.created_at = _as_utc(
            self.created_at
        )

        self.expires_at = _as_utc(
            self.expires_at
        )

        if self.expires_at <= self.created_at:
            raise ValueError(
                "Cache expiry must be later than creation time."
            )

        self.provider = (
            str(
                self.provider
            ).strip()[
                :MAX_PROVIDER_LENGTH
            ]
            if self.provider
            else None
        )

        self.payload = _validate_mapping(
            self.payload,
            field_name="Cache payload",
            maximum_keys=MAX_PAYLOAD_KEYS,
        )

        self.metadata = _validate_mapping(
            self.metadata,
            field_name="Cache metadata",
            maximum_keys=MAX_METADATA_KEYS,
        )

        self.access_count = max(
            0,
            int(
                self.access_count
                or 0
            ),
        )

        if self.last_accessed_at is not None:
            self.last_accessed_at = _as_utc(
                self.last_accessed_at
            )

    @property
    def is_expired(self) -> bool:
        return (
            utc_now()
            >= self.expires_at
        )

    @property
    def remaining_seconds(self) -> int:
        remaining = (
            self.expires_at
            - utc_now()
        )

        return max(
            0,
            int(
                remaining.total_seconds()
            ),
        )

    def mark_accessed(self) -> None:
        self.access_count = (
            _increment_counter(
                self.access_count
            )
        )

        self.last_accessed_at = (
            utc_now()
        )

    def clone_payload(
        self,
    ) -> dict[str, Any]:
        return _safe_deepcopy(
            self.payload,
            field_name="Cache payload",
        )

    def to_summary(self) -> dict[str, Any]:
        """
        Return safe cache metadata without provider or custom metadata.
        """

        return {
            "key": self.key,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "created_at": (
                self.created_at.isoformat()
            ),
            "expires_at": (
                self.expires_at.isoformat()
            ),
            "is_expired": self.is_expired,
            "remaining_seconds": (
                self.remaining_seconds
            ),
            "access_count": (
                self.access_count
            ),
            "last_accessed_at": (
                self.last_accessed_at.isoformat()
                if self.last_accessed_at
                else None
            ),
            "provider_configured": bool(
                self.provider
            ),
            "metadata_present": bool(
                self.metadata
            ),
        }


class MarketDataCache:
    def __init__(
        self,
        *,
        max_entries: int = MAX_CACHE_ENTRIES,
    ) -> None:
        resolved_max_entries = int(
            max_entries
        )

        if resolved_max_entries < 1:
            raise ValueError(
                "Maximum cache entries must be at least one."
            )

        self._max_entries = min(
            resolved_max_entries,
            MAX_CACHE_ENTRIES,
        )

        self._cache: dict[
            str,
            MarketCacheEntry,
        ] = {}

        self._lock = RLock()

        self._hits = 0
        self._misses = 0
        self._writes = 0
        self._expired_removals = 0
        self._manual_removals = 0
        self._capacity_evictions = 0

    def _remove_expired_locked(
        self,
    ) -> int:
        expired_keys = [
            key
            for (
                key,
                entry,
            ) in self._cache.items()
            if entry.is_expired
        ]

        for key in expired_keys:
            self._cache.pop(
                key,
                None,
            )

        removed_count = len(
            expired_keys
        )

        self._expired_removals = (
            _increment_counter(
                self._expired_removals,
                removed_count,
            )
        )

        return removed_count

    def _evict_for_capacity_locked(
        self,
        incoming_key: str,
    ) -> None:
        if incoming_key in self._cache:
            return

        self._remove_expired_locked()

        while (
            len(self._cache)
            >= self._max_entries
        ):
            oldest_key = min(
                self._cache,
                key=lambda key: (
                    self._cache[key].last_accessed_at
                    or self._cache[key].created_at,
                    self._cache[key].created_at,
                    key,
                ),
            )

            self._cache.pop(
                oldest_key,
                None,
            )

            self._capacity_evictions = (
                _increment_counter(
                    self._capacity_evictions
                )
            )

    def get(
        self,
        symbol: str,
        timeframe: str,
        *,
        allow_expired: bool = False,
    ) -> dict[str, Any] | None:
        key = build_cache_key(
            symbol,
            timeframe,
        )

        with self._lock:
            entry = self._cache.get(
                key
            )

            if entry is None:
                self._misses = (
                    _increment_counter(
                        self._misses
                    )
                )

                return None

            if (
                entry.is_expired
                and not allow_expired
            ):
                self._cache.pop(
                    key,
                    None,
                )

                self._misses = (
                    _increment_counter(
                        self._misses
                    )
                )

                self._expired_removals = (
                    _increment_counter(
                        self._expired_removals
                    )
                )

                return None

            entry.mark_accessed()

            self._hits = (
                _increment_counter(
                    self._hits
                )
            )

            return entry.clone_payload()

    def get_entry(
        self,
        symbol: str,
        timeframe: str,
        *,
        allow_expired: bool = False,
    ) -> MarketCacheEntry | None:
        """
        Return an isolated entry copy so callers cannot mutate the cache.
        """

        key = build_cache_key(
            symbol,
            timeframe,
        )

        with self._lock:
            entry = self._cache.get(
                key
            )

            if entry is None:
                self._misses = (
                    _increment_counter(
                        self._misses
                    )
                )

                return None

            if (
                entry.is_expired
                and not allow_expired
            ):
                self._cache.pop(
                    key,
                    None,
                )

                self._misses = (
                    _increment_counter(
                        self._misses
                    )
                )

                self._expired_removals = (
                    _increment_counter(
                        self._expired_removals
                    )
                )

                return None

            entry.mark_accessed()

            self._hits = (
                _increment_counter(
                    self._hits
                )
            )

            return _safe_deepcopy(
                entry,
                field_name="Cache entry",
            )

    def set(
        self,
        symbol: str,
        timeframe: str,
        payload: dict[str, Any],
        *,
        provider: str | None = None,
        ttl_seconds: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MarketCacheEntry:
        normalized_symbol = normalize_symbol(
            symbol
        )

        normalized_timeframe = normalize_timeframe(
            timeframe
        )

        key = build_cache_key(
            normalized_symbol,
            normalized_timeframe,
        )

        try:
            effective_ttl = int(
                ttl_seconds
                if ttl_seconds is not None
                else TIMEFRAME_CACHE_SECONDS[
                    normalized_timeframe
                ]
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                "Cache TTL must be an integer."
            ) from exc

        if not (
            1
            <= effective_ttl
            <= MAX_TTL_SECONDS
        ):
            raise ValueError(
                "Cache TTL is outside the allowed range."
            )

        safe_payload = _validate_mapping(
            payload,
            field_name="Cache payload",
            maximum_keys=MAX_PAYLOAD_KEYS,
        )

        safe_metadata = _validate_mapping(
            metadata,
            field_name="Cache metadata",
            maximum_keys=MAX_METADATA_KEYS,
        )

        created_at = utc_now()

        entry = MarketCacheEntry(
            key=key,
            symbol=normalized_symbol,
            timeframe=normalized_timeframe,
            payload=safe_payload,
            created_at=created_at,
            expires_at=(
                created_at
                + timedelta(
                    seconds=effective_ttl
                )
            ),
            provider=provider,
            metadata=safe_metadata,
        )

        with self._lock:
            self._evict_for_capacity_locked(
                key
            )

            self._cache[key] = entry

            self._writes = (
                _increment_counter(
                    self._writes
                )
            )

            return _safe_deepcopy(
                entry,
                field_name="Cache entry",
            )

    def has_valid_entry(
        self,
        symbol: str,
        timeframe: str,
    ) -> bool:
        key = build_cache_key(
            symbol,
            timeframe,
        )

        with self._lock:
            entry = self._cache.get(
                key
            )

            if entry is None:
                return False

            if entry.is_expired:
                self._cache.pop(
                    key,
                    None,
                )

                self._expired_removals = (
                    _increment_counter(
                        self._expired_removals
                    )
                )

                return False

            return True

    def delete(
        self,
        symbol: str,
        timeframe: str,
    ) -> bool:
        key = build_cache_key(
            symbol,
            timeframe,
        )

        with self._lock:
            removed = self._cache.pop(
                key,
                None,
            )

            if removed is None:
                return False

            self._manual_removals = (
                _increment_counter(
                    self._manual_removals
                )
            )

            return True

    def delete_symbol(
        self,
        symbol: str,
    ) -> int:
        normalized_symbol = normalize_symbol(
            symbol
        )

        with self._lock:
            matching_keys = [
                key
                for (
                    key,
                    entry,
                ) in self._cache.items()
                if (
                    entry.symbol
                    == normalized_symbol
                )
            ]

            for key in matching_keys:
                self._cache.pop(
                    key,
                    None,
                )

            removed_count = len(
                matching_keys
            )

            self._manual_removals = (
                _increment_counter(
                    self._manual_removals,
                    removed_count,
                )
            )

            return removed_count

    def clear(self) -> int:
        with self._lock:
            removed_count = len(
                self._cache
            )

            self._cache.clear()

            self._manual_removals = (
                _increment_counter(
                    self._manual_removals,
                    removed_count,
                )
            )

            return removed_count

    def remove_expired(self) -> int:
        with self._lock:
            return (
                self._remove_expired_locked()
            )

    def list_entries(
        self,
        *,
        include_expired: bool = False,
    ) -> list[dict[str, Any]]:
        with self._lock:
            if not include_expired:
                self._remove_expired_locked()

            entries = sorted(
                self._cache.values(),
                key=lambda item: (
                    item.symbol,
                    item.timeframe,
                    item.created_at,
                ),
            )

            return [
                entry.to_summary()
                for entry in entries
                if (
                    include_expired
                    or not entry.is_expired
                )
            ]

    def stats(self) -> dict[str, Any]:
        with self._lock:
            self._remove_expired_locked()

            total_requests = (
                self._hits
                + self._misses
            )

            hit_rate = (
                round(
                    (
                        self._hits
                        / total_requests
                    )
                    * 100,
                    2,
                )
                if total_requests > 0
                else 0.0
            )

            return {
                "module": "Market Data Cache",
                "version": CACHE_SERVICE_VERSION,
                "cache_type": "in_memory",
                "entry_count": len(
                    self._cache
                ),
                "maximum_entries": (
                    self._max_entries
                ),
                "symbol_count": len(
                    {
                        entry.symbol
                        for entry
                        in self._cache.values()
                    }
                ),
                "timeframe_count": len(
                    {
                        entry.timeframe
                        for entry
                        in self._cache.values()
                    }
                ),
                "hits": self._hits,
                "misses": self._misses,
                "writes": self._writes,
                "total_requests": (
                    total_requests
                ),
                "hit_rate_percentage": (
                    hit_rate
                ),
                "expired_removals": (
                    self._expired_removals
                ),
                "manual_removals": (
                    self._manual_removals
                ),
                "capacity_evictions": (
                    self._capacity_evictions
                ),
                "broker_connection_enabled": False,
                "trade_execution_enabled": False,
            }

    def reset_statistics(self) -> None:
        with self._lock:
            self._hits = 0
            self._misses = 0
            self._writes = 0
            self._expired_removals = 0
            self._manual_removals = 0
            self._capacity_evictions = 0


market_data_cache = MarketDataCache()


def get_cached_market_data(
    symbol: str,
    timeframe: str,
    *,
    allow_expired: bool = False,
) -> dict[str, Any] | None:
    return market_data_cache.get(
        symbol=symbol,
        timeframe=timeframe,
        allow_expired=allow_expired,
    )


def cache_market_data(
    symbol: str,
    timeframe: str,
    payload: dict[str, Any],
    *,
    provider: str | None = None,
    ttl_seconds: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entry = market_data_cache.set(
        symbol=symbol,
        timeframe=timeframe,
        payload=payload,
        provider=provider,
        ttl_seconds=ttl_seconds,
        metadata=metadata,
    )

    return entry.to_summary()


def clear_market_cache() -> int:
    return market_data_cache.clear()


def clear_symbol_cache(
    symbol: str,
) -> int:
    return market_data_cache.delete_symbol(
        symbol
    )


def remove_expired_market_cache() -> int:
    return (
        market_data_cache.remove_expired()
    )


def get_market_cache_stats() -> dict[str, Any]:
    return market_data_cache.stats()


def list_market_cache_entries(
    *,
    include_expired: bool = False,
) -> list[dict[str, Any]]:
    return market_data_cache.list_entries(
        include_expired=include_expired
    )


__all__ = [
    "CACHE_SERVICE_VERSION",
    "MAX_CACHE_ENTRIES",
    "MAX_METADATA_KEYS",
    "MAX_PAYLOAD_KEYS",
    "MAX_SYMBOL_LENGTH",
    "MAX_TTL_SECONDS",
    "MarketCacheEntry",
    "MarketDataCache",
    "TIMEFRAME_ALIASES",
    "TIMEFRAME_CACHE_SECONDS",
    "build_cache_key",
    "cache_market_data",
    "clear_market_cache",
    "clear_symbol_cache",
    "get_cached_market_data",
    "get_market_cache_stats",
    "list_market_cache_entries",
    "market_data_cache",
    "normalize_symbol",
    "normalize_timeframe",
    "remove_expired_market_cache",
    "utc_now",
]