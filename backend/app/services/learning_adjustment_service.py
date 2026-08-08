from __future__ import annotations

import math
from typing import Any, Final

from sqlalchemy.orm import Session

from app.services.performance_analytics_service import (
    get_performance_analytics,
)


MINIMUM_COMPLETED_TRADES: Final = 20
MINIMUM_BASE_CONFIDENCE: Final = 80.0
MINIMUM_CONFIRMATIONS: Final = 3
MAXIMUM_CONFIRMATIONS: Final = 100

MAXIMUM_CONFIDENCE_INCREASE: Final = 5.0
MAXIMUM_CONFIDENCE_DECREASE: Final = -10.0

MINIMUM_GROUP_COMPLETED_TRADES: Final = 5
MAXIMUM_GROUPS_PER_CATEGORY: Final = 500
MAXIMUM_GROUP_NAME_LENGTH: Final = 64


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
    """Safely convert a value into a non-negative bounded integer."""

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
        MAXIMUM_CONFIRMATIONS,
    )


def safe_bool(
    value: Any,
) -> bool:
    """Accept only explicit truthy representations."""

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value == 1

    if isinstance(value, str):
        return value.strip().lower() in {
            "true",
            "1",
            "yes",
            "enabled",
            "ready",
        }

    return False


def clamp(
    value: Any,
    minimum: float,
    maximum: float,
) -> float:
    """Restrict a finite number between minimum and maximum values."""

    number = safe_float(
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


def find_performance_group(
    groups: list[dict[str, Any]],
    group_name: str | None,
) -> dict[str, Any] | None:
    """
    Finds one analytics group by its name.
    """

    if not group_name:
        return None

    normalized_name = str(
        group_name
    ).strip().upper()[
        :MAXIMUM_GROUP_NAME_LENGTH
    ]

    if not normalized_name:
        return None

    if not isinstance(
        groups,
        list,
    ):
        return None

    for group in groups[
        :MAXIMUM_GROUPS_PER_CATEGORY
    ]:
        if not isinstance(
            group,
            dict,
        ):
            continue

        current_name = str(
            group.get(
                "name",
                "",
            )
        ).strip().upper()[
            :MAXIMUM_GROUP_NAME_LENGTH
        ]

        if current_name == normalized_name:
            return group

    return None


def calculate_group_adjustment(
    group: dict[str, Any] | None,
    group_type: str,
) -> tuple[float, list[str]]:
    """
    Calculates a small confidence adjustment for one
    historical-performance group.

    A group must have at least five completed trades.
    """

    if not isinstance(
        group,
        dict,
    ) or not group:
        return 0.0, [
            f"No historical {group_type} data available."
        ]

    completed_trades = safe_int(
        group.get(
            "completed_for_win_rate",
            0,
        )
    )

    win_rate = safe_float(
        group.get(
            "win_rate",
            0.0,
        )
    )

    if completed_trades < MINIMUM_GROUP_COMPLETED_TRADES:
        return 0.0, [
            (
                f"{group_type.title()} learning skipped: "
                f"only {completed_trades} completed trades."
            )
        ]

    if win_rate >= 70.0:
        return 1.5, [
            (
                f"Strong {group_type} performance: "
                f"{win_rate:.2f}% win rate."
            )
        ]

    if win_rate >= 60.0:
        return 1.0, [
            (
                f"Positive {group_type} performance: "
                f"{win_rate:.2f}% win rate."
            )
        ]

    if win_rate >= 50.0:
        return 0.0, [
            (
                f"Neutral {group_type} performance: "
                f"{win_rate:.2f}% win rate."
            )
        ]

    if win_rate >= 40.0:
        return -1.5, [
            (
                f"Weak {group_type} performance: "
                f"{win_rate:.2f}% win rate."
            )
        ]

    return -3.0, [
        (
            f"Poor {group_type} performance: "
            f"{win_rate:.2f}% win rate."
        )
    ]


def calculate_overall_adjustment(
    overall: dict[str, Any],
) -> tuple[float, list[str]]:
    """
    Calculates a small adjustment from overall performance.
    """

    if not isinstance(
        overall,
        dict,
    ):
        overall = {}

    completed_trades = safe_int(
        overall.get(
            "completed_for_win_rate",
            0,
        )
    )

    win_rate = safe_float(
        overall.get(
            "win_rate",
            0.0,
        )
    )

    if completed_trades < MINIMUM_COMPLETED_TRADES:
        return 0.0, [
            (
                "Overall learning skipped because fewer "
                "than 20 completed trades are available."
            )
        ]

    if win_rate >= 65.0:
        return 1.0, [
            (
                "Overall historical performance is strong: "
                f"{win_rate:.2f}% win rate."
            )
        ]

    if win_rate >= 55.0:
        return 0.5, [
            (
                "Overall historical performance is positive: "
                f"{win_rate:.2f}% win rate."
            )
        ]

    if win_rate >= 45.0:
        return 0.0, [
            (
                "Overall historical performance is neutral: "
                f"{win_rate:.2f}% win rate."
            )
        ]

    if win_rate >= 35.0:
        return -2.0, [
            (
                "Overall historical performance is weak: "
                f"{win_rate:.2f}% win rate."
            )
        ]

    return -4.0, [
        (
            "Overall historical performance is poor: "
            f"{win_rate:.2f}% win rate."
        )
    ]


def get_learning_adjustment(
    db: Session,
    symbol: str,
    direction: str,
    trade_quality_grade: str,
    base_confidence: float,
    confirmations_count: int,
    signal_action: str,
) -> dict[str, Any]:
    """
    Applies a controlled historical-performance adjustment.

    Important safety rules:
    - Learning stays disabled below 20 completed trades.
    - WAIT and NO_TRADE signals cannot become approved.
    - Base confidence below 80 cannot be rescued.
    - Fewer than three confirmations cannot be rescued.
    - Maximum increase is +5%.
    - Maximum decrease is -10%.
    """

    normalized_action = str(
        signal_action or "WAIT"
    ).strip().upper()

    normalized_direction = str(
        direction or ""
    ).strip().upper()

    normalized_symbol = str(
        symbol or ""
    ).strip().upper()[
        :MAXIMUM_GROUP_NAME_LENGTH
    ]

    normalized_trade_quality_grade = str(
        trade_quality_grade or ""
    ).strip().upper()[
        :MAXIMUM_GROUP_NAME_LENGTH
    ]

    original_confidence = clamp(
        base_confidence,
        0.0,
        100.0,
    )

    confirmations = safe_int(
        confirmations_count
    )

    analytics = get_performance_analytics(
        db=db
    )

    if not isinstance(
        analytics,
        dict,
    ):
        raise ValueError(
            "Performance analytics returned an invalid response."
        )

    overall = analytics.get(
        "overall",
        {},
    )

    if not isinstance(
        overall,
        dict,
    ):
        overall = {}

    learning_status = analytics.get(
        "learning_status",
        {},
    )

    if not isinstance(
        learning_status,
        dict,
    ):
        learning_status = {}

    completed_trades = safe_int(
        learning_status.get(
            "completed_trades_available",
            0,
        )
    )

    learning_ready = safe_bool(
        learning_status.get(
            "sufficient_learning_data",
            False,
        )
    )

    safety_reasons: list[str] = []

    if normalized_direction not in {
        "BUY",
        "SELL",
    }:
        safety_reasons.append(
            "Learning direction must be BUY or SELL."
        )

    if normalized_action not in {
        "BUY",
        "SELL",
    }:
        safety_reasons.append(
            "Learning cannot convert a WAIT or NO_TRADE signal."
        )

    if original_confidence < MINIMUM_BASE_CONFIDENCE:
        safety_reasons.append(
            "Base confidence is below the required 80%."
        )

    if confirmations < MINIMUM_CONFIRMATIONS:
        safety_reasons.append(
            "Fewer than three confirmations are available."
        )

    if not learning_ready:
        safety_reasons.append(
            (
                "Learning adjustment is disabled until "
                f"{MINIMUM_COMPLETED_TRADES} completed trades "
                "are available."
            )
        )

    if safety_reasons:
        return {
            "status": "success",
            "safety_version": 11,
            "learning_applied": False,
            "learning_ready": learning_ready,
            "completed_trades_available": completed_trades,
            "minimum_completed_trades_required": (
                MINIMUM_COMPLETED_TRADES
            ),
            "original_confidence": round(
                original_confidence,
                2,
            ),
            "confidence_adjustment": 0.0,
            "adjusted_confidence": round(
                original_confidence,
                2,
            ),
            "trade_remains_allowed": (
                normalized_action in {"BUY", "SELL"}
                and original_confidence
                >= MINIMUM_BASE_CONFIDENCE
                and confirmations
                >= MINIMUM_CONFIRMATIONS
            ),
            "reasons": list(
                dict.fromkeys(
                    safety_reasons
                )
            ),
        }

    symbol_group = find_performance_group(
        groups=(
            analytics.get(
                "performance_by_symbol",
                [],
            )
            if isinstance(
                analytics.get(
                    "performance_by_symbol",
                    [],
                ),
                list,
            )
            else []
        ),
        group_name=normalized_symbol,
    )

    direction_group = find_performance_group(
        groups=(
            analytics.get(
                "performance_by_direction",
                [],
            )
            if isinstance(
                analytics.get(
                    "performance_by_direction",
                    [],
                ),
                list,
            )
            else []
        ),
        group_name=normalized_direction,
    )

    quality_group = find_performance_group(
        groups=(
            analytics.get(
                "performance_by_trade_quality",
                [],
            )
            if isinstance(
                analytics.get(
                    "performance_by_trade_quality",
                    [],
                ),
                list,
            )
            else []
        ),
        group_name=normalized_trade_quality_grade,
    )

    total_adjustment = 0.0
    learning_reasons: list[str] = []

    overall_adjustment, reasons = (
        calculate_overall_adjustment(
            overall=overall
        )
    )
    total_adjustment += overall_adjustment
    learning_reasons.extend(reasons)

    symbol_adjustment, reasons = (
        calculate_group_adjustment(
            group=symbol_group,
            group_type="symbol",
        )
    )
    total_adjustment += symbol_adjustment
    learning_reasons.extend(reasons)

    direction_adjustment, reasons = (
        calculate_group_adjustment(
            group=direction_group,
            group_type="direction",
        )
    )
    total_adjustment += direction_adjustment
    learning_reasons.extend(reasons)

    quality_adjustment, reasons = (
        calculate_group_adjustment(
            group=quality_group,
            group_type="trade quality",
        )
    )
    total_adjustment += quality_adjustment
    learning_reasons.extend(reasons)

    controlled_adjustment = clamp(
        total_adjustment,
        MAXIMUM_CONFIDENCE_DECREASE,
        MAXIMUM_CONFIDENCE_INCREASE,
    )

    adjusted_confidence = clamp(
        original_confidence
        + controlled_adjustment,
        0.0,
        100.0,
    )

    trade_remains_allowed = (
        normalized_action in {"BUY", "SELL"}
        and adjusted_confidence
        >= MINIMUM_BASE_CONFIDENCE
        and confirmations
        >= MINIMUM_CONFIRMATIONS
    )

    if not trade_remains_allowed:
        learning_reasons.append(
            (
                "The adjusted confidence does not satisfy "
                "the minimum trade-approval rules."
            )
        )

    return {
        "status": "success",
        "safety_version": 11,
        "learning_applied": True,
        "learning_ready": True,
        "completed_trades_available": completed_trades,
        "minimum_completed_trades_required": (
            MINIMUM_COMPLETED_TRADES
        ),
        "original_confidence": round(
            original_confidence,
            2,
        ),
        "confidence_adjustment": round(
            controlled_adjustment,
            2,
        ),
        "adjusted_confidence": round(
            adjusted_confidence,
            2,
        ),
        "maximum_confidence_increase": (
            MAXIMUM_CONFIDENCE_INCREASE
        ),
        "maximum_confidence_decrease": (
            MAXIMUM_CONFIDENCE_DECREASE
        ),
        "trade_remains_allowed": (
            trade_remains_allowed
        ),
        "adjustment_breakdown": {
            "overall": round(
                overall_adjustment,
                2,
            ),
            "symbol": round(
                symbol_adjustment,
                2,
            ),
            "direction": round(
                direction_adjustment,
                2,
            ),
            "trade_quality": round(
                quality_adjustment,
                2,
            ),
        },
        "reasons": learning_reasons,
    }

__all__ = [
    "MAXIMUM_CONFIDENCE_DECREASE",
    "MAXIMUM_CONFIDENCE_INCREASE",
    "MAXIMUM_CONFIRMATIONS",
    "MINIMUM_BASE_CONFIDENCE",
    "MINIMUM_COMPLETED_TRADES",
    "MINIMUM_CONFIRMATIONS",
    "MINIMUM_GROUP_COMPLETED_TRADES",
    "calculate_group_adjustment",
    "calculate_overall_adjustment",
    "clamp",
    "find_performance_group",
    "get_learning_adjustment",
    "safe_bool",
    "safe_float",
    "safe_int",
]