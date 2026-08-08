"""
Blue-Trading-AI
Version 28
learning_persistence_service.py

Rebuilds Version 27 Learning Intelligence from completed trades stored
in the database.

Analysis only:
- No broker connection
- No order placement
- No automatic trade execution
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Final, Iterable, Optional

from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.models.trade_history import TradeHistory
from app.services.learning_intelligence_integration import (
    get_learning_intelligence_service,
    get_learning_summary,
    reset_learning_intelligence_service,
)
from app.services.learning_intelligence_service import LearningTrade


logger = logging.getLogger(__name__)

PROJECT_NAME: Final = "Blue-Trading-AI"
SAFETY_VERSION: Final = 28

BROKER_CONNECTION_ENABLED: Final = False
TRADE_EXECUTION_ENABLED: Final = False
AUTOMATIC_ORDER_PLACEMENT_ENABLED: Final = False

MALAYSIA_TIMEZONE: Final = timezone(timedelta(hours=8))
MAXIMUM_SYMBOL_LENGTH: Final = 30
MAXIMUM_MARKET_CONDITION_LENGTH: Final = 80
MAXIMUM_REBUILD_TRADES: Final = 100_000

SUPPORTED_LEARNING_RESULTS = {
    "WIN",
    "LOSS",
    "BREAKEVEN",
}

IGNORED_DATABASE_RESULTS = {
    "PENDING",
    "TP1_HIT",
    "CANCELLED",
}


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """Convert a value safely into a finite float."""

    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return float(default)

    if not math.isfinite(number):
        return float(default)

    return number


def _normalise_symbol(value: Any) -> str:
    """
    Normalise a market symbol.
    """

    symbol = (
        str(value or "")
        .strip()
        .upper()
        .replace("/", "")
        .replace("-", "")
        .replace("_", "")
        .replace(" ", "")
    )

    if len(symbol) > MAXIMUM_SYMBOL_LENGTH:
        return ""

    if symbol and not symbol.isalnum():
        return ""

    return symbol


def _normalise_direction(value: Any) -> Optional[str]:
    """
    Convert stored direction values into BUY or SELL.
    """

    direction = str(value or "").strip().upper()

    aliases = {
        "LONG": "BUY",
        "BULLISH": "BUY",
        "SHORT": "SELL",
        "BEARISH": "SELL",
    }

    direction = aliases.get(direction, direction)

    if direction not in {"BUY", "SELL"}:
        return None

    return direction


def _normalise_learning_result(
    value: Any,
) -> Optional[str]:
    """
    Convert database trade results into Version 28 learning results.
    """

    result = str(value or "").strip().upper()

    win_results = {
        "TP2_HIT",
        "WIN",
        "WON",
        "PROFIT",
        "SUCCESS",
    }

    loss_results = {
        "STOP_LOSS",
        "LOSS",
        "LOST",
        "FAIL",
        "FAILED",
    }

    breakeven_results = {
        "BREAKEVEN",
        "BREAK_EVEN",
        "BREAK-EVEN",
        "BE",
        "DRAW",
    }

    if result in win_results:
        return "WIN"

    if result in loss_results:
        return "LOSS"

    if result in breakeven_results:
        return "BREAKEVEN"

    return None


def _normalise_market_condition(
    value: Any,
) -> str:
    """
    Normalise the persisted market condition.
    """

    condition = (
        str(value or "")
        .strip()
        .lower()
        .replace(" ", "_")
    )

    condition = condition or "unknown"

    if len(condition) > MAXIMUM_MARKET_CONDITION_LENGTH:
        return "unknown"

    allowed_characters = set(
        "abcdefghijklmnopqrstuvwxyz0123456789_-"
    )

    if any(
        character not in allowed_characters
        for character in condition
    ):
        return "unknown"

    return condition


def _resolve_datetime(
    value: Any,
    fallback: Optional[datetime] = None,
) -> datetime:
    """
    Return a timezone-aware datetime.
    """

    resolved = value if isinstance(value, datetime) else fallback

    if not isinstance(resolved, datetime):
        resolved = datetime.now(timezone.utc)

    if resolved.tzinfo is None:
        resolved = resolved.replace(
            tzinfo=timezone.utc
        )

    return resolved.astimezone(
        timezone.utc
    )


def determine_session_from_time(
    timestamp: datetime,
) -> str:
    """
    Determine Asian, European, or US session using Malaysia time.

    Configured MYT windows:
    - Asian: 07:00-16:00
    - European: 15:00-00:00
    - US: 20:00-05:00

    Overlap priority:
    - US
    - European
    - Asian
    """

    resolved = _resolve_datetime(timestamp)
    malaysia_time = resolved.astimezone(MALAYSIA_TIMEZONE)
    hour = malaysia_time.hour

    if hour >= 20 or hour < 5:
        return "us"

    if 15 <= hour < 20:
        return "european"

    return "asian"


def _normalise_session(
    value: Any,
    fallback_time: datetime,
) -> str:
    """
    Normalise a stored session or derive it from trade time.
    """

    raw = str(value or "").strip().lower()

    aliases = {
        "asia": "asian",
        "asian": "asian",
        "tokyo": "asian",
        "europe": "european",
        "euro": "european",
        "european": "european",
        "london": "european",
        "us": "us",
        "usa": "us",
        "american": "us",
        "new_york": "us",
        "new york": "us",
        "ny": "us",
    }

    session = aliases.get(raw)

    if session:
        return session

    return determine_session_from_time(fallback_time)


def calculate_planned_risk_reward(
    trade: TradeHistory,
) -> float:
    """
    Calculate planned TP2 reward-to-risk ratio.
    """

    entry = _safe_float(
        getattr(trade, "entry_price", None),
    )
    stop_loss = _safe_float(
        getattr(trade, "stop_loss", None),
    )
    take_profit_2 = _safe_float(
        getattr(trade, "take_profit_2", None),
    )

    if min(
        entry,
        stop_loss,
        take_profit_2,
    ) < 0.0:
        return 0.0

    original_risk = abs(
        entry - stop_loss
    )

    if original_risk <= 0.0:
        return 0.0

    reward = abs(
        take_profit_2 - entry
    )

    ratio = reward / original_risk

    if not math.isfinite(ratio):
        return 0.0

    return round(
        max(ratio, 0.0),
        4,
    )


def trade_history_to_learning_trade(
    trade: TradeHistory,
) -> Optional[LearningTrade]:
    """
    Convert one completed TradeHistory row into a LearningTrade.
    """

    status = str(
        getattr(trade, "status", "") or ""
    ).strip().upper()

    if status != "CLOSED":
        return None

    result = _normalise_learning_result(
        getattr(trade, "result", None)
    )

    if result not in SUPPORTED_LEARNING_RESULTS:
        return None

    symbol = _normalise_symbol(
        getattr(trade, "symbol", None)
    )

    direction = _normalise_direction(
        getattr(trade, "direction", None)
    )

    if not symbol or direction is None:
        return None

    closed_at = _resolve_datetime(
        getattr(trade, "closed_at", None),
        getattr(trade, "updated_at", None),
    )

    opened_at = _resolve_datetime(
        getattr(trade, "created_at", None),
        closed_at,
    )

    if closed_at < opened_at:
        opened_at = closed_at

    session = _normalise_session(
        getattr(trade, "market_session", None),
        closed_at,
    )

    market_condition = _normalise_market_condition(
        getattr(trade, "market_condition", None)
    )

    confidence = max(
        0.0,
        min(
            100.0,
            _safe_float(
                getattr(trade, "confidence", None)
            ),
        ),
    )

    entry_price = _safe_float(
        getattr(trade, "entry_price", None)
    )
    stop_loss = _safe_float(
        getattr(trade, "stop_loss", None)
    )
    take_profit = _safe_float(
        getattr(trade, "take_profit_2", None)
    )

    if min(entry_price, stop_loss, take_profit) < 0.0:
        return None

    risk_reward = calculate_planned_risk_reward(trade)

    return LearningTrade(
        symbol=symbol,
        session=session,
        market_condition=market_condition,
        direction=direction,
        confidence=confidence,
        risk_reward=risk_reward,
        result=result,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        opened_at=opened_at,
        closed_at=closed_at,
    )


def get_completed_learning_trades(
    db: Session,
) -> list[TradeHistory]:
    """
    Load all closed database trades in chronological order.
    """

    return (
        db.query(TradeHistory)
        .filter(TradeHistory.status == "CLOSED")
        .order_by(
            TradeHistory.closed_at.asc(),
            TradeHistory.id.asc(),
        )
        .limit(MAXIMUM_REBUILD_TRADES)
        .all()
    )


def rebuild_learning_from_trades(
    trades: Iterable[TradeHistory],
    *,
    reset_engine: bool = True,
) -> Dict[str, Any]:
    """
    Rebuild the in-memory learning engine from completed database trades.
    """

    if reset_engine:
        reset_learning_intelligence_service()

    service = get_learning_intelligence_service()

    loaded_count = 0
    skipped_count = 0
    result_counts = {
        "WIN": 0,
        "LOSS": 0,
        "BREAKEVEN": 0,
    }
    session_counts = {
        "asian": 0,
        "european": 0,
        "us": 0,
    }

    for index, trade in enumerate(trades):
        if index >= MAXIMUM_REBUILD_TRADES:
            break

        try:
            learning_trade = trade_history_to_learning_trade(trade)
        except Exception:
            logger.exception(
                "Skipping malformed trade-history row during learning rebuild."
            )
            skipped_count += 1
            continue

        if learning_trade is None:
            skipped_count += 1
            continue

        service.add_completed_trade(learning_trade)

        loaded_count += 1
        result_counts[learning_trade.result] += 1
        session_counts[learning_trade.session] += 1

    summary = get_learning_summary()

    return {
        "status": "success",
        "project": PROJECT_NAME,
        "version": 28,
        "safety_version": SAFETY_VERSION,
        "engine_reset": reset_engine,
        "loaded_completed_trades": loaded_count,
        "skipped_database_rows": skipped_count,
        "result_counts": result_counts,
        "session_counts": session_counts,
        "learning_summary": summary,
        "timeframe_performance_learning_enabled": False,
        "session_performance_learning_enabled": True,
        "analysis_only": True,
        "broker_connection_enabled": (
            BROKER_CONNECTION_ENABLED
        ),
        "trade_execution_enabled": (
            TRADE_EXECUTION_ENABLED
        ),
        "automatic_order_placement_enabled": (
            AUTOMATIC_ORDER_PLACEMENT_ENABLED
        ),
    }


def rebuild_learning_from_database(
    db: Optional[Session] = None,
    *,
    reset_engine: bool = True,
) -> Dict[str, Any]:
    """
    Rebuild learning from the persistent trade_history database table.
    """

    owns_session = db is None
    resolved_db = db or SessionLocal()

    try:
        trades = get_completed_learning_trades(
            resolved_db
        )

        result = rebuild_learning_from_trades(
            trades,
            reset_engine=reset_engine,
        )

        logger.info(
            "Version 28 learning persistence loaded %s trades.",
            result["loaded_completed_trades"],
        )

        return result

    except Exception:
        logger.exception(
            "Version 28 learning persistence rebuild failed."
        )
        raise

    finally:
        if owns_session:
            resolved_db.close()


def get_learning_persistence_status(
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    Return database and in-memory persistence status.
    """

    owns_session = db is None
    resolved_db = db or SessionLocal()

    try:
        total_closed = (
            resolved_db.query(TradeHistory)
            .filter(TradeHistory.status == "CLOSED")
            .count()
        )

        eligible_count = 0

        for trade in get_completed_learning_trades(
            resolved_db
        ):
            try:
                learning_trade = trade_history_to_learning_trade(trade)
            except Exception:
                logger.exception(
                    "Skipping malformed trade-history row during persistence status."
                )
                continue

            if learning_trade is not None:
                eligible_count += 1

        summary = get_learning_summary()

        return {
            "status": "success",
            "project": PROJECT_NAME,
            "version": 28,
            "database_closed_trades": int(total_closed),
            "database_learning_eligible_trades": (
                eligible_count
            ),
            "in_memory_learning_trades": int(
                summary.get(
                    "total_completed_trades",
                    0,
                )
            ),
            "learning_restored": (
                int(
                    summary.get(
                        "total_completed_trades",
                        0,
                    )
                )
                == eligible_count
            ),
            "supported_sessions": [
                "asian",
                "european",
                "us",
            ],
            "supported_results": sorted(
                SUPPORTED_LEARNING_RESULTS
            ),
            "timeframe_performance_learning_enabled": False,
            "session_performance_learning_enabled": True,
            "analysis_only": True,
            "broker_connection_enabled": False,
            "trade_execution_enabled": False,
        }

    finally:
        if owns_session:
            resolved_db.close()


def initialise_learning_persistence() -> Dict[str, Any]:
    """
    Startup helper used by the FastAPI lifespan function.
    """

    logger.info(
        "Initialising Version 28 Persistent Learning Intelligence."
    )

    return rebuild_learning_from_database(
        reset_engine=True,
    )


__all__ = [
    "AUTOMATIC_ORDER_PLACEMENT_ENABLED",
    "BROKER_CONNECTION_ENABLED",
    "MAXIMUM_REBUILD_TRADES",
    "PROJECT_NAME",
    "SAFETY_VERSION",
    "SUPPORTED_LEARNING_RESULTS",
    "TRADE_EXECUTION_ENABLED",
    "calculate_planned_risk_reward",
    "determine_session_from_time",
    "get_completed_learning_trades",
    "get_learning_persistence_status",
    "initialise_learning_persistence",
    "rebuild_learning_from_database",
    "rebuild_learning_from_trades",
    "trade_history_to_learning_trade",
]