"""
Blue-Trading-AI
Version 29
learning_analytics_service.py

Analytics and calibration layer built on top of the Version 27/28
Learning Intelligence engine.

Included:
- Symbol performance
- Asian, European, and US session performance
- Market-condition performance
- BUY and SELL performance
- Confidence-band calibration
- Risk-reward performance
- Win/loss streak analysis
- Learning health score
- Recommendation generation

Excluded:
- Strategy optimization
- Strategy ranking
- Timeframe performance learning
- Broker connection
- Trade execution
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Dict, Final, Iterable, List, Mapping, Optional, Sequence

from app.services.learning_intelligence_integration import (
    get_learning_intelligence_service,
)
from app.services.learning_intelligence_service import (
    LearningStatistics,
    LearningTrade,
)


PROJECT_NAME: Final = "Blue-Trading-AI"
SAFETY_VERSION: Final = 29

MINIMUM_TRADES: Final = 20
MAXIMUM_CONFIDENCE_ADJUSTMENT: Final = 4
MAXIMUM_TRADE_HISTORY: Final = 100_000
MAXIMUM_GROUP_NAME_LENGTH: Final = 64
MAXIMUM_CATEGORY_COUNT: Final = 10_000

SUPPORTED_SESSIONS = {
    "asian",
    "european",
    "us",
}

SUPPORTED_DIRECTIONS = {
    "BUY",
    "SELL",
}

CONFIDENCE_BANDS = (
    (0.0, 74.99, "below_75"),
    (75.0, 79.99, "75_79"),
    (80.0, 84.99, "80_84"),
    (85.0, 89.99, "85_89"),
    (90.0, 94.99, "90_94"),
    (95.0, 100.0, "95_100"),
)

RISK_REWARD_BANDS = (
    (0.0, 0.99, "below_1"),
    (1.0, 1.49, "1_1_49"),
    (1.5, 1.99, "1_5_1_99"),
    (2.0, 2.99, "2_2_99"),
    (3.0, float("inf"), "3_plus"),
)


@dataclass
class CategoryPerformance:
    category: str
    total_trades: int
    wins: int
    losses: int
    breakeven: int
    win_rate: float
    loss_rate: float
    breakeven_rate: float
    average_confidence: float
    average_risk_reward: float
    current_win_streak: int
    current_loss_streak: int
    highest_win_streak: int
    highest_loss_streak: int
    eligible_for_learning: bool
    confidence_adjustment: int
    recommendation: str


@dataclass
class ConfidenceCalibration:
    band: str
    minimum_confidence: float
    maximum_confidence: float
    total_trades: int
    wins: int
    losses: int
    breakeven: int
    actual_win_rate: float
    expected_confidence_midpoint: float
    calibration_error: float
    calibration_status: str


@dataclass
class LearningHealth:
    score: float
    grade: str
    completed_trades: int
    eligible_categories: int
    total_categories: int
    data_coverage_score: float
    calibration_score: float
    streak_stability_score: float
    session_coverage_score: float
    recommendation: str


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return float(default)

    if not math.isfinite(number):
        return float(default)

    return number


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    if isinstance(value, bool):
        return int(default)

    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return int(default)

    return max(
        number,
        0,
    )


def _percentage(
    numerator: int,
    denominator: int,
) -> float:
    if denominator <= 0:
        return 0.0

    value = (
        _safe_float(
            numerator,
            0.0,
        )
        / _safe_float(
            denominator,
            1.0,
        )
        * 100.0
    )

    return round(
        max(
            0.0,
            min(
                value,
                100.0,
            ),
        ),
        2,
    )


def _bounded_adjustment(
    win_rate: float,
) -> int:
    if win_rate >= 90.0:
        adjustment = 4
    elif win_rate >= 85.0:
        adjustment = 3
    elif win_rate >= 80.0:
        adjustment = 2
    elif win_rate >= 75.0:
        adjustment = 1
    elif win_rate >= 65.0:
        adjustment = 0
    elif win_rate >= 55.0:
        adjustment = -1
    elif win_rate >= 45.0:
        adjustment = -2
    else:
        adjustment = -4

    return max(
        -MAXIMUM_CONFIDENCE_ADJUSTMENT,
        min(
            MAXIMUM_CONFIDENCE_ADJUSTMENT,
            adjustment,
        ),
    )


def _category_recommendation(
    *,
    total_trades: int,
    win_rate: float,
    current_loss_streak: int,
) -> str:
    if total_trades < MINIMUM_TRADES:
        return "COLLECT_MORE_DATA"

    if current_loss_streak >= 4:
        return "REQUIRE_STRONGER_CONFIRMATION"

    if win_rate < 45.0:
        return "RECOMMEND_WAIT"

    if win_rate < 65.0:
        return "REDUCE_CONFIDENCE"

    if win_rate >= 80.0:
        return "INCREASE_CONFIDENCE"

    return "MAINTAIN_CONFIDENCE"


def _statistics_to_performance(
    category: str,
    stats: LearningStatistics,
) -> CategoryPerformance:
    total = _safe_int(
        stats.total_trades
    )
    wins = min(
        _safe_int(
            stats.wins
        ),
        total,
    )
    losses = min(
        _safe_int(
            stats.losses
        ),
        total,
    )
    breakeven = min(
        _safe_int(
            stats.breakeven
        ),
        total,
    )
    win_rate = round(
        max(
            0.0,
            min(
                _safe_float(
                    stats.win_rate
                ),
                100.0,
            ),
        ),
        2,
    )

    eligible = total >= MINIMUM_TRADES

    adjustment = (
        _bounded_adjustment(win_rate)
        if eligible
        else 0
    )

    return CategoryPerformance(
        category=category,
        total_trades=total,
        wins=wins,
        losses=losses,
        breakeven=breakeven,
        win_rate=win_rate,
        loss_rate=_percentage(losses, total),
        breakeven_rate=_percentage(
            breakeven,
            total,
        ),
        average_confidence=round(
            max(
                0.0,
                min(
                    _safe_float(
                        stats.average_confidence
                    ),
                    100.0,
                ),
            ),
            2,
        ),
        average_risk_reward=round(
            max(
                0.0,
                _safe_float(
                    stats.average_rr
                ),
            ),
            4,
        ),
        current_win_streak=_safe_int(
            stats.current_win_streak
        ),
        current_loss_streak=_safe_int(
            stats.current_loss_streak
        ),
        highest_win_streak=_safe_int(
            stats.highest_win_streak
        ),
        highest_loss_streak=_safe_int(
            stats.highest_loss_streak
        ),
        eligible_for_learning=eligible,
        confidence_adjustment=adjustment,
        recommendation=_category_recommendation(
            total_trades=total,
            win_rate=win_rate,
            current_loss_streak=_safe_int(
                stats.current_loss_streak
            ),
        ),
    )


def _calculate_trade_statistics(
    trades: Sequence[LearningTrade],
) -> LearningStatistics:
    stats = LearningStatistics()

    confidence_sum = 0.0
    rr_sum = 0.0

    current_win_streak = 0
    current_loss_streak = 0
    highest_win_streak = 0
    highest_loss_streak = 0

    bounded_trades = list(
        trades[
            :MAXIMUM_TRADE_HISTORY
        ]
    )

    for trade in bounded_trades:
        if trade is None:
            continue

        result = str(
            getattr(
                trade,
                "result",
                "",
            )
        ).strip().upper()

        stats.total_trades += 1
        confidence_sum += max(
            0.0,
            min(
                _safe_float(
                    getattr(
                        trade,
                        "confidence",
                        0.0,
                    )
                ),
                100.0,
            ),
        )
        rr_sum += max(
            0.0,
            _safe_float(
                getattr(
                    trade,
                    "risk_reward",
                    0.0,
                )
            ),
        )

        if result == "WIN":
            stats.wins += 1
            current_win_streak += 1
            current_loss_streak = 0
            highest_win_streak = max(
                highest_win_streak,
                current_win_streak,
            )

        elif result == "LOSS":
            stats.losses += 1
            current_loss_streak += 1
            current_win_streak = 0
            highest_loss_streak = max(
                highest_loss_streak,
                current_loss_streak,
            )

        else:
            stats.breakeven += 1
            current_win_streak = 0
            current_loss_streak = 0

    if stats.total_trades > 0:
        stats.win_rate = _percentage(
            stats.wins,
            stats.total_trades,
        )
        stats.average_confidence = (
            confidence_sum / stats.total_trades
        )
        stats.average_rr = (
            rr_sum / stats.total_trades
        )

    stats.current_win_streak = current_win_streak
    stats.current_loss_streak = current_loss_streak
    stats.highest_win_streak = highest_win_streak
    stats.highest_loss_streak = highest_loss_streak

    return stats


def _group_trades(
    trades: Iterable[LearningTrade],
    key_getter,
) -> Dict[str, List[LearningTrade]]:
    grouped: Dict[str, List[LearningTrade]] = {}

    for index, trade in enumerate(
        trades,
    ):
        if index >= MAXIMUM_TRADE_HISTORY:
            break

        try:
            raw_key = key_getter(
                trade
            )
        except Exception:
            raw_key = "unknown"

        key = str(
            raw_key or "unknown"
        ).strip()[
            :MAXIMUM_GROUP_NAME_LENGTH
        ] or "unknown"

        if (
            key not in grouped
            and len(grouped)
            >= MAXIMUM_CATEGORY_COUNT
        ):
            key = "other"

        grouped.setdefault(
            key,
            [],
        ).append(
            trade
        )

    return grouped


def _confidence_band_name(
    confidence: float,
) -> str:
    resolved = max(
        0.0,
        min(100.0, _safe_float(confidence)),
    )

    for lower, upper, name in CONFIDENCE_BANDS:
        if lower <= resolved <= upper:
            return name

    return "unknown"


def _risk_reward_band_name(
    risk_reward: float,
) -> str:
    resolved = max(
        0.0,
        _safe_float(risk_reward),
    )

    for lower, upper, name in RISK_REWARD_BANDS:
        if lower <= resolved <= upper:
            return name

    return "unknown"


def build_category_performance(
    trades: Sequence[LearningTrade],
    category_name: str,
) -> CategoryPerformance:
    stats = _calculate_trade_statistics(
        trades
    )

    return _statistics_to_performance(
        category_name,
        stats,
    )


def get_symbol_performance() -> Dict[str, Dict[str, Any]]:
    service = get_learning_intelligence_service()

    symbol_statistics = getattr(
        service,
        "symbol_statistics",
        {},
    )

    if not isinstance(
        symbol_statistics,
        Mapping,
    ):
        return {}

    output: Dict[str, Dict[str, Any]] = {}

    for index, (
        symbol,
        stats,
    ) in enumerate(
        sorted(
            symbol_statistics.items()
        )
    ):
        if index >= MAXIMUM_CATEGORY_COUNT:
            break

        if not isinstance(
            stats,
            LearningStatistics,
        ):
            continue

        normalized_symbol = str(
            symbol
        ).strip().upper()[
            :MAXIMUM_GROUP_NAME_LENGTH
        ]

        if not normalized_symbol:
            continue

        output[
            normalized_symbol
        ] = asdict(
            _statistics_to_performance(
                normalized_symbol,
                stats,
            )
        )

    return output


def get_session_performance() -> Dict[str, Dict[str, Any]]:
    service = get_learning_intelligence_service()

    output: Dict[str, Dict[str, Any]] = {}

    for session in (
        "asian",
        "european",
        "us",
    ):
        session_statistics = getattr(
            service,
            "session_statistics",
            {},
        )

        if not isinstance(
            session_statistics,
            Mapping,
        ):
            session_statistics = {}

        stats = session_statistics.get(
            session,
            LearningStatistics(),
        )

        if not isinstance(
            stats,
            LearningStatistics,
        ):
            stats = LearningStatistics()

        output[session] = asdict(
            _statistics_to_performance(
                session,
                stats,
            )
        )

    return output


def get_market_condition_performance() -> Dict[str, Dict[str, Any]]:
    service = get_learning_intelligence_service()

    market_statistics = getattr(
        service,
        "market_statistics",
        {},
    )

    if not isinstance(
        market_statistics,
        Mapping,
    ):
        return {}

    output: Dict[str, Dict[str, Any]] = {}

    for index, (
        condition,
        stats,
    ) in enumerate(
        sorted(
            market_statistics.items()
        )
    ):
        if index >= MAXIMUM_CATEGORY_COUNT:
            break

        if not isinstance(
            stats,
            LearningStatistics,
        ):
            continue

        normalized_condition = str(
            condition
        ).strip().lower()[
            :MAXIMUM_GROUP_NAME_LENGTH
        ]

        if not normalized_condition:
            continue

        output[
            normalized_condition
        ] = asdict(
            _statistics_to_performance(
                normalized_condition,
                stats,
            )
        )

    return output


def get_direction_performance() -> Dict[str, Dict[str, Any]]:
    service = get_learning_intelligence_service()

    trade_history = getattr(
        service,
        "trade_history",
        [],
    )

    if not isinstance(
        trade_history,
        Sequence,
    ):
        trade_history = []

    grouped = _group_trades(
        trade_history,
        lambda trade: str(
            trade.direction
        ).strip().upper(),
    )

    output: Dict[str, Dict[str, Any]] = {}

    for direction in (
        "BUY",
        "SELL",
    ):
        output[direction] = asdict(
            build_category_performance(
                grouped.get(direction, []),
                direction,
            )
        )

    return output


def get_risk_reward_performance() -> Dict[str, Dict[str, Any]]:
    service = get_learning_intelligence_service()

    trade_history = getattr(
        service,
        "trade_history",
        [],
    )

    if not isinstance(
        trade_history,
        Sequence,
    ):
        trade_history = []

    grouped = _group_trades(
        trade_history,
        lambda trade: _risk_reward_band_name(
            trade.risk_reward
        ),
    )

    output: Dict[str, Dict[str, Any]] = {}

    for _, _, band_name in RISK_REWARD_BANDS:
        output[band_name] = asdict(
            build_category_performance(
                grouped.get(band_name, []),
                band_name,
            )
        )

    return output


def get_confidence_calibration() -> Dict[str, Dict[str, Any]]:
    service = get_learning_intelligence_service()

    trade_history = getattr(
        service,
        "trade_history",
        [],
    )

    if not isinstance(
        trade_history,
        Sequence,
    ):
        trade_history = []

    grouped = _group_trades(
        trade_history,
        lambda trade: _confidence_band_name(
            trade.confidence
        ),
    )

    output: Dict[str, Dict[str, Any]] = {}

    for lower, upper, band_name in CONFIDENCE_BANDS:
        trades = grouped.get(
            band_name,
            [],
        )

        total = len(trades)
        wins = sum(
            1
            for trade in trades
            if str(trade.result).upper() == "WIN"
        )
        losses = sum(
            1
            for trade in trades
            if str(trade.result).upper() == "LOSS"
        )
        breakeven = total - wins - losses

        actual_win_rate = _percentage(
            wins,
            total,
        )

        midpoint = round(
            (lower + upper) / 2.0,
            2,
        )

        calibration_error = round(
            actual_win_rate - midpoint,
            2,
        )

        absolute_error = abs(
            calibration_error
        )

        if total < MINIMUM_TRADES:
            status = "INSUFFICIENT_DATA"
        elif absolute_error <= 5.0:
            status = "WELL_CALIBRATED"
        elif calibration_error < -5.0:
            status = "OVERCONFIDENT"
        else:
            status = "UNDERCONFIDENT"

        output[band_name] = asdict(
            ConfidenceCalibration(
                band=band_name,
                minimum_confidence=lower,
                maximum_confidence=upper,
                total_trades=total,
                wins=wins,
                losses=losses,
                breakeven=breakeven,
                actual_win_rate=actual_win_rate,
                expected_confidence_midpoint=midpoint,
                calibration_error=calibration_error,
                calibration_status=status,
            )
        )

    return output


def get_streak_analysis() -> Dict[str, Any]:
    service = get_learning_intelligence_service()

    trade_history = getattr(
        service,
        "trade_history",
        [],
    )

    if not isinstance(
        trade_history,
        Sequence,
    ):
        trade_history = []

    stats = _calculate_trade_statistics(
        trade_history
    )

    risk_level = "LOW"

    if stats.current_loss_streak >= 5:
        risk_level = "CRITICAL"
    elif stats.current_loss_streak >= 3:
        risk_level = "HIGH"
    elif stats.current_loss_streak >= 2:
        risk_level = "MEDIUM"

    recommendation = "NORMAL_OPERATION"

    if risk_level == "CRITICAL":
        recommendation = "RECOMMEND_WAIT"
    elif risk_level == "HIGH":
        recommendation = (
            "REQUIRE_STRONGER_CONFIRMATION"
        )
    elif risk_level == "MEDIUM":
        recommendation = (
            "REDUCE_CONFIDENCE_SLIGHTLY"
        )

    return {
        "current_win_streak": (
            stats.current_win_streak
        ),
        "current_loss_streak": (
            stats.current_loss_streak
        ),
        "highest_win_streak": (
            stats.highest_win_streak
        ),
        "highest_loss_streak": (
            stats.highest_loss_streak
        ),
        "loss_streak_risk_level": risk_level,
        "recommendation": recommendation,
    }


def get_learning_health() -> Dict[str, Any]:
    service = get_learning_intelligence_service()

    trade_history = getattr(
        service,
        "trade_history",
        [],
    )

    if not isinstance(
        trade_history,
        Sequence,
    ):
        trade_history = []

    total_trades = min(
        len(
            trade_history
        ),
        MAXIMUM_TRADE_HISTORY,
    )

    symbol_performance = get_symbol_performance()
    session_performance = get_session_performance()
    market_performance = (
        get_market_condition_performance()
    )
    calibration = get_confidence_calibration()
    streaks = get_streak_analysis()

    categories: List[Dict[str, Any]] = []

    categories.extend(
        symbol_performance.values()
    )
    categories.extend(
        session_performance.values()
    )
    categories.extend(
        market_performance.values()
    )

    total_categories = len(categories)
    eligible_categories = sum(
        1
        for item in categories
        if item.get("eligible_for_learning")
    )

    data_coverage_score = min(
        100.0,
        total_trades / 100.0 * 100.0,
    )

    calibrated_bands = [
        item
        for item in calibration.values()
        if item.get("calibration_status")
        != "INSUFFICIENT_DATA"
    ]

    well_calibrated_count = sum(
        1
        for item in calibrated_bands
        if item.get("calibration_status")
        == "WELL_CALIBRATED"
    )

    calibration_score = (
        _percentage(
            well_calibrated_count,
            len(calibrated_bands),
        )
        if calibrated_bands
        else 0.0
    )

    current_loss_streak = _safe_int(
        streaks.get("current_loss_streak")
    )

    streak_stability_score = max(
        0.0,
        100.0 - current_loss_streak * 20.0,
    )

    session_coverage_count = sum(
        1
        for session_data in session_performance.values()
        if _safe_int(
            session_data.get("total_trades")
        ) > 0
    )

    session_coverage_score = _percentage(
        session_coverage_count,
        3,
    )

    health_score = round(
        data_coverage_score * 0.35
        + calibration_score * 0.30
        + streak_stability_score * 0.20
        + session_coverage_score * 0.15,
        2,
    )

    if health_score >= 90.0:
        grade = "A"
        recommendation = "LEARNING_HEALTHY"
    elif health_score >= 75.0:
        grade = "B"
        recommendation = "LEARNING_STABLE"
    elif health_score >= 60.0:
        grade = "C"
        recommendation = "COLLECT_MORE_DATA"
    elif health_score >= 40.0:
        grade = "D"
        recommendation = (
            "REQUIRE_STRONGER_CONFIRMATION"
        )
    else:
        grade = "F"
        recommendation = (
            "LEARNING_NOT_READY"
        )

    return asdict(
        LearningHealth(
            score=health_score,
            grade=grade,
            completed_trades=total_trades,
            eligible_categories=eligible_categories,
            total_categories=total_categories,
            data_coverage_score=round(
                data_coverage_score,
                2,
            ),
            calibration_score=round(
                calibration_score,
                2,
            ),
            streak_stability_score=round(
                streak_stability_score,
                2,
            ),
            session_coverage_score=round(
                session_coverage_score,
                2,
            ),
            recommendation=recommendation,
        )
    )


def get_learning_analytics_summary() -> Dict[str, Any]:
    """
    Return the complete Version 29 analytics payload.
    """

    service = get_learning_intelligence_service()

    return {
        "status": "success",
        "project": PROJECT_NAME,
        "version": 29,
        "safety_version": SAFETY_VERSION,
        "module": (
            "Learning Analytics and Confidence Calibration"
        ),
        "completed_trades": min(
            len(
                getattr(
                    service,
                    "trade_history",
                    [],
                )
                if isinstance(
                    getattr(
                        service,
                        "trade_history",
                        [],
                    ),
                    Sequence,
                )
                else []
            ),
            MAXIMUM_TRADE_HISTORY,
        ),
        "symbol_performance": (
            get_symbol_performance()
        ),
        "session_performance": (
            get_session_performance()
        ),
        "market_condition_performance": (
            get_market_condition_performance()
        ),
        "direction_performance": (
            get_direction_performance()
        ),
        "confidence_calibration": (
            get_confidence_calibration()
        ),
        "risk_reward_performance": (
            get_risk_reward_performance()
        ),
        "streak_analysis": (
            get_streak_analysis()
        ),
        "learning_health": (
            get_learning_health()
        ),
        "rules": {
            "minimum_completed_trades": (
                MINIMUM_TRADES
            ),
            "maximum_confidence_adjustment": (
                MAXIMUM_CONFIDENCE_ADJUSTMENT
            ),
            "session_performance_enabled": True,
            "timeframe_performance_enabled": False,
            "strategy_optimization_enabled": False,
            "strategy_ranking_enabled": False,
        },
        "safety": {
            "analysis_only": True,
            "broker_connection_enabled": False,
            "trade_execution_enabled": False,
            "automatic_order_placement_enabled": False,
        },
    }


__all__ = [
    "CONFIDENCE_BANDS",
    "CategoryPerformance",
    "ConfidenceCalibration",
    "LearningHealth",
    "MAXIMUM_CONFIDENCE_ADJUSTMENT",
    "MAXIMUM_TRADE_HISTORY",
    "MINIMUM_TRADES",
    "PROJECT_NAME",
    "RISK_REWARD_BANDS",
    "SAFETY_VERSION",
    "SUPPORTED_DIRECTIONS",
    "SUPPORTED_SESSIONS",
    "build_category_performance",
    "get_confidence_calibration",
    "get_direction_performance",
    "get_learning_analytics_summary",
    "get_learning_health",
    "get_market_condition_performance",
    "get_risk_reward_performance",
    "get_session_performance",
    "get_streak_analysis",
    "get_symbol_performance",
]