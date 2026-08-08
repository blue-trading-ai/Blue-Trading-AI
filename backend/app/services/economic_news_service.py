from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import math
from threading import RLock
from typing import Any, Final
from zoneinfo import ZoneInfo


# ============================================================
# BLUE-TRADING-AI
# VERSION 23
# ECONOMIC NEWS INTELLIGENCE SERVICE
# ============================================================


NEWS_TIMEZONE: Final = "Asia/Kuala_Lumpur"

MINIMUM_NEWS_CONFIDENCE: Final = 80.0
MAXIMUM_HOURS_AHEAD: Final = 168
MAXIMUM_EVENT_BATCH_SIZE: Final = 500
MAXIMUM_EVENT_ID_LENGTH: Final = 128
MAXIMUM_EVENT_TITLE_LENGTH: Final = 250
MAXIMUM_TEXT_FIELD_LENGTH: Final = 128

SUPPORTED_CURRENCIES = {
    "USD",
    "EUR",
    "GBP",
    "JPY",
    "AUD",
    "NZD",
    "CAD",
    "CHF",
}


IMPACT_LEVELS = {
    "LOW",
    "MEDIUM",
    "HIGH",
}


BLACKOUT_WINDOWS: dict[str, dict[str, int]] = {
    "HIGH": {
        "minutes_before": 30,
        "minutes_after": 30,
    },
    "MEDIUM": {
        "minutes_before": 15,
        "minutes_after": 15,
    },
    "LOW": {
        "minutes_before": 0,
        "minutes_after": 0,
    },
}


IMPACT_RISK_SCORES = {
    "LOW": 20.0,
    "MEDIUM": 55.0,
    "HIGH": 90.0,
}


EVENT_KEYWORDS: dict[str, list[str]] = {
    "INTEREST_RATE_DECISION": [
        "interest rate decision",
        "rate decision",
        "cash rate",
        "policy rate",
        "bank rate",
        "federal funds rate",
    ],
    "CENTRAL_BANK_STATEMENT": [
        "fomc statement",
        "monetary policy statement",
        "central bank statement",
        "policy statement",
    ],
    "CENTRAL_BANK_SPEECH": [
        "central bank speech",
        "fed chair speech",
        "ecb president speech",
        "boe governor speech",
        "boj governor speech",
        "rba governor speech",
        "rbnz governor speech",
        "boc governor speech",
        "snb chairman speech",
    ],
    "NON_FARM_PAYROLLS": [
        "non-farm payroll",
        "nonfarm payroll",
        "nfp",
        "employment change",
    ],
    "INFLATION": [
        "consumer price index",
        "cpi",
        "inflation rate",
        "core inflation",
        "core cpi",
    ],
    "PRODUCER_INFLATION": [
        "producer price index",
        "ppi",
        "producer inflation",
    ],
    "GDP": [
        "gross domestic product",
        "gdp",
        "economic growth",
    ],
    "PMI": [
        "purchasing managers index",
        "manufacturing pmi",
        "services pmi",
        "composite pmi",
        "pmi",
    ],
    "RETAIL_SALES": [
        "retail sales",
        "core retail sales",
    ],
    "UNEMPLOYMENT": [
        "unemployment rate",
        "jobless rate",
        "jobless claims",
        "initial jobless claims",
    ],
    "CONSUMER_CONFIDENCE": [
        "consumer confidence",
        "consumer sentiment",
    ],
    "TRADE_BALANCE": [
        "trade balance",
        "current account",
    ],
}


CENTRAL_BANK_CURRENCY_MAP = {
    "FED": "USD",
    "FOMC": "USD",
    "ECB": "EUR",
    "BOE": "GBP",
    "BOJ": "JPY",
    "RBA": "AUD",
    "RBNZ": "NZD",
    "BOC": "CAD",
    "SNB": "CHF",
}


SYMBOL_CURRENCY_MAP: dict[str, list[str]] = {
    "XAUUSD": ["USD"],
    "BTCUSD": ["USD"],
    "ETHUSD": ["USD"],
    "EURUSD": ["EUR", "USD"],
    "GBPUSD": ["GBP", "USD"],
    "USDJPY": ["USD", "JPY"],
    "AUDUSD": ["AUD", "USD"],
    "NZDUSD": ["NZD", "USD"],
    "USDCAD": ["USD", "CAD"],
    "USDCHF": ["USD", "CHF"],
    "EURGBP": ["EUR", "GBP"],
    "EURJPY": ["EUR", "JPY"],
    "GBPJPY": ["GBP", "JPY"],
    "AUDJPY": ["AUD", "JPY"],
    "CADJPY": ["CAD", "JPY"],
    "CHFJPY": ["CHF", "JPY"],
}


@dataclass
class EconomicNewsEvent:
    event_id: str
    title: str
    currency: str
    impact: str
    scheduled_datetime: datetime
    actual: str | float | None = None
    forecast: str | float | None = None
    previous: str | float | None = None
    source: str = "MANUAL"
    country: str | None = None
    category: str | None = None

    def to_dict(
        self,
        *,
        timezone: ZoneInfo | None = None,
    ) -> dict[str, Any]:
        event_datetime = self.scheduled_datetime

        if timezone is not None:
            if event_datetime.tzinfo is None:
                event_datetime = event_datetime.replace(
                    tzinfo=timezone,
                )
            else:
                event_datetime = event_datetime.astimezone(
                    timezone,
                )

        return {
            "event_id": self.event_id,
            "title": self.title,
            "currency": self.currency,
            "impact": self.impact,
            "scheduled_datetime": event_datetime.isoformat(),
            "actual": self.actual,
            "forecast": self.forecast,
            "previous": self.previous,
            "source": self.source,
            "country": self.country,
            "category": self.category,
        }


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """Safely convert a value into a finite float."""

    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default

    if not math.isfinite(number):
        return default

    return number


def normalize_currency(currency: str) -> str:
    normalized = currency.strip().upper()

    if normalized not in SUPPORTED_CURRENCIES:
        raise ValueError(
            f"Unsupported economic-news currency: {currency}"
        )

    return normalized


def normalize_impact(impact: str) -> str:
    normalized = impact.strip().upper()

    if normalized not in IMPACT_LEVELS:
        raise ValueError(
            f"Unsupported economic-news impact: {impact}"
        )

    return normalized


def normalize_market_symbol(symbol: str) -> str:
    if not isinstance(
        symbol,
        str,
    ):
        raise ValueError(
            "Market symbol must be a string."
        )

    normalized = (
        symbol.strip()
        .upper()
        .replace("/", "")
        .replace("-", "")
        .replace("_", "")
        .replace(" ", "")
    )

    if not normalized:
        raise ValueError(
            "Market symbol cannot be empty."
        )

    if len(normalized) > 32:
        raise ValueError(
            "Market symbol is too long."
        )

    if not all(
        character.isalnum()
        or character == "."
        for character in normalized
    ):
        raise ValueError(
            "Market symbol contains unsupported characters."
        )

    return normalized


def normalize_event_datetime(
    value: datetime,
    timezone: ZoneInfo,
) -> datetime:
    if not isinstance(
        value,
        datetime,
    ):
        raise ValueError(
            "Economic-news datetime must be a datetime value."
        )

    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone
        )

    return value.astimezone(
        timezone
    )


def detect_event_category(title: str) -> str:
    normalized_title = title.strip().lower()

    for category, keywords in EVENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in normalized_title:
                return category

    return "OTHER"


def detect_currency_from_title(
    title: str,
) -> str | None:
    normalized_title = title.upper()

    for keyword, currency in CENTRAL_BANK_CURRENCY_MAP.items():
        if keyword in normalized_title:
            return currency

    for currency in SUPPORTED_CURRENCIES:
        if currency in normalized_title:
            return currency

    return None


def infer_symbol_currencies(
    symbol: str,
) -> list[str]:
    normalized_symbol = normalize_market_symbol(symbol)

    mapped = SYMBOL_CURRENCY_MAP.get(normalized_symbol)

    if mapped:
        return list(mapped)

    currencies: list[str] = []

    for currency in SUPPORTED_CURRENCIES:
        if currency in normalized_symbol:
            currencies.append(currency)

    return sorted(set(currencies))


class EconomicNewsIntelligence:
    def __init__(
        self,
        *,
        timezone_name: str = NEWS_TIMEZONE,
    ) -> None:
        self.timezone_name = timezone_name
        self.timezone = ZoneInfo(timezone_name)
        self._events: dict[str, EconomicNewsEvent] = {}
        self._events_lock = RLock()

    def get_current_datetime(
        self,
        current_datetime: datetime | None = None,
    ) -> datetime:
        if current_datetime is None:
            return datetime.now(self.timezone)

        return normalize_event_datetime(
            current_datetime,
            self.timezone,
        )

    def register_event(
        self,
        *,
        event_id: str,
        title: str,
        currency: str,
        impact: str,
        scheduled_datetime: datetime,
        actual: str | float | None = None,
        forecast: str | float | None = None,
        previous: str | float | None = None,
        source: str = "MANUAL",
        country: str | None = None,
        category: str | None = None,
    ) -> dict[str, Any]:
        normalized_event_id = str(
            event_id
        ).strip()

        if not normalized_event_id:
            raise ValueError(
                "Economic-news event ID cannot be empty."
            )

        if len(
            normalized_event_id
        ) > MAXIMUM_EVENT_ID_LENGTH:
            raise ValueError(
                "Economic-news event ID is too long."
            )

        normalized_title = str(
            title
        ).strip()

        if not normalized_title:
            raise ValueError(
                "Economic-news event title cannot be empty."
            )

        if len(
            normalized_title
        ) > MAXIMUM_EVENT_TITLE_LENGTH:
            raise ValueError(
                "Economic-news event title is too long."
            )

        normalized_currency = normalize_currency(currency)
        normalized_impact = normalize_impact(impact)
        normalized_datetime = normalize_event_datetime(
            scheduled_datetime,
            self.timezone,
        )

        event_category = (
            category.strip().upper()
            if category and category.strip()
            else detect_event_category(normalized_title)
        )

        event = EconomicNewsEvent(
            event_id=normalized_event_id,
            title=normalized_title,
            currency=normalized_currency,
            impact=normalized_impact,
            scheduled_datetime=normalized_datetime,
            actual=actual,
            forecast=forecast,
            previous=previous,
            source=(
                str(source).strip().upper()[
                    :MAXIMUM_TEXT_FIELD_LENGTH
                ]
                or "MANUAL"
            ),
            country=(
                str(country).strip()[
                    :MAXIMUM_TEXT_FIELD_LENGTH
                ]
                if country
                else None
            ),
            category=event_category[
                :MAXIMUM_TEXT_FIELD_LENGTH
            ],
        )

        with self._events_lock:
            self._events[
                normalized_event_id
            ] = event

        return event.to_dict(
            timezone=self.timezone,
        )

    def register_events(
        self,
        events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not isinstance(
            events,
            list,
        ):
            raise ValueError(
                "Economic-news events must be provided as a list."
            )

        if len(events) > MAXIMUM_EVENT_BATCH_SIZE:
            raise ValueError(
                "Too many economic-news events were provided."
            )

        registered: list[dict[str, Any]] = []

        for event_data in events:
            if not isinstance(
                event_data,
                dict,
            ):
                raise ValueError(
                    "Each economic-news event must be an object."
                )

            if "scheduled_datetime" not in event_data:
                raise ValueError(
                    "Each economic-news event requires scheduled_datetime."
                )

            registered.append(
                self.register_event(
                    event_id=str(
                        event_data.get(
                            "event_id",
                            "",
                        )
                    ),
                    title=str(
                        event_data.get(
                            "title",
                            "",
                        )
                    ),
                    currency=str(
                        event_data.get(
                            "currency",
                            "",
                        )
                    ),
                    impact=str(
                        event_data.get(
                            "impact",
                            "",
                        )
                    ),
                    scheduled_datetime=event_data[
                        "scheduled_datetime"
                    ],
                    actual=event_data.get("actual"),
                    forecast=event_data.get("forecast"),
                    previous=event_data.get("previous"),
                    source=str(
                        event_data.get(
                            "source",
                            "MANUAL",
                        )
                    ),
                    country=event_data.get("country"),
                    category=event_data.get("category"),
                )
            )

        return registered

    def remove_event(
        self,
        event_id: str,
    ) -> bool:
        normalized_event_id = event_id.strip()

        if not normalized_event_id:
            return False

        with self._events_lock:
            return (
                self._events.pop(
                    normalized_event_id,
                    None,
                )
                is not None
            )

    def clear_events(self) -> int:
        with self._events_lock:
            count = len(
                self._events
            )
            self._events.clear()

        return count

    def get_all_events(self) -> list[EconomicNewsEvent]:
        with self._events_lock:
            events = list(
                self._events.values()
            )

        return sorted(
            events,
            key=lambda event: event.scheduled_datetime,
        )

    def get_calendar(
        self,
        *,
        start_datetime: datetime | None = None,
        end_datetime: datetime | None = None,
        currencies: list[str] | None = None,
        impacts: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        events = self.get_all_events()

        normalized_start = (
            normalize_event_datetime(
                start_datetime,
                self.timezone,
            )
            if start_datetime
            else None
        )

        normalized_end = (
            normalize_event_datetime(
                end_datetime,
                self.timezone,
            )
            if end_datetime
            else None
        )

        if (
            normalized_start is not None
            and normalized_end is not None
            and normalized_end < normalized_start
        ):
            raise ValueError(
                "Economic-news end datetime cannot be before start datetime."
            )

        normalized_currencies = (
            {
                normalize_currency(currency)
                for currency in currencies
            }
            if currencies
            else None
        )

        normalized_impacts = (
            {
                normalize_impact(impact)
                for impact in impacts
            }
            if impacts
            else None
        )

        filtered_events: list[dict[str, Any]] = []

        for event in events:
            if (
                normalized_start is not None
                and event.scheduled_datetime < normalized_start
            ):
                continue

            if (
                normalized_end is not None
                and event.scheduled_datetime > normalized_end
            ):
                continue

            if (
                normalized_currencies is not None
                and event.currency not in normalized_currencies
            ):
                continue

            if (
                normalized_impacts is not None
                and event.impact not in normalized_impacts
            ):
                continue

            filtered_events.append(
                event.to_dict(
                    timezone=self.timezone,
                )
            )

        return filtered_events

    def get_upcoming_events(
        self,
        *,
        current_datetime: datetime | None = None,
        hours_ahead: int = 24,
        currencies: list[str] | None = None,
        impacts: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        if not isinstance(
            hours_ahead,
            int,
        ) or isinstance(
            hours_ahead,
            bool,
        ):
            raise ValueError(
                "Hours ahead must be an integer."
            )

        if not 1 <= hours_ahead <= MAXIMUM_HOURS_AHEAD:
            raise ValueError(
                f"Hours ahead must be between 1 and {MAXIMUM_HOURS_AHEAD}."
            )

        local_datetime = self.get_current_datetime(
            current_datetime,
        )

        return self.get_calendar(
            start_datetime=local_datetime,
            end_datetime=local_datetime
            + timedelta(hours=hours_ahead),
            currencies=currencies,
            impacts=impacts,
        )

    def get_high_impact_events(
        self,
        *,
        current_datetime: datetime | None = None,
        hours_ahead: int = 24,
        currencies: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        return self.get_upcoming_events(
            current_datetime=current_datetime,
            hours_ahead=hours_ahead,
            currencies=currencies,
            impacts=["HIGH"],
        )

    def calculate_event_time_difference(
        self,
        event: EconomicNewsEvent,
        current_datetime: datetime,
    ) -> dict[str, int | float]:
        seconds_until_event = (
            event.scheduled_datetime - current_datetime
        ).total_seconds()

        minutes_until_event = (
            seconds_until_event / 60
        )

        return {
            "seconds_until_event": round(
                seconds_until_event,
                2,
            ),
            "minutes_until_event": round(
                minutes_until_event,
                2,
            ),
            "absolute_minutes_from_event": round(
                abs(minutes_until_event),
                2,
            ),
        }

    def analyze_event_blackout(
        self,
        event: EconomicNewsEvent,
        current_datetime: datetime,
    ) -> dict[str, Any]:
        window = BLACKOUT_WINDOWS[event.impact]

        minutes_before = int(
            window["minutes_before"]
        )
        minutes_after = int(
            window["minutes_after"]
        )

        blackout_start = (
            event.scheduled_datetime
            - timedelta(minutes=minutes_before)
        )

        blackout_end = (
            event.scheduled_datetime
            + timedelta(minutes=minutes_after)
        )

        blackout_active = (
            blackout_start
            <= current_datetime
            <= blackout_end
        )

        timing = self.calculate_event_time_difference(
            event,
            current_datetime,
        )

        if current_datetime < blackout_start:
            blackout_status = "UPCOMING"
        elif blackout_active:
            blackout_status = "ACTIVE"
        else:
            blackout_status = "FINISHED"

        return {
            "event_id": event.event_id,
            "blackout_active": blackout_active,
            "blackout_status": blackout_status,
            "blackout_start": blackout_start.isoformat(),
            "blackout_end": blackout_end.isoformat(),
            "minutes_before": minutes_before,
            "minutes_after": minutes_after,
            **timing,
        }

    def calculate_event_risk_score(
        self,
        event: EconomicNewsEvent,
        *,
        current_datetime: datetime,
        symbol_currencies: list[str],
    ) -> float:
        base_score = IMPACT_RISK_SCORES[event.impact]

        time_data = self.calculate_event_time_difference(
            event,
            current_datetime,
        )

        absolute_minutes = float(
            time_data["absolute_minutes_from_event"]
        )

        if absolute_minutes <= 15:
            proximity_multiplier = 1.15
        elif absolute_minutes <= 30:
            proximity_multiplier = 1.05
        elif absolute_minutes <= 60:
            proximity_multiplier = 0.90
        elif absolute_minutes <= 240:
            proximity_multiplier = 0.70
        else:
            proximity_multiplier = 0.45

        currency_multiplier = (
            1.0
            if event.currency in symbol_currencies
            else 0.50
        )

        category_multiplier = 1.0

        if event.category in {
            "INTEREST_RATE_DECISION",
            "CENTRAL_BANK_STATEMENT",
            "NON_FARM_PAYROLLS",
            "INFLATION",
        }:
            category_multiplier = 1.10

        score = (
            base_score
            * proximity_multiplier
            * currency_multiplier
            * category_multiplier
        )

        return round(
            min(max(score, 0.0), 100.0),
            2,
        )

    def determine_news_risk_level(
        self,
        risk_score: float,
    ) -> str:
        if risk_score >= 85:
            return "EXTREME"

        if risk_score >= 70:
            return "HIGH"

        if risk_score >= 45:
            return "MEDIUM"

        if risk_score >= 20:
            return "LOW"

        return "VERY_LOW"

    def calculate_confidence_adjustment(
        self,
        *,
        highest_risk_score: float,
        blackout_active: bool,
        relevant_high_impact_count: int,
        relevant_medium_impact_count: int,
    ) -> dict[str, Any]:
        if blackout_active:
            adjustment = -25.0
            signal = "BLOCK"
        elif highest_risk_score >= 85:
            adjustment = -20.0
            signal = "STRONG_REDUCTION"
        elif highest_risk_score >= 70:
            adjustment = -15.0
            signal = "REDUCE"
        elif highest_risk_score >= 55:
            adjustment = -10.0
            signal = "REDUCE"
        elif highest_risk_score >= 40:
            adjustment = -5.0
            signal = "SMALL_REDUCTION"
        elif highest_risk_score >= 20:
            adjustment = -2.0
            signal = "CAUTION"
        else:
            adjustment = 0.0
            signal = "NEUTRAL"

        if relevant_high_impact_count >= 2:
            adjustment -= 5.0

        if relevant_medium_impact_count >= 3:
            adjustment -= 3.0

        adjustment = max(
            adjustment,
            -35.0,
        )

        return {
            "confidence_adjustment": round(
                adjustment,
                2,
            ),
            "confidence_signal": signal,
            "maximum_confidence_reduction": -35.0,
            "confidence_boost_allowed": False,
        }

    def analyze_symbol(
        self,
        symbol: str,
        *,
        current_datetime: datetime | None = None,
        hours_ahead: int = 24,
    ) -> dict[str, Any]:
        if not isinstance(
            hours_ahead,
            int,
        ) or isinstance(
            hours_ahead,
            bool,
        ):
            raise ValueError(
                "Hours ahead must be an integer."
            )

        if not 1 <= hours_ahead <= MAXIMUM_HOURS_AHEAD:
            raise ValueError(
                f"Hours ahead must be between 1 and {MAXIMUM_HOURS_AHEAD}."
            )

        normalized_symbol = normalize_market_symbol(
            symbol,
        )

        local_datetime = self.get_current_datetime(
            current_datetime,
        )

        symbol_currencies = infer_symbol_currencies(
            normalized_symbol,
        )

        relevant_events: list[dict[str, Any]] = []
        active_blackout_events: list[dict[str, Any]] = []

        highest_risk_score = 0.0
        highest_risk_event: dict[str, Any] | None = None

        high_impact_count = 0
        medium_impact_count = 0
        low_impact_count = 0

        analysis_start = local_datetime - timedelta(
            minutes=60,
        )

        analysis_end = local_datetime + timedelta(
            hours=hours_ahead,
        )

        for event in self.get_all_events():
            if not (
                analysis_start
                <= event.scheduled_datetime
                <= analysis_end
            ):
                continue

            if (
                symbol_currencies
                and event.currency not in symbol_currencies
            ):
                continue

            blackout_data = self.analyze_event_blackout(
                event,
                local_datetime,
            )

            risk_score = self.calculate_event_risk_score(
                event,
                current_datetime=local_datetime,
                symbol_currencies=symbol_currencies,
            )

            risk_level = self.determine_news_risk_level(
                risk_score,
            )

            event_result = {
                **event.to_dict(
                    timezone=self.timezone,
                ),
                "risk_score": risk_score,
                "risk_level": risk_level,
                "blackout": blackout_data,
            }

            relevant_events.append(event_result)

            if blackout_data["blackout_active"]:
                active_blackout_events.append(
                    event_result,
                )

            if event.impact == "HIGH":
                high_impact_count += 1
            elif event.impact == "MEDIUM":
                medium_impact_count += 1
            else:
                low_impact_count += 1

            if risk_score > highest_risk_score:
                highest_risk_score = risk_score
                highest_risk_event = event_result

        relevant_events.sort(
            key=lambda item: item[
                "scheduled_datetime"
            ]
        )

        blackout_active = bool(
            active_blackout_events
        )

        confidence_adjustment = (
            self.calculate_confidence_adjustment(
                highest_risk_score=highest_risk_score,
                blackout_active=blackout_active,
                relevant_high_impact_count=high_impact_count,
                relevant_medium_impact_count=medium_impact_count,
            )
        )

        if blackout_active:
            trade_status = "NO_TRADE"
            decision = "WAIT"
            news_approval = False
        elif highest_risk_score >= 85:
            trade_status = "NO_TRADE"
            decision = "WAIT"
            news_approval = False
        else:
            trade_status = "NEWS_CHECK_PASSED"
            decision = "CONTINUE_ANALYSIS"
            news_approval = True

        return {
            "project": "Blue-Trading-AI",
            "version": 23,
            "module": "Economic News Intelligence",
            "symbol": normalized_symbol,
            "symbol_currencies": symbol_currencies,
            "timezone": self.timezone_name,
            "local_datetime": local_datetime.isoformat(),
            "hours_analyzed": hours_ahead,
            "economic_calendar_available": bool(
                self.get_all_events()
            ),
            "event_count": len(relevant_events),
            "high_impact_event_count": high_impact_count,
            "medium_impact_event_count": (
                medium_impact_count
            ),
            "low_impact_event_count": low_impact_count,
            "blackout_active": blackout_active,
            "active_blackout_count": len(
                active_blackout_events
            ),
            "active_blackout_events": (
                active_blackout_events
            ),
            "highest_news_risk_score": round(
                highest_risk_score,
                2,
            ),
            "highest_news_risk_level": (
                self.determine_news_risk_level(
                    highest_risk_score,
                )
            ),
            "highest_risk_event": highest_risk_event,
            "relevant_events": relevant_events,
            "confidence_adjustment": (
                confidence_adjustment
            ),
            "news_approval": news_approval,
            "decision": decision,
            "signal": trade_status,
            "analysis_only": True,
            "broker_connection_enabled": False,
            "trade_execution_enabled": False,
        }

    def apply_confidence(
        self,
        *,
        symbol: str,
        base_confidence: float,
        current_datetime: datetime | None = None,
        hours_ahead: int = 24,
    ) -> dict[str, Any]:
        normalized_confidence = safe_float(
            base_confidence,
            default=float("nan"),
        )

        if not math.isfinite(
            normalized_confidence
        ):
            raise ValueError(
                "Base confidence must be a valid finite number."
            )

        if not 0.0 <= normalized_confidence <= 100.0:
            raise ValueError(
                "Base confidence must be between 0 and 100."
            )

        news_analysis = self.analyze_symbol(
            symbol,
            current_datetime=current_datetime,
            hours_ahead=hours_ahead,
        )

        adjustment = float(
            news_analysis[
                "confidence_adjustment"
            ]["confidence_adjustment"]
        )

        adjusted_confidence = max(
            0.0,
            min(
                100.0,
                normalized_confidence + adjustment,
            ),
        )

        confidence_passed = (
            adjusted_confidence
            >= MINIMUM_NEWS_CONFIDENCE
        )

        news_approval = bool(
            news_analysis["news_approval"]
        )

        signal_approved = (
            confidence_passed
            and news_approval
        )

        return {
            "project": "Blue-Trading-AI",
            "version": 23,
            "module": (
                "Economic News Confidence Adjustment"
            ),
            "symbol": news_analysis["symbol"],
            "base_confidence": round(
                normalized_confidence,
                2,
            ),
            "news_confidence_adjustment": round(
                adjustment,
                2,
            ),
            "adjusted_confidence": round(
                adjusted_confidence,
                2,
            ),
            "minimum_required_confidence": (
                MINIMUM_NEWS_CONFIDENCE
            ),
            "confidence_passed": confidence_passed,
            "news_approval": news_approval,
            "signal_approved": signal_approved,
            "blackout_active": news_analysis[
                "blackout_active"
            ],
            "highest_news_risk_score": (
                news_analysis[
                    "highest_news_risk_score"
                ]
            ),
            "highest_news_risk_level": (
                news_analysis[
                    "highest_news_risk_level"
                ]
            ),
            "decision": (
                "CONTINUE_ANALYSIS"
                if signal_approved
                else "WAIT"
            ),
            "signal": (
                "NEWS_APPROVED"
                if signal_approved
                else "NO_TRADE"
            ),
            "news_analysis": news_analysis,
            "analysis_only": True,
            "broker_connection_enabled": False,
            "trade_execution_enabled": False,
        }

    def get_configuration(self) -> dict[str, Any]:
        return {
            "project": "Blue-Trading-AI",
            "version": 23,
            "module": "Economic News Intelligence",
            "timezone": self.timezone_name,
            "supported_currencies": sorted(
                SUPPORTED_CURRENCIES
            ),
            "impact_levels": sorted(
                IMPACT_LEVELS
            ),
            "blackout_windows": {
                impact: dict(window)
                for impact, window
                in BLACKOUT_WINDOWS.items()
            },
            "impact_risk_scores": dict(
                IMPACT_RISK_SCORES
            ),
            "minimum_news_confidence": (
                MINIMUM_NEWS_CONFIDENCE
            ),
            "event_categories": sorted(
                EVENT_KEYWORDS.keys()
            ),
            "economic_calendar_provider": (
                "NOT_CONNECTED"
            ),
            "manual_event_registration_enabled": True,
            "analysis_only": True,
            "broker_connection_enabled": False,
            "trade_execution_enabled": False,
        }


economic_news_intelligence = (
    EconomicNewsIntelligence()
)


def register_economic_news_event(
    *,
    event_id: str,
    title: str,
    currency: str,
    impact: str,
    scheduled_datetime: datetime,
    actual: str | float | None = None,
    forecast: str | float | None = None,
    previous: str | float | None = None,
    source: str = "MANUAL",
    country: str | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    return economic_news_intelligence.register_event(
        event_id=event_id,
        title=title,
        currency=currency,
        impact=impact,
        scheduled_datetime=scheduled_datetime,
        actual=actual,
        forecast=forecast,
        previous=previous,
        source=source,
        country=country,
        category=category,
    )


def register_economic_news_events(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return economic_news_intelligence.register_events(
        events,
    )


def remove_economic_news_event(
    event_id: str,
) -> bool:
    return economic_news_intelligence.remove_event(
        event_id,
    )


def clear_economic_news_events() -> int:
    return economic_news_intelligence.clear_events()


def get_economic_news_calendar(
    *,
    start_datetime: datetime | None = None,
    end_datetime: datetime | None = None,
    currencies: list[str] | None = None,
    impacts: list[str] | None = None,
) -> list[dict[str, Any]]:
    return economic_news_intelligence.get_calendar(
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        currencies=currencies,
        impacts=impacts,
    )


def get_upcoming_economic_news(
    *,
    current_datetime: datetime | None = None,
    hours_ahead: int = 24,
    currencies: list[str] | None = None,
    impacts: list[str] | None = None,
) -> list[dict[str, Any]]:
    return economic_news_intelligence.get_upcoming_events(
        current_datetime=current_datetime,
        hours_ahead=hours_ahead,
        currencies=currencies,
        impacts=impacts,
    )


def get_high_impact_economic_news(
    *,
    current_datetime: datetime | None = None,
    hours_ahead: int = 24,
    currencies: list[str] | None = None,
) -> list[dict[str, Any]]:
    return economic_news_intelligence.get_high_impact_events(
        current_datetime=current_datetime,
        hours_ahead=hours_ahead,
        currencies=currencies,
    )


def analyze_economic_news(
    symbol: str,
    *,
    current_datetime: datetime | None = None,
    hours_ahead: int = 24,
) -> dict[str, Any]:
    return economic_news_intelligence.analyze_symbol(
        symbol,
        current_datetime=current_datetime,
        hours_ahead=hours_ahead,
    )


def apply_economic_news_confidence(
    *,
    symbol: str,
    base_confidence: float,
    current_datetime: datetime | None = None,
    hours_ahead: int = 24,
) -> dict[str, Any]:
    return economic_news_intelligence.apply_confidence(
        symbol=symbol,
        base_confidence=base_confidence,
        current_datetime=current_datetime,
        hours_ahead=hours_ahead,
    )


def get_economic_news_configuration() -> dict[str, Any]:
    return economic_news_intelligence.get_configuration()

__all__ = [
    "BLACKOUT_WINDOWS",
    "CENTRAL_BANK_CURRENCY_MAP",
    "EVENT_KEYWORDS",
    "EconomicNewsEvent",
    "EconomicNewsIntelligence",
    "IMPACT_LEVELS",
    "IMPACT_RISK_SCORES",
    "MAXIMUM_EVENT_BATCH_SIZE",
    "MAXIMUM_EVENT_ID_LENGTH",
    "MAXIMUM_EVENT_TITLE_LENGTH",
    "MAXIMUM_HOURS_AHEAD",
    "MINIMUM_NEWS_CONFIDENCE",
    "NEWS_TIMEZONE",
    "SUPPORTED_CURRENCIES",
    "SYMBOL_CURRENCY_MAP",
    "analyze_economic_news",
    "apply_economic_news_confidence",
    "clear_economic_news_events",
    "detect_currency_from_title",
    "detect_event_category",
    "economic_news_intelligence",
    "get_economic_news_calendar",
    "get_economic_news_configuration",
    "get_high_impact_economic_news",
    "get_upcoming_economic_news",
    "infer_symbol_currencies",
    "normalize_currency",
    "normalize_event_datetime",
    "normalize_impact",
    "normalize_market_symbol",
    "register_economic_news_event",
    "register_economic_news_events",
    "remove_economic_news_event",
    "safe_float",
]