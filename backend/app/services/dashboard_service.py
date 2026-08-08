from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.performance_analytics_service import (
    get_performance_analytics,
)


def _as_dict(
    value: Any,
) -> dict[str, Any]:
    """
    Return a dictionary value safely.

    Unexpected service payload types are converted
    to an empty dictionary so dashboard assembly
    remains predictable.
    """

    if isinstance(
        value,
        dict,
    ):
        return value

    return {}


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    """Return a safe non-negative integer."""

    if isinstance(
        value,
        bool,
    ):
        return default

    try:
        result = int(value)
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return default

    return max(
        result,
        0,
    )


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """Return a safe numeric dashboard value."""

    try:
        result = float(value)
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return default

    if result != result:
        return default

    if result in {
        float("inf"),
        float("-inf"),
    }:
        return default

    return result


def get_dashboard_summary(
    db: Session,
) -> dict[str, Any]:
    """
    Return a simplified dashboard response.

    This function uses the full performance analytics
    service but exposes only the metrics required by
    the frontend dashboard.
    """

    analytics = get_performance_analytics(
        db=db,
    )

    if not isinstance(
        analytics,
        dict,
    ):
        raise ValueError(
            "Performance analytics returned an invalid response."
        )

    overall = _as_dict(
        analytics.get(
            "overall",
        )
    )

    current_period = _as_dict(
        analytics.get(
            "current_period_summary",
        )
    )

    today = _as_dict(
        current_period.get(
            "today",
        )
    )

    this_week = _as_dict(
        current_period.get(
            "this_week",
        )
    )

    this_month = _as_dict(
        current_period.get(
            "this_month",
        )
    )

    best_performing = _as_dict(
        analytics.get(
            "best_performing",
        )
    )

    learning_status = _as_dict(
        analytics.get(
            "learning_status",
        )
    )

    return {
        "status": "success",
        "safety_version": 10,
        "dashboard_ready": (
            analytics.get(
                "analytics_ready",
            )
            is True
        ),
        "summary": {
            "total_trades": _safe_int(
                overall.get(
                    "total_trades",
                )
            ),
            "active_trades": _safe_int(
                overall.get(
                    "active_trades",
                )
            ),
            "closed_trades": _safe_int(
                overall.get(
                    "closed_trades",
                )
            ),
            "winning_trades": _safe_int(
                overall.get(
                    "winning_trades",
                )
            ),
            "losing_trades": _safe_int(
                overall.get(
                    "losing_trades",
                )
            ),
            "pending_trades": _safe_int(
                overall.get(
                    "pending_trades",
                )
            ),
            "overall_win_rate": _safe_float(
                overall.get(
                    "win_rate",
                )
            ),
            "overall_loss_rate": _safe_float(
                overall.get(
                    "loss_rate",
                )
            ),
            "average_confidence": _safe_float(
                overall.get(
                    "average_confidence",
                )
            ),
            "average_trade_quality": _safe_float(
                overall.get(
                    "average_trade_quality",
                )
            ),
            "average_risk_reward": _safe_float(
                overall.get(
                    "average_risk_reward",
                )
            ),
            "total_profit_loss_points": _safe_float(
                overall.get(
                    "total_profit_loss_points",
                )
            ),
        },
        "current_performance": {
            "today": {
                "period": today.get(
                    "period",
                ),
                "total_trades": _safe_int(
                    today.get(
                        "total_trades",
                    )
                ),
                "win_rate": _safe_float(
                    today.get(
                        "win_rate",
                    )
                ),
                "loss_rate": _safe_float(
                    today.get(
                        "loss_rate",
                    )
                ),
                "profit_loss_points": _safe_float(
                    today.get(
                        "total_profit_loss_points",
                    )
                ),
            },
            "this_week": {
                "period": this_week.get(
                    "period",
                ),
                "total_trades": _safe_int(
                    this_week.get(
                        "total_trades",
                    )
                ),
                "win_rate": _safe_float(
                    this_week.get(
                        "win_rate",
                    )
                ),
                "loss_rate": _safe_float(
                    this_week.get(
                        "loss_rate",
                    )
                ),
                "profit_loss_points": _safe_float(
                    this_week.get(
                        "total_profit_loss_points",
                    )
                ),
            },
            "this_month": {
                "period": this_month.get(
                    "period",
                ),
                "total_trades": _safe_int(
                    this_month.get(
                        "total_trades",
                    )
                ),
                "win_rate": _safe_float(
                    this_month.get(
                        "win_rate",
                    )
                ),
                "loss_rate": _safe_float(
                    this_month.get(
                        "loss_rate",
                    )
                ),
                "profit_loss_points": _safe_float(
                    this_month.get(
                        "total_profit_loss_points",
                    )
                ),
            },
        },
        "best_performing": {
            "symbol": best_performing.get(
                "symbol",
            ),
            "direction": best_performing.get(
                "direction",
            ),
            "trade_quality_grade": (
                best_performing.get(
                    "trade_quality_grade",
                )
            ),
        },
        "learning_status": {
            "enabled": (
                learning_status.get(
                    "enabled",
                    True,
                )
                is True
            ),
            "completed_trades_available": _safe_int(
                learning_status.get(
                    "completed_trades_available",
                )
            ),
            "minimum_completed_trades_required": _safe_int(
                learning_status.get(
                    "minimum_completed_trades_required",
                    20,
                ),
                default=20,
            ),
            "sufficient_learning_data": (
                learning_status.get(
                    "sufficient_learning_data",
                    False,
                )
                is True
            ),
            "confidence_adjustment_active": (
                learning_status.get(
                    "confidence_adjustment_active",
                    False,
                )
                is True
            ),
        },
    }


__all__ = [
    "get_dashboard_summary",
]