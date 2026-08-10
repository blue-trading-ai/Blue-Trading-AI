from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta
from threading import RLock
from typing import Any

import requests

from app.core.config import settings
from app.services.economic_news_service import (
    IMPACT_LEVELS,
    SUPPORTED_CURRENCIES,
    register_economic_news_events,
)

logger = logging.getLogger(__name__)


class EconomicNewsProviderError(RuntimeError):
    """Raised when the external economic-news provider cannot be used safely."""


class ForexFactoryEconomicNewsProvider:
    """
    Fetch and normalize the official Forex Factory weekly JSON export.

    Notes:
    - The provider feed is weekly.
    - Only currencies supported by the current Blue-Trading-AI
      Economic News Intelligence service are registered.
    - Only LOW / MEDIUM / HIGH impact economic events are registered.
      Non-economic values such as Holiday are ignored by the trading-risk engine.
    - Refreshes are cached to avoid unnecessary repeated external requests.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._last_refresh_at: datetime | None = None
        self._last_result: dict[str, Any] | None = None

    @staticmethod
    def _normalize_optional_value(
        value: Any,
    ) -> str | float | None:
        if value is None:
            return None

        if isinstance(value, (int, float)):
            return value

        cleaned = str(value).strip()

        return cleaned or None

    @staticmethod
    def _parse_datetime(
        value: Any,
    ) -> datetime:
        cleaned = str(value or "").strip()

        if not cleaned:
            raise ValueError(
                "Economic-news event date is missing."
            )

        try:
            parsed = datetime.fromisoformat(
                cleaned.replace("Z", "+00:00")
            )
        except ValueError as error:
            raise ValueError(
                f"Unsupported economic-news datetime: {cleaned!r}."
            ) from error

        if parsed.tzinfo is None:
            raise ValueError(
                "Economic-news provider datetime must include a timezone offset."
            )

        return parsed

    @staticmethod
    def _build_event_id(
        *,
        title: str,
        currency: str,
        scheduled_datetime: datetime,
    ) -> str:
        identity = "|".join(
            [
                "FOREX_FACTORY",
                currency,
                title,
                scheduled_datetime.isoformat(),
            ]
        )

        digest = hashlib.sha256(
            identity.encode("utf-8")
        ).hexdigest()[:32]

        return f"ff-{digest}"

    def _normalize_event(
        self,
        event: Any,
    ) -> dict[str, Any] | None:
        if not isinstance(event, dict):
            return None

        title = str(
            event.get("title") or ""
        ).strip()

        currency = str(
            event.get("country") or ""
        ).strip().upper()

        impact = str(
            event.get("impact") or ""
        ).strip().upper()

        if not title:
            return None

        if currency not in SUPPORTED_CURRENCIES:
            return None

        if impact not in IMPACT_LEVELS:
            return None

        scheduled_datetime = self._parse_datetime(
            event.get("date")
        )

        return {
            "event_id": self._build_event_id(
                title=title,
                currency=currency,
                scheduled_datetime=scheduled_datetime,
            ),
            "title": title,
            "currency": currency,
            "impact": impact,
            "scheduled_datetime": scheduled_datetime,
            "actual": self._normalize_optional_value(
                event.get("actual")
            ),
            "forecast": self._normalize_optional_value(
                event.get("forecast")
            ),
            "previous": self._normalize_optional_value(
                event.get("previous")
            ),
            "source": "FOREX_FACTORY",
            "country": currency,
        }

    def _cache_is_fresh(
        self,
        now: datetime,
    ) -> bool:
        if (
            self._last_refresh_at is None
            or self._last_result is None
        ):
            return False

        maximum_age = timedelta(
            minutes=settings.ECONOMIC_NEWS_CACHE_MINUTES
        )

        return (
            now - self._last_refresh_at
        ) < maximum_age

    def fetch_weekly_feed(
        self,
    ) -> list[dict[str, Any]]:
        headers = {
            "Accept": "application/json",
            "User-Agent": settings.ECONOMIC_NEWS_USER_AGENT,
        }

        try:
            response = requests.get(
                settings.ECONOMIC_NEWS_WEEKLY_URL,
                headers=headers,
                timeout=settings.ECONOMIC_NEWS_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            raise EconomicNewsProviderError(
                "Forex Factory weekly calendar could not be fetched."
            ) from error

        try:
            payload = response.json()
        except ValueError as error:
            raise EconomicNewsProviderError(
                "Forex Factory returned invalid JSON."
            ) from error

        if not isinstance(payload, list):
            raise EconomicNewsProviderError(
                "Forex Factory weekly calendar returned an unexpected response shape."
            )

        return payload

    def refresh_current_week(
        self,
        *,
        force: bool = False,
    ) -> dict[str, Any]:
        now = datetime.now().astimezone()

        with self._lock:
            if (
                not force
                and self._cache_is_fresh(now)
            ):
                return {
                    **self._last_result,
                    "cached": True,
                }

            raw_events = self.fetch_weekly_feed()

            normalized_events: list[
                dict[str, Any]
            ] = []

            skipped_events = 0
            invalid_events = 0

            for raw_event in raw_events:
                try:
                    normalized_event = (
                        self._normalize_event(
                            raw_event
                        )
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    logger.warning(
                        "Skipping invalid Forex Factory economic-news event.",
                        exc_info=True,
                    )
                    invalid_events += 1
                    continue

                if normalized_event is None:
                    skipped_events += 1
                    continue

                normalized_events.append(
                    normalized_event
                )

            registered_events = (
                register_economic_news_events(
                    normalized_events
                )
                if normalized_events
                else []
            )

            result = {
                "project": "Blue-Trading-AI",
                "provider": "FOREX_FACTORY",
                "source_url": (
                    settings.ECONOMIC_NEWS_WEEKLY_URL
                ),
                "refresh_type": "CURRENT_WEEK",
                "refreshed_at": now.isoformat(),
                "raw_event_count": len(
                    raw_events
                ),
                "normalized_event_count": len(
                    normalized_events
                ),
                "registered_event_count": len(
                    registered_events
                ),
                "skipped_event_count": skipped_events,
                "invalid_event_count": invalid_events,
                "cache_minutes": (
                    settings.ECONOMIC_NEWS_CACHE_MINUTES
                ),
                "cached": False,
            }

            self._last_refresh_at = now
            self._last_result = result

            return dict(result)


economic_news_provider = (
    ForexFactoryEconomicNewsProvider()
)


def refresh_forex_factory_current_week(
    *,
    force: bool = False,
) -> dict[str, Any]:
    return economic_news_provider.refresh_current_week(
        force=force
    )


__all__ = [
    "EconomicNewsProviderError",
    "ForexFactoryEconomicNewsProvider",
    "economic_news_provider",
    "refresh_forex_factory_current_week",
]