from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import math
from typing import Any, Final

from sqlalchemy.orm import Session

from app.models.trade_history import TradeHistory


WIN_RESULTS: Final[frozenset[str]] = frozenset(
    {
        "TP1_HIT",
        "TP2_HIT",
    }
)

LOSS_RESULTS: Final[frozenset[str]] = frozenset(
    {
        "STOP_LOSS",
    }
)

SUPPORTED_PERIOD_TYPES: Final[frozenset[str]] = frozenset(
    {
        "daily",
        "weekly",
        "monthly",
    }
)

SUPPORTED_GROUP_ATTRIBUTES: Final[frozenset[str]] = frozenset(
    {
        "symbol",
        "direction",
        "trade_quality_grade",
    }
)

MINIMUM_LEARNING_TRADES: Final = 20


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """Safely convert a value to a finite float."""

    try:
        number = float(
            0.0
            if value is None
            else value
        )
    except (TypeError, ValueError, OverflowError):
        return default

    if not math.isfinite(number):
        return default

    return number


def normalize_datetime(
    value: datetime | None,
) -> datetime | None:
    """
    Ensures database datetime values use UTC timezone.
    """

    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


def calculate_rate(
    successful: int,
    total: int,
) -> float:
    """
    Calculates a percentage safely.
    """

    if total <= 0:
        return 0.0

    return round(
        successful / total * 100,
        2,
    )


def determine_trade_outcome(
    trade: TradeHistory,
) -> str:
    """
    Converts a trade result into:
    WIN, LOSS, CANCELLED, or PENDING.
    """

    result = str(
        trade.result or "PENDING"
    ).strip().upper()

    status = str(
        trade.status or "ACTIVE"
    ).strip().upper()

    if result in WIN_RESULTS:
        return "WIN"

    if result in LOSS_RESULTS:
        return "LOSS"

    if (
        result == "CANCELLED"
        or status == "CANCELLED"
    ):
        return "CANCELLED"

    return "PENDING"


def create_group_bucket() -> dict[str, Any]:
    """
    Creates an empty performance bucket.
    """

    return {
        "total_trades": 0,
        "active_trades": 0,
        "closed_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "cancelled_trades": 0,
        "pending_trades": 0,
        "tp1_trades": 0,
        "tp2_trades": 0,
        "stop_loss_trades": 0,
        "total_confidence": 0.0,
        "total_trade_quality": 0.0,
        "total_profit_loss_points": 0.0,
        "total_risk_reward": 0.0,
        "risk_reward_count": 0,
    }


def add_trade_to_bucket(
    bucket: dict[str, Any],
    trade: TradeHistory,
) -> None:
    """
    Adds one trade into a performance bucket.
    """

    bucket["total_trades"] += 1

    status = str(
        trade.status or "ACTIVE"
    ).strip().upper()

    outcome = determine_trade_outcome(
        trade
    )

    if status == "ACTIVE":
        bucket["active_trades"] += 1

    if status == "CLOSED":
        bucket["closed_trades"] += 1

    if outcome == "WIN":
        bucket["winning_trades"] += 1

    elif outcome == "LOSS":
        bucket["losing_trades"] += 1

    elif outcome == "CANCELLED":
        bucket["cancelled_trades"] += 1

    else:
        bucket["pending_trades"] += 1

    if bool(trade.tp1_hit):
        bucket["tp1_trades"] += 1

    if bool(trade.tp2_hit):
        bucket["tp2_trades"] += 1

    if bool(trade.stop_loss_hit):
        bucket["stop_loss_trades"] += 1

    bucket["total_confidence"] += safe_float(
        trade.confidence
    )

    bucket["total_trade_quality"] += safe_float(
        trade.trade_quality_score
    )

    bucket["total_profit_loss_points"] += safe_float(
        trade.profit_loss_points
    )

    if trade.risk_reward_achieved is not None:
        bucket["total_risk_reward"] += safe_float(
            trade.risk_reward_achieved
        )
        bucket["risk_reward_count"] += 1


def finalize_bucket(
    name: str,
    bucket: dict[str, Any],
) -> dict[str, Any]:
    """
    Converts a bucket into API-ready statistics.
    """

    total_trades = int(
        bucket["total_trades"]
    )

    completed_trades = (
        int(bucket["winning_trades"])
        + int(bucket["losing_trades"])
    )

    average_confidence = (
        bucket["total_confidence"]
        / total_trades
        if total_trades > 0
        else 0.0
    )

    average_trade_quality = (
        bucket["total_trade_quality"]
        / total_trades
        if total_trades > 0
        else 0.0
    )

    average_risk_reward = (
        bucket["total_risk_reward"]
        / bucket["risk_reward_count"]
        if bucket["risk_reward_count"] > 0
        else 0.0
    )

    return {
        "period": name,
        "total_trades": total_trades,
        "active_trades": int(
            bucket["active_trades"]
        ),
        "closed_trades": int(
            bucket["closed_trades"]
        ),
        "winning_trades": int(
            bucket["winning_trades"]
        ),
        "losing_trades": int(
            bucket["losing_trades"]
        ),
        "cancelled_trades": int(
            bucket["cancelled_trades"]
        ),
        "pending_trades": int(
            bucket["pending_trades"]
        ),
        "tp1_trades": int(
            bucket["tp1_trades"]
        ),
        "tp2_trades": int(
            bucket["tp2_trades"]
        ),
        "stop_loss_trades": int(
            bucket["stop_loss_trades"]
        ),
        "completed_for_win_rate": (
            completed_trades
        ),
        "win_rate": calculate_rate(
            successful=int(
                bucket["winning_trades"]
            ),
            total=completed_trades,
        ),
        "loss_rate": calculate_rate(
            successful=int(
                bucket["losing_trades"]
            ),
            total=completed_trades,
        ),
        "average_confidence": round(
            average_confidence,
            2,
        ),
        "average_trade_quality": round(
            average_trade_quality,
            2,
        ),
        "average_risk_reward": round(
            average_risk_reward,
            4,
        ),
        "total_profit_loss_points": round(
            bucket[
                "total_profit_loss_points"
            ],
            8,
        ),
    }


def get_trade_result_datetime(
    trade: TradeHistory,
) -> datetime | None:
    """
    Uses closed_at for completed trades.

    Falls back to updated_at or created_at when needed.
    """

    return normalize_datetime(
        trade.closed_at
        or trade.updated_at
        or trade.created_at
    )


def get_daily_period(
    trade: TradeHistory,
) -> str | None:
    """
    Returns a daily period such as:
    2026-07-30
    """

    trade_time = get_trade_result_datetime(
        trade
    )

    if trade_time is None:
        return None

    return trade_time.strftime(
        "%Y-%m-%d"
    )


def get_weekly_period(
    trade: TradeHistory,
) -> str | None:
    """
    Returns an ISO week such as:
    2026-W31
    """

    trade_time = get_trade_result_datetime(
        trade
    )

    if trade_time is None:
        return None

    iso_year, iso_week, _ = (
        trade_time.isocalendar()
    )

    return (
        f"{iso_year}-W"
        f"{iso_week:02d}"
    )


def get_monthly_period(
    trade: TradeHistory,
) -> str | None:
    """
    Returns a monthly period such as:
    2026-07
    """

    trade_time = get_trade_result_datetime(
        trade
    )

    if trade_time is None:
        return None

    return trade_time.strftime(
        "%Y-%m"
    )


def aggregate_by_period(
    trades: list[TradeHistory],
    period_type: str,
) -> list[dict[str, Any]]:
    """
    Groups trades by daily, weekly, or monthly period.
    """

    if period_type not in SUPPORTED_PERIOD_TYPES:
        raise ValueError(
            "Unsupported period type."
        )

    grouped_data: dict[
        str,
        dict[str, Any],
    ] = defaultdict(
        create_group_bucket
    )

    for trade in trades:

        if period_type == "daily":
            period = get_daily_period(
                trade
            )

        elif period_type == "weekly":
            period = get_weekly_period(
                trade
            )

        elif period_type == "monthly":
            period = get_monthly_period(
                trade
            )

        if period is None:
            continue

        add_trade_to_bucket(
            bucket=grouped_data[period],
            trade=trade,
        )

    results = [
        finalize_bucket(
            name=period,
            bucket=bucket,
        )
        for period, bucket
        in grouped_data.items()
    ]

    return sorted(
        results,
        key=lambda item: item["period"],
        reverse=True,
    )


def aggregate_by_attribute(
    trades: list[TradeHistory],
    group_attribute: str,
    default_name: str = "UNKNOWN",
) -> list[dict[str, Any]]:
    """
    Groups trades by an approved TradeHistory attribute.

    Used for:
    - Symbol
    - Direction
    - Trade-quality grade
    """

    if group_attribute not in SUPPORTED_GROUP_ATTRIBUTES:
        raise ValueError(
            "Unsupported analytics grouping attribute."
        )

    grouped_data: dict[
        str,
        dict[str, Any],
    ] = defaultdict(
        create_group_bucket
    )

    for trade in trades:
        raw_name = getattr(
            trade,
            group_attribute,
            None,
        )

        name = str(
            raw_name or default_name
        ).strip().upper()

        add_trade_to_bucket(
            bucket=grouped_data[name],
            trade=trade,
        )

    results = []

    for name, bucket in grouped_data.items():
        item = finalize_bucket(
            name=name,
            bucket=bucket,
        )

        item["name"] = item.pop(
            "period"
        )

        results.append(item)

    return sorted(
        results,
        key=lambda item: (
            item["win_rate"],
            item["total_trades"],
        ),
        reverse=True,
    )


def get_overall_performance(
    trades: list[TradeHistory],
) -> dict[str, Any]:
    """
    Calculates overall trading performance.
    """

    bucket = create_group_bucket()

    for trade in trades:
        add_trade_to_bucket(
            bucket=bucket,
            trade=trade,
        )

    overall = finalize_bucket(
        name="OVERALL",
        bucket=bucket,
    )

    overall.pop(
        "period",
        None,
    )

    return overall


def get_best_period(
    periods: list[dict[str, Any]],
    minimum_completed_trades: int = 1,
) -> dict[str, Any] | None:
    """
    Returns the period with the highest win rate.
    """

    minimum_completed_trades = max(
        int(minimum_completed_trades),
        1,
    )

    eligible_periods = [
        period
        for period in periods
        if period[
            "completed_for_win_rate"
        ]
        >= minimum_completed_trades
    ]

    if not eligible_periods:
        return None

    return max(
        eligible_periods,
        key=lambda period: (
            period["win_rate"],
            period[
                "completed_for_win_rate"
            ],
            period[
                "average_risk_reward"
            ],
        ),
    )


def get_best_group(
    groups: list[dict[str, Any]],
    minimum_completed_trades: int = 1,
) -> dict[str, Any] | None:
    """
    Returns the best-performing category.
    """

    minimum_completed_trades = max(
        int(minimum_completed_trades),
        1,
    )

    eligible_groups = [
        group
        for group in groups
        if group[
            "completed_for_win_rate"
        ]
        >= minimum_completed_trades
    ]

    if not eligible_groups:
        return None

    return max(
        eligible_groups,
        key=lambda group: (
            group["win_rate"],
            group[
                "completed_for_win_rate"
            ],
            group[
                "average_risk_reward"
            ],
        ),
    )



def find_period_record(
    records: list[dict[str, Any]],
    period: str,
) -> dict[str, Any] | None:
    """
    Finds one period record from an analytics list.
    """

    for record in records:
        if record.get("period") == period:
            return record

    return None


def create_empty_period_summary(
    period: str,
) -> dict[str, Any]:
    """
    Creates a dashboard-safe empty period result.
    """

    return {
        "period": period,
        "total_trades": 0,
        "active_trades": 0,
        "closed_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "cancelled_trades": 0,
        "pending_trades": 0,
        "tp1_trades": 0,
        "tp2_trades": 0,
        "stop_loss_trades": 0,
        "completed_for_win_rate": 0,
        "win_rate": 0.0,
        "loss_rate": 0.0,
        "average_confidence": 0.0,
        "average_trade_quality": 0.0,
        "average_risk_reward": 0.0,
        "total_profit_loss_points": 0.0,
    }


def get_current_period_summary(
    daily_performance: list[dict[str, Any]],
    weekly_performance: list[dict[str, Any]],
    monthly_performance: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Returns today's, this week's, and this month's performance.

    UTC is used because trade-history timestamps are normalized to UTC.
    """

    now = datetime.now(timezone.utc)

    today_period = now.strftime("%Y-%m-%d")

    iso_year, iso_week, _ = now.isocalendar()
    current_week_period = f"{iso_year}-W{iso_week:02d}"

    current_month_period = now.strftime("%Y-%m")

    today_data = find_period_record(
        records=daily_performance,
        period=today_period,
    )

    week_data = find_period_record(
        records=weekly_performance,
        period=current_week_period,
    )

    month_data = find_period_record(
        records=monthly_performance,
        period=current_month_period,
    )

    return {
        "today": (
            today_data
            or create_empty_period_summary(
                period=today_period,
            )
        ),
        "this_week": (
            week_data
            or create_empty_period_summary(
                period=current_week_period,
            )
        ),
        "this_month": (
            month_data
            or create_empty_period_summary(
                period=current_month_period,
            )
        ),
    }

def get_performance_analytics(
    db: Session,
) -> dict[str, Any]:
    """
    Returns dashboard-ready analytics.

    Timeframe win rate is intentionally excluded.

    Includes:
    - Overall performance
    - Daily win rate
    - Weekly win rate
    - Monthly win rate
    - Performance by symbol
    - Performance by direction
    - Performance by trade-quality grade
    """

    trades = (
        db.query(TradeHistory)
        .order_by(
            TradeHistory.created_at.asc()
        )
        .all()
    )

    overall = get_overall_performance(
        trades=trades
    )

    daily_performance = (
        aggregate_by_period(
            trades=trades,
            period_type="daily",
        )
    )

    weekly_performance = (
        aggregate_by_period(
            trades=trades,
            period_type="weekly",
        )
    )

    monthly_performance = (
        aggregate_by_period(
            trades=trades,
            period_type="monthly",
        )
    )

    current_period_summary = (
        get_current_period_summary(
            daily_performance=daily_performance,
            weekly_performance=weekly_performance,
            monthly_performance=monthly_performance,
        )
    )

    by_symbol = aggregate_by_attribute(
        trades=trades,
        group_attribute="symbol",
    )

    by_direction = aggregate_by_attribute(
        trades=trades,
        group_attribute="direction",
    )

    by_trade_quality = (
        aggregate_by_attribute(
            trades=trades,
            group_attribute=(
                "trade_quality_grade"
            ),
            default_name="UNRATED",
        )
    )

    completed_trades = (
        overall["winning_trades"]
        + overall["losing_trades"]
    )

    return {
        "status": "success",
        "safety_version": 9,
        "analytics_ready": (
            len(trades) > 0
        ),
        "message": (
            "Performance analytics "
            "calculated successfully"
            if trades
            else (
                "Performance analytics is "
                "ready, but no trading "
                "history is available yet"
            )
        ),
        "overall": overall,
        "daily_performance": (
            daily_performance
        ),
        "weekly_performance": (
            weekly_performance
        ),
        "monthly_performance": (
            monthly_performance
        ),
        "current_period_summary": (
            current_period_summary
        ),
        "performance_by_symbol": (
            by_symbol
        ),
        "performance_by_direction": (
            by_direction
        ),
        "performance_by_trade_quality": (
            by_trade_quality
        ),
        "best_performing": {
            "day": get_best_period(
                daily_performance
            ),
            "week": get_best_period(
                weekly_performance
            ),
            "month": get_best_period(
                monthly_performance
            ),
            "symbol": get_best_group(
                by_symbol
            ),
            "direction": get_best_group(
                by_direction
            ),
            "trade_quality_grade": (
                get_best_group(
                    by_trade_quality
                )
            ),
        },
        "learning_status": {
            "enabled": True,
            "minimum_completed_trades_required": MINIMUM_LEARNING_TRADES,
            "completed_trades_available": (
                completed_trades
            ),
            "sufficient_learning_data": (
                completed_trades >= MINIMUM_LEARNING_TRADES
            ),
            "confidence_adjustment_active": False,
            "reason": (
                "Historical performance is "
                "being collected. Automatic "
                "confidence adjustment remains "
                "disabled until at least "
                f"{MINIMUM_LEARNING_TRADES} "
                "completed trades exist."
            ),
        },
    }

__all__ = [
    "LOSS_RESULTS",
    "MINIMUM_LEARNING_TRADES",
    "SUPPORTED_GROUP_ATTRIBUTES",
    "SUPPORTED_PERIOD_TYPES",
    "WIN_RESULTS",
    "add_trade_to_bucket",
    "aggregate_by_attribute",
    "aggregate_by_period",
    "calculate_rate",
    "create_empty_period_summary",
    "create_group_bucket",
    "determine_trade_outcome",
    "finalize_bucket",
    "find_period_record",
    "get_best_group",
    "get_best_period",
    "get_current_period_summary",
    "get_daily_period",
    "get_monthly_period",
    "get_overall_performance",
    "get_performance_analytics",
    "get_trade_result_datetime",
    "get_weekly_period",
    "normalize_datetime",
    "safe_float",
]