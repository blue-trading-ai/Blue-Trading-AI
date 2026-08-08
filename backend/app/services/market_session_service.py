from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any, Final
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


# ============================================================
# BLUE-TRADING-AI
# VERSION 22 PART 1
# MARKET SESSION INTELLIGENCE ENGINE
# ============================================================

MARKET_TIMEZONE: Final = "Asia/Kuala_Lumpur"
MINIMUM_REQUIRED_CONFIDENCE: Final = 80.0
MAXIMUM_SYMBOL_LENGTH: Final = 30

SESSION_WINDOWS: Final[dict[str, dict[str, str]]] = {
    "ASIAN": {
        "display_name": "Asian Session",
        "start": "07:00",
        "end": "16:00",
    },
    "EUROPEAN": {
        "display_name": "European Session",
        "start": "15:00",
        "end": "00:00",
    },
    "US": {
        "display_name": "US Session",
        "start": "20:00",
        "end": "05:00",
    },
}

SYMBOL_SESSION_PREFERENCES: Final[dict[str, list[str]]] = {
    "XAUUSD": ["EUROPEAN", "US", "EUROPEAN_US_OVERLAP"],
    "GBPUSD": ["EUROPEAN", "US", "EUROPEAN_US_OVERLAP"],
    "EURUSD": ["EUROPEAN", "US", "EUROPEAN_US_OVERLAP"],
    "USDJPY": ["ASIAN", "EUROPEAN"],
    "AUDUSD": ["ASIAN", "EUROPEAN"],
    "NZDUSD": ["ASIAN", "EUROPEAN"],
    "BTCUSD": ["ASIAN", "EUROPEAN", "US", "EUROPEAN_US_OVERLAP"],
    "ETHUSD": ["ASIAN", "EUROPEAN", "US", "EUROPEAN_US_OVERLAP"],
}

DEFAULT_SESSION_PREFERENCES: Final[list[str]] = [
    "EUROPEAN",
    "US",
    "EUROPEAN_US_OVERLAP",
]


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """Convert a value to a finite float."""

    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default

    if not math.isfinite(number):
        return default

    return number


def _clamp(
    value: Any,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    number = _safe_float(
        value,
        default=minimum,
    )

    return max(
        minimum,
        min(
            number,
            maximum,
        ),
    )


def normalize_market_symbol(
    symbol: str,
) -> str:
    normalized = (
        str(symbol or "")
        .strip()
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

    if len(normalized) > MAXIMUM_SYMBOL_LENGTH:
        raise ValueError(
            "Market symbol is too long."
        )

    if not normalized.isalnum():
        raise ValueError(
            "Market symbol contains unsupported characters."
        )

    return normalized


def parse_session_time(
    value: str,
) -> time:
    try:
        hour_text, minute_text = str(
            value
        ).split(
            ":",
            maxsplit=1,
        )
        parsed = time(
            hour=int(hour_text),
            minute=int(minute_text),
        )
    except (
        ValueError,
        TypeError,
    ) as exc:
        raise ValueError(
            f"Invalid session time: {value}"
        ) from exc

    return parsed


def time_to_minutes(
    value: time,
) -> int:
    if not isinstance(
        value,
        time,
    ):
        raise TypeError(
            "value must be a datetime.time instance."
        )

    return (
        value.hour * 60
    ) + value.minute


def is_time_inside_session(
    current_time: time,
    start_time: time,
    end_time: time,
) -> bool:
    current_minutes = time_to_minutes(
        current_time
    )
    start_minutes = time_to_minutes(
        start_time
    )
    end_minutes = time_to_minutes(
        end_time
    )

    if start_minutes < end_minutes:
        return (
            start_minutes
            <= current_minutes
            < end_minutes
        )

    if start_minutes > end_minutes:
        return (
            current_minutes
            >= start_minutes
            or current_minutes
            < end_minutes
        )

    # Equal start/end represents a full-day window,
    # preserving Version 22 behavior.
    return True


def calculate_minutes_until_session_end(
    current_time: time,
    end_time: time,
) -> int:
    current_minutes = time_to_minutes(
        current_time
    )
    end_minutes = time_to_minutes(
        end_time
    )
    difference = (
        end_minutes
        - current_minutes
    )

    if difference <= 0:
        difference += 24 * 60

    return difference


@dataclass(frozen=True)
class MarketSessionState:
    session_name: str
    display_name: str
    is_active: bool
    start_time: str
    end_time: str
    minutes_until_close: int | None

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "session_name": self.session_name,
            "display_name": self.display_name,
            "is_active": self.is_active,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "minutes_until_close": self.minutes_until_close,
        }


class MarketSessionIntelligence:
    def __init__(
        self,
        *,
        timezone_name: str = MARKET_TIMEZONE,
    ) -> None:
        normalized_timezone = str(
            timezone_name or ""
        ).strip()

        if not normalized_timezone:
            raise ValueError(
                "timezone_name cannot be empty."
            )

        try:
            timezone_value = ZoneInfo(
                normalized_timezone
            )
        except (
            ZoneInfoNotFoundError,
            ValueError,
        ) as exc:
            raise ValueError(
                "Unsupported market timezone."
            ) from exc

        self.timezone_name = normalized_timezone
        self.timezone = timezone_value

    def get_current_datetime(
        self,
        current_datetime: datetime | None = None,
    ) -> datetime:
        if current_datetime is None:
            return datetime.now(
                self.timezone
            )

        if not isinstance(
            current_datetime,
            datetime,
        ):
            raise ValueError(
                "current_datetime must be a datetime."
            )

        if current_datetime.tzinfo is None:
            return current_datetime.replace(
                tzinfo=self.timezone
            )

        return current_datetime.astimezone(
            self.timezone
        )

    def analyze_session(
        self,
        session_name: str,
        current_datetime: datetime | None = None,
    ) -> MarketSessionState:
        normalized_name = str(
            session_name or ""
        ).strip().upper()

        session_config = SESSION_WINDOWS.get(
            normalized_name
        )

        if session_config is None:
            raise ValueError(
                f"Unsupported market session: {session_name}"
            )

        local_datetime = self.get_current_datetime(
            current_datetime
        )
        current_time = local_datetime.time().replace(
            tzinfo=None
        )
        start_time = parse_session_time(
            session_config["start"]
        )
        end_time = parse_session_time(
            session_config["end"]
        )
        is_active = is_time_inside_session(
            current_time,
            start_time,
            end_time,
        )
        minutes_until_close = (
            calculate_minutes_until_session_end(
                current_time,
                end_time,
            )
            if is_active
            else None
        )

        return MarketSessionState(
            session_name=normalized_name,
            display_name=session_config["display_name"],
            is_active=is_active,
            start_time=session_config["start"],
            end_time=session_config["end"],
            minutes_until_close=minutes_until_close,
        )

    def get_all_sessions(
        self,
        current_datetime: datetime | None = None,
    ) -> list[MarketSessionState]:
        return [
            self.analyze_session(
                name,
                current_datetime,
            )
            for name in SESSION_WINDOWS
        ]

    def get_active_sessions(
        self,
        current_datetime: datetime | None = None,
    ) -> list[MarketSessionState]:
        return [
            session
            for session in self.get_all_sessions(
                current_datetime
            )
            if session.is_active
        ]

    def detect_overlap(
        self,
        active_session_names: list[str],
    ) -> dict[str, Any]:
        active_names = {
            str(name).strip().upper()
            for name in (
                active_session_names
                if isinstance(
                    active_session_names,
                    list,
                )
                else []
            )
        }
        overlaps: list[str] = []

        if {
            "ASIAN",
            "EUROPEAN",
        }.issubset(
            active_names
        ):
            overlaps.append(
                "ASIAN_EUROPEAN_OVERLAP"
            )

        if {
            "EUROPEAN",
            "US",
        }.issubset(
            active_names
        ):
            overlaps.append(
                "EUROPEAN_US_OVERLAP"
            )

        if {
            "ASIAN",
            "US",
        }.issubset(
            active_names
        ):
            overlaps.append(
                "ASIAN_US_OVERLAP"
            )

        return {
            "overlap_active": bool(
                overlaps
            ),
            "overlap_count": len(
                overlaps
            ),
            "overlaps": overlaps,
        }

    def calculate_session_strength(
        self,
        active_session_names: list[str],
        overlap_data: dict[str, Any],
    ) -> float:
        if not active_session_names:
            return 20.0

        score = 45.0

        if "ASIAN" in active_session_names:
            score += 10.0
        if "EUROPEAN" in active_session_names:
            score += 20.0
        if "US" in active_session_names:
            score += 20.0
        if bool(
            overlap_data.get(
                "overlap_active",
                False,
            )
        ):
            score += 15.0

        return _clamp(
            score
        )

    def calculate_liquidity_score(
        self,
        active_session_names: list[str],
        overlap_data: dict[str, Any],
    ) -> float:
        if not active_session_names:
            return 20.0

        score = 35.0

        if "ASIAN" in active_session_names:
            score += 10.0
        if "EUROPEAN" in active_session_names:
            score += 20.0
        if "US" in active_session_names:
            score += 20.0

        overlaps = overlap_data.get(
            "overlaps",
            [],
        )

        if (
            isinstance(
                overlaps,
                list,
            )
            and "EUROPEAN_US_OVERLAP"
            in overlaps
        ):
            score += 20.0

        return _clamp(
            score
        )

    def calculate_volatility_score(
        self,
        active_session_names: list[str],
        overlap_data: dict[str, Any],
    ) -> float:
        if not active_session_names:
            return 15.0

        score = 30.0

        if "ASIAN" in active_session_names:
            score += 10.0
        if "EUROPEAN" in active_session_names:
            score += 25.0
        if "US" in active_session_names:
            score += 25.0
        if bool(
            overlap_data.get(
                "overlap_active",
                False,
            )
        ):
            score += 15.0

        return _clamp(
            score
        )

    def determine_market_activity(
        self,
        session_strength: float,
        liquidity_score: float,
        volatility_score: float,
    ) -> str:
        average_score = (
            _clamp(
                session_strength
            )
            + _clamp(
                liquidity_score
            )
            + _clamp(
                volatility_score
            )
        ) / 3.0

        if average_score >= 85.0:
            return "VERY_HIGH"
        if average_score >= 70.0:
            return "HIGH"
        if average_score >= 50.0:
            return "MODERATE"
        if average_score >= 30.0:
            return "LOW"

        return "VERY_LOW"

    def determine_best_session(
        self,
        active_session_names: list[str],
        overlap_data: dict[str, Any],
    ) -> str | None:
        overlaps = overlap_data.get(
            "overlaps",
            [],
        )

        if (
            isinstance(
                overlaps,
                list,
            )
            and "EUROPEAN_US_OVERLAP"
            in overlaps
        ):
            return "EUROPEAN_US_OVERLAP"

        if "US" in active_session_names:
            return "US"
        if "EUROPEAN" in active_session_names:
            return "EUROPEAN"
        if "ASIAN" in active_session_names:
            return "ASIAN"

        return None

    def calculate_symbol_session_score(
        self,
        symbol: str,
        active_session_names: list[str],
        overlap_data: dict[str, Any],
    ) -> dict[str, Any]:
        normalized_symbol = normalize_market_symbol(
            symbol
        )
        preferred_sessions = list(
            SYMBOL_SESSION_PREFERENCES.get(
                normalized_symbol,
                DEFAULT_SESSION_PREFERENCES,
            )
        )

        active_conditions = list(
            active_session_names
        )

        overlaps = overlap_data.get(
            "overlaps",
            [],
        )

        if isinstance(
            overlaps,
            list,
        ):
            active_conditions.extend(
                overlaps
            )

        matched_preferences = list(
            dict.fromkeys(
                condition
                for condition in active_conditions
                if condition in preferred_sessions
            )
        )

        if not active_conditions:
            score = 25.0
        elif matched_preferences:
            score = (
                75.0
                + min(
                    len(
                        matched_preferences
                    )
                    * 7.5,
                    25.0,
                )
            )
        else:
            score = 50.0

        return {
            "symbol": normalized_symbol,
            "preferred_sessions": preferred_sessions,
            "matched_preferences": matched_preferences,
            "symbol_session_score": round(
                _clamp(
                    score
                ),
                2,
            ),
            "preferred_session_active": bool(
                matched_preferences
            ),
        }

    def calculate_confidence_adjustment(
        self,
        *,
        session_strength: float,
        liquidity_score: float,
        volatility_score: float,
        symbol_session_score: float,
        overlap_active: bool,
    ) -> dict[str, Any]:
        combined_score = (
            _clamp(
                session_strength
            )
            * 0.25
            + _clamp(
                liquidity_score
            )
            * 0.25
            + _clamp(
                volatility_score
            )
            * 0.20
            + _clamp(
                symbol_session_score
            )
            * 0.30
        )

        if combined_score >= 85.0:
            adjustment, signal = 5.0, "BOOST"
        elif combined_score >= 70.0:
            adjustment, signal = 3.0, "BOOST"
        elif combined_score >= 55.0:
            adjustment, signal = 1.0, "SMALL_BOOST"
        elif combined_score >= 40.0:
            adjustment, signal = 0.0, "NEUTRAL"
        elif combined_score >= 25.0:
            adjustment, signal = -3.0, "REDUCE"
        else:
            adjustment, signal = -5.0, "STRONG_REDUCTION"

        if (
            overlap_active is True
            and adjustment > 0.0
        ):
            adjustment = min(
                adjustment + 1.0,
                6.0,
            )

        return {
            "combined_session_score": round(
                _clamp(
                    combined_score
                ),
                2,
            ),
            "confidence_adjustment": adjustment,
            "confidence_signal": signal,
            "maximum_confidence_boost": 6.0,
            "maximum_confidence_reduction": -5.0,
        }

    def analyze(
        self,
        symbol: str,
        current_datetime: datetime | None = None,
    ) -> dict[str, Any]:
        normalized_symbol = normalize_market_symbol(
            symbol
        )
        local_datetime = self.get_current_datetime(
            current_datetime
        )
        all_sessions = self.get_all_sessions(
            local_datetime
        )
        active_sessions = [
            session
            for session in all_sessions
            if session.is_active
        ]
        active_session_names = [
            session.session_name
            for session in active_sessions
        ]
        overlap_data = self.detect_overlap(
            active_session_names
        )

        session_strength = self.calculate_session_strength(
            active_session_names,
            overlap_data,
        )
        liquidity_score = self.calculate_liquidity_score(
            active_session_names,
            overlap_data,
        )
        volatility_score = self.calculate_volatility_score(
            active_session_names,
            overlap_data,
        )
        market_activity = self.determine_market_activity(
            session_strength,
            liquidity_score,
            volatility_score,
        )
        best_session = self.determine_best_session(
            active_session_names,
            overlap_data,
        )
        symbol_analysis = self.calculate_symbol_session_score(
            normalized_symbol,
            active_session_names,
            overlap_data,
        )
        confidence_adjustment = (
            self.calculate_confidence_adjustment(
                session_strength=session_strength,
                liquidity_score=liquidity_score,
                volatility_score=volatility_score,
                symbol_session_score=symbol_analysis[
                    "symbol_session_score"
                ],
                overlap_active=bool(
                    overlap_data.get(
                        "overlap_active",
                        False,
                    )
                ),
            )
        )

        return {
            "project": "Blue-Trading-AI",
            "version": 22,
            "module": "Market Session Intelligence Engine",
            "symbol": normalized_symbol,
            "timezone": self.timezone_name,
            "local_datetime": local_datetime.isoformat(),
            "local_date": local_datetime.date().isoformat(),
            "local_time": (
                local_datetime.time()
                .replace(
                    tzinfo=None
                )
                .isoformat(
                    timespec="seconds"
                )
            ),
            "market_open": bool(
                active_sessions
            ),
            "active_session_count": len(
                active_sessions
            ),
            "active_sessions": [
                session.to_dict()
                for session in active_sessions
            ],
            "all_sessions": [
                session.to_dict()
                for session in all_sessions
            ],
            "overlap": overlap_data,
            "best_active_session": best_session,
            "session_strength_score": round(
                session_strength,
                2,
            ),
            "session_liquidity_score": round(
                liquidity_score,
                2,
            ),
            "session_volatility_score": round(
                volatility_score,
                2,
            ),
            "market_activity_level": market_activity,
            "symbol_session_analysis": symbol_analysis,
            "confidence_adjustment": confidence_adjustment,
            "analysis_only": True,
            "broker_connection_enabled": False,
            "trade_execution_enabled": False,
        }


market_session_intelligence = MarketSessionIntelligence()


def analyze_market_session(
    symbol: str,
    current_datetime: datetime | None = None,
) -> dict[str, Any]:
    return market_session_intelligence.analyze(
        symbol=symbol,
        current_datetime=current_datetime,
    )


def get_current_market_sessions(
    current_datetime: datetime | None = None,
) -> list[dict[str, Any]]:
    sessions = (
        market_session_intelligence.get_active_sessions(
            current_datetime
        )
    )

    return [
        session.to_dict()
        for session in sessions
    ]


def get_market_session_configuration() -> dict[str, Any]:
    return {
        "project": "Blue-Trading-AI",
        "version": 22,
        "timezone": MARKET_TIMEZONE,
        "sessions": {
            key: dict(
                value
            )
            for key, value in SESSION_WINDOWS.items()
        },
        "symbol_preferences": {
            key: list(
                value
            )
            for key, value in SYMBOL_SESSION_PREFERENCES.items()
        },
        "default_preferences": list(
            DEFAULT_SESSION_PREFERENCES
        ),
    }


def apply_market_session_confidence(
    symbol: str,
    base_confidence: float,
    current_datetime: datetime | None = None,
) -> dict[str, Any]:
    """
    Apply the Version 22 market-session confidence adjustment
    to an existing signal confidence score.

    The result remains analysis-only and does not execute trades.
    """

    normalized_confidence = _safe_float(
        base_confidence,
        default=float("nan"),
    )

    if not math.isfinite(
        normalized_confidence
    ):
        raise ValueError(
            "Base confidence must be a valid finite number."
        )

    if not (
        0.0
        <= normalized_confidence
        <= 100.0
    ):
        raise ValueError(
            "Base confidence must be between 0 and 100."
        )

    session_analysis = analyze_market_session(
        symbol=symbol,
        current_datetime=current_datetime,
    )

    adjustment_data = session_analysis.get(
        "confidence_adjustment",
        {},
    )

    if not isinstance(
        adjustment_data,
        dict,
    ):
        adjustment_data = {}

    confidence_adjustment = _safe_float(
        adjustment_data.get(
            "confidence_adjustment",
            0.0,
        ),
        0.0,
    )

    confidence_adjustment = max(
        -5.0,
        min(
            confidence_adjustment,
            6.0,
        ),
    )

    adjusted_confidence = _clamp(
        normalized_confidence
        + confidence_adjustment,
        0.0,
        100.0,
    )

    session_confidence_passed = (
        adjusted_confidence
        >= MINIMUM_REQUIRED_CONFIDENCE
    )

    return {
        "project": "Blue-Trading-AI",
        "version": 22,
        "module": "Market Session Confidence Adjustment",
        "symbol": session_analysis["symbol"],
        "timezone": session_analysis["timezone"],
        "base_confidence": round(
            normalized_confidence,
            2,
        ),
        "confidence_adjustment": round(
            confidence_adjustment,
            2,
        ),
        "adjusted_confidence": round(
            adjusted_confidence,
            2,
        ),
        "minimum_required_confidence": (
            MINIMUM_REQUIRED_CONFIDENCE
        ),
        "session_confidence_passed": (
            session_confidence_passed
        ),
        "confidence_signal": adjustment_data.get(
            "confidence_signal",
            "NEUTRAL",
        ),
        "combined_session_score": _clamp(
            adjustment_data.get(
                "combined_session_score",
                0.0,
            )
        ),
        "market_open": bool(
            session_analysis.get(
                "market_open",
                False,
            )
        ),
        "best_active_session": session_analysis.get(
            "best_active_session"
        ),
        "active_sessions": session_analysis.get(
            "active_sessions",
            [],
        ),
        "market_activity_level": session_analysis.get(
            "market_activity_level",
            "VERY_LOW",
        ),
        "decision": (
            "CONTINUE_ANALYSIS"
            if session_confidence_passed
            else "WAIT"
        ),
        "signal": (
            "SESSION_APPROVED"
            if session_confidence_passed
            else "NO_TRADE"
        ),
        "analysis_only": True,
        "broker_connection_enabled": False,
        "trade_execution_enabled": False,
    }


__all__ = [
    "DEFAULT_SESSION_PREFERENCES",
    "MARKET_TIMEZONE",
    "MINIMUM_REQUIRED_CONFIDENCE",
    "MarketSessionIntelligence",
    "MarketSessionState",
    "SESSION_WINDOWS",
    "SYMBOL_SESSION_PREFERENCES",
    "analyze_market_session",
    "apply_market_session_confidence",
    "calculate_minutes_until_session_end",
    "get_current_market_sessions",
    "get_market_session_configuration",
    "is_time_inside_session",
    "market_session_intelligence",
    "normalize_market_symbol",
    "parse_session_time",
    "time_to_minutes",
]