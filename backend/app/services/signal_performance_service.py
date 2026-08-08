from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Final

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.trading_signal import (
    TradingSignal,
    SIGNAL_RESULT_BREAKEVEN,
    SIGNAL_RESULT_LOSS,
    SIGNAL_RESULT_WIN,
    SIGNAL_STATUS_COMPLETED,
)


LEARNING_MINIMUM_COMPLETED_TRADES: Final[int] = 20
MAXIMUM_RECENT_LIMIT: Final[int] = 500
MAXIMUM_RATE: Final[Decimal] = Decimal("100.00")


def _safe_decimal(
    value: Any,
    default: Decimal = Decimal("0"),
) -> Decimal:
    if value is None:
        return default

    try:
        resolved = Decimal(
            str(value)
        )
    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ):
        return default

    if not resolved.is_finite():
        return default

    return resolved


def _safe_rate(
    numerator: int,
    denominator: int,
) -> Decimal:
    try:
        safe_numerator = max(
            0,
            int(
                numerator
            ),
        )
        safe_denominator = max(
            0,
            int(
                denominator
            ),
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return Decimal("0.00")

    if safe_denominator <= 0:
        return Decimal("0.00")

    rate = (
        Decimal(
            safe_numerator
        )
        / Decimal(
            safe_denominator
        )
        * Decimal("100")
    )

    return min(
        max(
            rate,
            Decimal("0.00"),
        ),
        MAXIMUM_RATE,
    ).quantize(
        Decimal("0.01")
    )



def _safe_non_negative_int(
    value: Any,
    default: int = 0,
) -> int:
    if isinstance(
        value,
        bool,
    ):
        return default

    try:
        resolved = int(
            value
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return default

    return max(
        0,
        resolved,
    )

def get_completed_signal_counts(
    db: Session,
) -> dict[str, int]:
    """
    Return completed signal outcome totals.
    """

    total_completed = _safe_non_negative_int(
        db.query(
            func.count(
                TradingSignal.id
            )
        )
        .filter(
            TradingSignal.status
            == SIGNAL_STATUS_COMPLETED
        )
        .scalar()
        or 0
    )

    wins = _safe_non_negative_int(
        db.query(
            func.count(
                TradingSignal.id
            )
        )
        .filter(
            TradingSignal.status
            == SIGNAL_STATUS_COMPLETED,
            TradingSignal.result
            == SIGNAL_RESULT_WIN,
        )
        .scalar()
        or 0
    )

    losses = _safe_non_negative_int(
        db.query(
            func.count(
                TradingSignal.id
            )
        )
        .filter(
            TradingSignal.status
            == SIGNAL_STATUS_COMPLETED,
            TradingSignal.result
            == SIGNAL_RESULT_LOSS,
        )
        .scalar()
        or 0
    )

    breakevens = _safe_non_negative_int(
        db.query(
            func.count(
                TradingSignal.id
            )
        )
        .filter(
            TradingSignal.status
            == SIGNAL_STATUS_COMPLETED,
            TradingSignal.result
            == SIGNAL_RESULT_BREAKEVEN,
        )
        .scalar()
        or 0
    )

    return {
        "total_completed": total_completed,
        "wins": wins,
        "losses": losses,
        "breakevens": breakevens,
    }


def get_overall_performance(
    db: Session,
) -> dict[str, Any]:
    """
    Return overall completed-signal performance metrics.
    """

    counts = get_completed_signal_counts(db)

    decisive_trades = (
        counts["wins"]
        + counts["losses"]
    )

    average_confidence = (
        db.query(
            func.avg(TradingSignal.confidence)
        )
        .filter(
            TradingSignal.status
            == SIGNAL_STATUS_COMPLETED
        )
        .scalar()
    )

    average_risk_reward = (
        db.query(
            func.avg(
                TradingSignal.risk_reward_ratio
            )
        )
        .filter(
            TradingSignal.status
            == SIGNAL_STATUS_COMPLETED,
            TradingSignal.risk_reward_ratio.isnot(
                None
            ),
        )
        .scalar()
    )

    win_rate = _safe_rate(
        counts["wins"],
        decisive_trades,
    )

    completion_quality_rate = _safe_rate(
        counts["wins"] + counts["breakevens"],
        counts["total_completed"],
    )

    return {
        **counts,
        "decisive_trades": decisive_trades,
        "win_rate": win_rate,
        "non_loss_rate": completion_quality_rate,
        "average_confidence": min(
            max(
                _safe_decimal(
                    average_confidence
                ),
                Decimal("0"),
            ),
            Decimal("100"),
        ).quantize(
            Decimal("0.01")
        ),
        "average_risk_reward": max(
            _safe_decimal(
                average_risk_reward
            ),
            Decimal("0"),
        ).quantize(
            Decimal("0.0001")
        ),
        "learning_minimum_completed_trades": (
            LEARNING_MINIMUM_COMPLETED_TRADES
        ),
        "learning_ready": (
            counts["total_completed"]
            >= LEARNING_MINIMUM_COMPLETED_TRADES
        ),
        "learning_trades_remaining": max(
            0,
            LEARNING_MINIMUM_COMPLETED_TRADES
            - counts["total_completed"],
        ),
    }


def get_symbol_performance(
    db: Session,
) -> list[dict[str, Any]]:
    """
    Return grouped completed performance by symbol.
    """

    rows = (
        db.query(
            TradingSignal.symbol,
            func.count(TradingSignal.id).label(
                "total_completed"
            ),
            func.sum(
                case(
                    (
                        TradingSignal.result
                        == SIGNAL_RESULT_WIN,
                        1,
                    ),
                    else_=0,
                )
            ).label("wins"),
            func.sum(
                case(
                    (
                        TradingSignal.result
                        == SIGNAL_RESULT_LOSS,
                        1,
                    ),
                    else_=0,
                )
            ).label("losses"),
            func.sum(
                case(
                    (
                        TradingSignal.result
                        == SIGNAL_RESULT_BREAKEVEN,
                        1,
                    ),
                    else_=0,
                )
            ).label("breakevens"),
            func.avg(
                TradingSignal.confidence
            ).label("average_confidence"),
            func.avg(
                TradingSignal.risk_reward_ratio
            ).label("average_risk_reward"),
        )
        .filter(
            TradingSignal.status
            == SIGNAL_STATUS_COMPLETED
        )
        .group_by(TradingSignal.symbol)
        .order_by(
            func.count(TradingSignal.id).desc(),
            TradingSignal.symbol.asc(),
        )
        .all()
    )

    result: list[dict[str, Any]] = []

    for row in rows:
        wins = _safe_non_negative_int(
            row.wins or 0
        )
        losses = _safe_non_negative_int(
            row.losses or 0
        )
        breakevens = _safe_non_negative_int(
            row.breakevens or 0
        )
        decisive = wins + losses

        result.append(
            {
                "symbol": str(
                    row.symbol or ""
                ).strip().upper(),
                "total_completed": _safe_non_negative_int(
                    row.total_completed or 0
                ),
                "wins": wins,
                "losses": losses,
                "breakevens": breakevens,
                "win_rate": _safe_rate(
                    wins,
                    decisive,
                ),
                "average_confidence": (
                    min(
                        max(
                            _safe_decimal(
                                row.average_confidence
                            ),
                            Decimal("0"),
                        ),
                        Decimal("100"),
                    ).quantize(
                        Decimal("0.01")
                    )
                ),
                "average_risk_reward": (
                    max(
                        _safe_decimal(
                            row.average_risk_reward
                        ),
                        Decimal("0"),
                    ).quantize(
                        Decimal("0.0001")
                    )
                ),
            }
        )

    return result


def get_timeframe_performance(
    db: Session,
) -> list[dict[str, Any]]:
    """
    Return grouped completed performance by timeframe.
    """

    rows = (
        db.query(
            TradingSignal.timeframe,
            func.count(TradingSignal.id).label(
                "total_completed"
            ),
            func.sum(
                case(
                    (
                        TradingSignal.result
                        == SIGNAL_RESULT_WIN,
                        1,
                    ),
                    else_=0,
                )
            ).label("wins"),
            func.sum(
                case(
                    (
                        TradingSignal.result
                        == SIGNAL_RESULT_LOSS,
                        1,
                    ),
                    else_=0,
                )
            ).label("losses"),
            func.sum(
                case(
                    (
                        TradingSignal.result
                        == SIGNAL_RESULT_BREAKEVEN,
                        1,
                    ),
                    else_=0,
                )
            ).label("breakevens"),
            func.avg(
                TradingSignal.confidence
            ).label("average_confidence"),
            func.avg(
                TradingSignal.risk_reward_ratio
            ).label("average_risk_reward"),
        )
        .filter(
            TradingSignal.status
            == SIGNAL_STATUS_COMPLETED
        )
        .group_by(TradingSignal.timeframe)
        .order_by(
            func.count(TradingSignal.id).desc(),
            TradingSignal.timeframe.asc(),
        )
        .all()
    )

    result: list[dict[str, Any]] = []

    for row in rows:
        wins = _safe_non_negative_int(
            row.wins or 0
        )
        losses = _safe_non_negative_int(
            row.losses or 0
        )
        breakevens = _safe_non_negative_int(
            row.breakevens or 0
        )
        decisive = wins + losses

        result.append(
            {
                "timeframe": str(
                    row.timeframe or ""
                ).strip().upper(),
                "total_completed": _safe_non_negative_int(
                    row.total_completed or 0
                ),
                "wins": wins,
                "losses": losses,
                "breakevens": breakevens,
                "win_rate": _safe_rate(
                    wins,
                    decisive,
                ),
                "average_confidence": (
                    min(
                        max(
                            _safe_decimal(
                                row.average_confidence
                            ),
                            Decimal("0"),
                        ),
                        Decimal("100"),
                    ).quantize(
                        Decimal("0.01")
                    )
                ),
                "average_risk_reward": (
                    max(
                        _safe_decimal(
                            row.average_risk_reward
                        ),
                        Decimal("0"),
                    ).quantize(
                        Decimal("0.0001")
                    )
                ),
            }
        )

    return result


def get_recent_completed_signals(
    db: Session,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    Return safe recent completed signal history.
    """

    if isinstance(
        limit,
        bool,
    ):
        resolved_limit = 50
    else:
        try:
            resolved_limit = int(
                limit
            )
        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            resolved_limit = 50

    resolved_limit = max(
        1,
        min(
            resolved_limit,
            MAXIMUM_RECENT_LIMIT,
        ),
    )

    rows = (
        db.query(TradingSignal)
        .filter(
            TradingSignal.status
            == SIGNAL_STATUS_COMPLETED
        )
        .order_by(
            TradingSignal.completed_at.desc(),
            TradingSignal.id.desc(),
        )
        .limit(resolved_limit)
        .all()
    )

    result: list[
        dict[str, Any]
    ] = []

    for signal in rows:
        payload = signal.to_public_dict()

        if isinstance(
            payload,
            dict,
        ):
            result.append(
                payload
            )

    return result


def get_performance_snapshot(
    db: Session,
    *,
    recent_limit: int = 50,
) -> dict[str, Any]:
    """
    Build the complete Version 44 performance snapshot.
    """

    return {
        "overall": get_overall_performance(db),
        "by_symbol": get_symbol_performance(db),
        "by_timeframe": get_timeframe_performance(
            db
        ),
        "recent_completed_signals": (
            get_recent_completed_signals(
                db,
                limit=recent_limit,
            )
        ),
    }


__all__ = [
    "LEARNING_MINIMUM_COMPLETED_TRADES",
    "MAXIMUM_RECENT_LIMIT",
    "get_completed_signal_counts",
    "get_overall_performance",
    "get_performance_snapshot",
    "get_recent_completed_signals",
    "get_symbol_performance",
    "get_timeframe_performance",
]