from __future__ import annotations

from datetime import datetime
import math
from typing import Any, Final
from zoneinfo import ZoneInfo


MALAYSIA_TIMEZONE: Final = ZoneInfo(
    "Asia/Kuala_Lumpur"
)

ASIAN_SESSION: Final = "ASIAN"
EUROPEAN_SESSION: Final = "EUROPEAN"
US_SESSION: Final = "US"
SESSION_OVERLAP: Final = "SESSION_OVERLAP"
SESSION_CLOSED: Final = "SESSION_CLOSED"

TRENDING_MARKET: Final = "TRENDING"
RANGING_MARKET: Final = "RANGING"
VOLATILE_MARKET: Final = "VOLATILE"

WEAK_TREND: Final = "WEAK"
MODERATE_TREND: Final = "MODERATE"
STRONG_TREND: Final = "STRONG"

LOW_RISK: Final = "LOW"
MEDIUM_RISK: Final = "MEDIUM"
HIGH_RISK: Final = "HIGH"

EXCELLENT_QUALITY: Final = "EXCELLENT"
GOOD_QUALITY: Final = "GOOD"
MODERATE_QUALITY: Final = "MODERATE"
WEAK_QUALITY: Final = "WEAK"

MAXIMUM_CONTEXT_COUNT: Final = 100


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


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    """Safely convert a value into a bounded non-negative integer."""

    if isinstance(value, bool):
        return default

    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return default

    return min(
        max(
            number,
            0,
        ),
        MAXIMUM_CONTEXT_COUNT,
    )


def clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    """
    Restricts a value between minimum and maximum.
    """

    return max(
        minimum,
        min(value, maximum),
    )


def is_hour_in_range(
    current_hour: int,
    start_hour: int,
    end_hour: int,
) -> bool:
    """
    Check whether an hour is inside a session range.

    Supports ranges that cross midnight.
    """

    for hour in (
        current_hour,
        start_hour,
        end_hour,
    ):
        if not 0 <= hour <= 23:
            raise ValueError(
                "Session hours must be between 0 and 23."
            )

    if start_hour < end_hour:
        return start_hour <= current_hour < end_hour

    return (
        current_hour >= start_hour
        or current_hour < end_hour
    )


def get_active_sessions(
    current_hour: int,
) -> list[str]:
    """
    Returns all active market sessions using
    Malaysia Time.

    Blue-Trading-AI session windows:

    ASIAN:
    07:00 until 16:00 MYT

    EUROPEAN:
    15:00 until 00:00 MYT

    US:
    20:00 until 05:00 MYT
    """

    active_sessions: list[str] = []

    if is_hour_in_range(
        current_hour=current_hour,
        start_hour=7,
        end_hour=16,
    ):
        active_sessions.append(
            ASIAN_SESSION
        )

    if is_hour_in_range(
        current_hour=current_hour,
        start_hour=15,
        end_hour=0,
    ):
        active_sessions.append(
            EUROPEAN_SESSION
        )

    if is_hour_in_range(
        current_hour=current_hour,
        start_hour=20,
        end_hour=5,
    ):
        active_sessions.append(
            US_SESSION
        )

    return active_sessions


def get_current_session(
    current_datetime: datetime | None = None,
) -> dict[str, Any]:
    """
    Detects the current Blue-Trading-AI market
    session using Malaysia Time.
    """

    if current_datetime is None:
        malaysia_time = datetime.now(
            MALAYSIA_TIMEZONE
        )

    elif current_datetime.tzinfo is None:
        malaysia_time = current_datetime.replace(
            tzinfo=MALAYSIA_TIMEZONE
        )

    else:
        malaysia_time = current_datetime.astimezone(
            MALAYSIA_TIMEZONE
        )

    active_sessions = get_active_sessions(
        current_hour=malaysia_time.hour
    )

    if len(active_sessions) > 1:
        session_name = SESSION_OVERLAP

    elif len(active_sessions) == 1:
        session_name = active_sessions[0]

    else:
        session_name = SESSION_CLOSED

    return {
        "timezone": "Asia/Kuala_Lumpur",
        "malaysia_time": (
            malaysia_time.isoformat()
        ),
        "current_hour": malaysia_time.hour,
        "current_session": session_name,
        "active_sessions": active_sessions,
        "is_session_overlap": (
            len(active_sessions) > 1
        ),
        "session_windows_myt": {
            "ASIAN": "07:00-16:00",
            "EUROPEAN": "15:00-00:00",
            "US": "20:00-05:00",
        },
    }


def determine_trend_strength(
    trend_score: Any,
) -> str:
    """
    Classifies trend strength using a score
    between 0 and 100.
    """

    score = clamp(
        safe_float(trend_score),
        0.0,
        100.0,
    )

    if score >= 75.0:
        return STRONG_TREND

    if score >= 50.0:
        return MODERATE_TREND

    return WEAK_TREND


def determine_market_condition(
    trend_score: Any,
    volatility_score: Any,
) -> str:
    """
    Classifies the current market condition.
    """

    trend = clamp(
        safe_float(trend_score),
        0.0,
        100.0,
    )

    volatility = clamp(
        safe_float(volatility_score),
        0.0,
        100.0,
    )

    if volatility >= 75.0:
        return VOLATILE_MARKET

    if trend >= 60.0:
        return TRENDING_MARKET

    return RANGING_MARKET


def determine_risk_environment(
    volatility_score: Any,
    conflicting_factors_count: Any,
    session_overlap: bool,
) -> str:
    """
    Determines the market risk environment.
    """

    volatility = clamp(
        safe_float(volatility_score),
        0.0,
        100.0,
    )

    conflicts = safe_int(
        conflicting_factors_count
    )

    risk_score = 0

    if volatility >= 75.0:
        risk_score += 2

    elif volatility >= 50.0:
        risk_score += 1

    if conflicts >= 4:
        risk_score += 2

    elif conflicts >= 2:
        risk_score += 1

    if session_overlap:
        risk_score += 1

    if risk_score >= 4:
        return HIGH_RISK

    if risk_score >= 2:
        return MEDIUM_RISK

    return LOW_RISK


def determine_signal_quality(
    confidence: Any,
    confirmations_count: Any,
    risk_environment: str,
    market_condition: str,
) -> str:
    """
    Classifies overall signal quality.
    """

    confidence_value = clamp(
        safe_float(confidence),
        0.0,
        100.0,
    )

    confirmations = safe_int(
        confirmations_count
    )

    if (
        confidence_value >= 92.0
        and confirmations >= 7
        and risk_environment == LOW_RISK
        and market_condition == TRENDING_MARKET
    ):
        return EXCELLENT_QUALITY

    if (
        confidence_value >= 85.0
        and confirmations >= 5
        and risk_environment
        in {
            LOW_RISK,
            MEDIUM_RISK,
        }
    ):
        return GOOD_QUALITY

    if (
        confidence_value >= 80.0
        and confirmations >= 3
        and risk_environment != HIGH_RISK
    ):
        return MODERATE_QUALITY

    return WEAK_QUALITY


def analyze_market_context(
    trend_score: Any,
    volatility_score: Any,
    confidence: Any,
    confirmations_count: Any,
    conflicting_factors_count: Any = 0,
    current_datetime: datetime | None = None,
) -> dict[str, Any]:
    """
    Produces the full Blue-Trading-AI
    market-context analysis.
    """

    session_data = get_current_session(
        current_datetime=current_datetime
    )

    trend_strength = determine_trend_strength(
        trend_score=trend_score
    )

    market_condition = determine_market_condition(
        trend_score=trend_score,
        volatility_score=volatility_score,
    )

    risk_environment = determine_risk_environment(
        volatility_score=volatility_score,
        conflicting_factors_count=(
            conflicting_factors_count
        ),
        session_overlap=session_data[
            "is_session_overlap"
        ],
    )

    signal_quality = determine_signal_quality(
        confidence=confidence,
        confirmations_count=(
            confirmations_count
        ),
        risk_environment=risk_environment,
        market_condition=market_condition,
    )

    context_supports_trade = (
        signal_quality
        in {
            EXCELLENT_QUALITY,
            GOOD_QUALITY,
            MODERATE_QUALITY,
        }
        and risk_environment != HIGH_RISK
    )

    reasons: list[str] = []

    if market_condition == TRENDING_MARKET:
        reasons.append(
            "The market is showing a trending condition."
        )

    elif market_condition == RANGING_MARKET:
        reasons.append(
            "The market is currently ranging."
        )

    else:
        reasons.append(
            "The market is experiencing high volatility."
        )

    reasons.append(
        f"Trend strength is {trend_strength}."
    )

    reasons.append(
        f"Risk environment is {risk_environment}."
    )

    reasons.append(
        f"Signal quality is {signal_quality}."
    )

    if session_data["is_session_overlap"]:
        reasons.append(
            "More than one market session is active."
        )

    return {
        "status": "success",
        "project": "Blue-Trading-AI",
        "safety_version": 13,
        "market_condition": market_condition,
        "trend_strength": trend_strength,
        "risk_environment": risk_environment,
        "signal_quality": signal_quality,
        "context_supports_trade": (
            context_supports_trade
        ),
        "session": session_data,
        "input_summary": {
            "trend_score": clamp(
                safe_float(trend_score),
                0.0,
                100.0,
            ),
            "volatility_score": clamp(
                safe_float(volatility_score),
                0.0,
                100.0,
            ),
            "confidence": clamp(
                safe_float(confidence),
                0.0,
                100.0,
            ),
            "confirmations_count": safe_int(
                confirmations_count
            ),
            "conflicting_factors_count": safe_int(
                conflicting_factors_count
            ),
        },
        "reasons": reasons,
        "safety_rules": {
            "high_risk_context_blocks_trade": True,
            "weak_quality_blocks_trade": True,
            "session_names": [
                "ASIAN",
                "EUROPEAN",
                "US",
            ],
            "timezone": "Asia/Kuala_Lumpur",
            "broker_execution_enabled": False,
        },
    }

__all__ = [
    "ASIAN_SESSION",
    "EUROPEAN_SESSION",
    "EXCELLENT_QUALITY",
    "GOOD_QUALITY",
    "HIGH_RISK",
    "LOW_RISK",
    "MALAYSIA_TIMEZONE",
    "MAXIMUM_CONTEXT_COUNT",
    "MEDIUM_RISK",
    "MODERATE_QUALITY",
    "MODERATE_TREND",
    "RANGING_MARKET",
    "SESSION_CLOSED",
    "SESSION_OVERLAP",
    "STRONG_TREND",
    "TRENDING_MARKET",
    "US_SESSION",
    "VOLATILE_MARKET",
    "WEAK_QUALITY",
    "WEAK_TREND",
    "analyze_market_context",
    "clamp",
    "determine_market_condition",
    "determine_risk_environment",
    "determine_signal_quality",
    "determine_trend_strength",
    "get_active_sessions",
    "get_current_session",
    "is_hour_in_range",
    "safe_float",
    "safe_int",
]