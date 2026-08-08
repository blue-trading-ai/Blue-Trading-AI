from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Final, Optional
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.trade_history import (
    MAXIMUM_DIRECTION_LENGTH as MODEL_MAXIMUM_DIRECTION_LENGTH,
    MAXIMUM_ENGINE_VERSION_LENGTH as MODEL_MAXIMUM_ENGINE_VERSION_LENGTH,
    MAXIMUM_INTERVAL_LENGTH as MODEL_MAXIMUM_INTERVAL_LENGTH,
    MAXIMUM_MARKET_CONDITION_LENGTH as MODEL_MAXIMUM_MARKET_CONDITION_LENGTH,
    MAXIMUM_MARKET_SESSION_LENGTH as MODEL_MAXIMUM_MARKET_SESSION_LENGTH,
    MAXIMUM_SIGNAL_ID_LENGTH as MODEL_MAXIMUM_SIGNAL_ID_LENGTH,
    MAXIMUM_SYMBOL_LENGTH as MODEL_MAXIMUM_SYMBOL_LENGTH,
    MAXIMUM_TRADE_QUALITY_GRADE_LENGTH as MODEL_MAXIMUM_TRADE_QUALITY_GRADE_LENGTH,
    TradeHistory,
)
from app.services.learning_intelligence_integration import (
    register_completed_trade,
)
from app.services.confidence_guardrail_service import (
    MAXIMUM_CONFIDENCE_ADJUSTMENT,
    MINIMUM_COMPLETED_TRADES,
    MINIMUM_SIGNAL_CONFIDENCE,
)

logger = logging.getLogger(__name__)

VERSION_27_LEARNING_ENABLED: Final = True
VERSION_30_GUARDRAIL_ENABLED: Final = True
MALAYSIA_TIMEZONE: Final = timezone(
    timedelta(hours=8)
)

MAXIMUM_CONFIRMATIONS: Final = 100
MAXIMUM_SIGNAL_ID_LENGTH: Final = MODEL_MAXIMUM_SIGNAL_ID_LENGTH
MAXIMUM_SERIALIZED_TEXT_LENGTH: Final = 20_000
MAXIMUM_SYMBOL_LENGTH: Final = MODEL_MAXIMUM_SYMBOL_LENGTH
MAXIMUM_INTERVAL_LENGTH: Final = MODEL_MAXIMUM_INTERVAL_LENGTH
MAXIMUM_DIRECTION_LENGTH: Final = MODEL_MAXIMUM_DIRECTION_LENGTH
MAXIMUM_MARKET_SESSION_LENGTH: Final = MODEL_MAXIMUM_MARKET_SESSION_LENGTH
MAXIMUM_MARKET_CONDITION_LENGTH: Final = MODEL_MAXIMUM_MARKET_CONDITION_LENGTH
MAXIMUM_ENGINE_VERSION_LENGTH: Final = MODEL_MAXIMUM_ENGINE_VERSION_LENGTH
MAXIMUM_TRADE_QUALITY_GRADE_LENGTH: Final = MODEL_MAXIMUM_TRADE_QUALITY_GRADE_LENGTH
MAXIMUM_HISTORY_LIMIT: Final = 500
MAXIMUM_HISTORY_SKIP: Final = 1_000_000
MAXIMUM_ACTIVE_TRADES: Final = 10_000
DEFAULT_ENTRY_TOLERANCE: Final = 0.0005


def utc_now() -> datetime:
    """
    Returns the current UTC time.
    """

    return datetime.now(timezone.utc)


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
        MAXIMUM_CONFIRMATIONS,
    )



def safe_pagination_int(
    value: Any,
    default: int,
    *,
    minimum: int = 0,
    maximum: int,
) -> int:
    """Safely convert pagination values without the confirmation-count cap."""

    if isinstance(value, bool):
        return default

    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return default

    return min(
        max(
            number,
            minimum,
        ),
        maximum,
    )

def safe_bool(
    value: Any,
) -> bool:
    """Interpret only explicit truthy representations as True."""

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value == 1

    if isinstance(value, str):
        return value.strip().lower() in {
            "true",
            "1",
            "yes",
            "approved",
            "allowed",
        }

    return False


def normalize_public_text(
    value: Any,
    *,
    maximum_length: int,
) -> str:
    """Normalize bounded text used in public identifiers and labels."""

    normalized = str(
        value or ""
    ).strip()

    return normalized[
        :maximum_length
    ]


def normalize_signal_id(
    value: Any,
) -> str:
    """
    Validate one public signal identifier without silently truncating it.
    """

    resolved = str(
        value or ""
    ).strip()

    if not resolved:
        raise ValueError(
            "signal_id is required."
        )

    if len(
        resolved
    ) > MAXIMUM_SIGNAL_ID_LENGTH:
        raise ValueError(
            "signal_id exceeds the database maximum length."
        )

    if any(
        not character.isprintable()
        or character in {
            "\r",
            "\n",
            "\t",
        }
        for character in resolved
    ):
        raise ValueError(
            "signal_id contains unsupported characters."
        )

    return resolved


def generate_signal_id(
    symbol: str,
    interval: str,
    direction: str,
) -> str:
    """
    Generates a unique public signal ID.

    Example:
    BT-XAUUSD-1H-BUY-A12B34C5
    """

    safe_symbol = "".join(
        character
        for character in normalize_public_text(
            symbol,
            maximum_length=MAXIMUM_SYMBOL_LENGTH,
        ).upper()
        if character.isalnum()
    ) or "UNKNOWN"

    safe_interval = "".join(
        character
        for character in normalize_public_text(
            interval,
            maximum_length=MAXIMUM_INTERVAL_LENGTH,
        ).upper()
        if character.isalnum()
    ) or "UNKNOWN"

    safe_direction = "".join(
        character
        for character in normalize_public_text(
            direction,
            maximum_length=MAXIMUM_DIRECTION_LENGTH,
        ).upper()
        if character.isalnum()
    ) or "UNKNOWN"

    unique_code = uuid4().hex[:8].upper()

    generated = (
        f"BT-{safe_symbol}-"
        f"{safe_interval}-"
        f"{safe_direction}-"
        f"{unique_code}"
    )

    return normalize_signal_id(
        generated
    )


def serialize_text(value: Any) -> Optional[str]:
    """
    Converts lists, dictionaries, or other values into database-safe text.
    """

    if value is None:
        return None

    if isinstance(value, str):
        return value[
            :MAXIMUM_SERIALIZED_TEXT_LENGTH
        ]

    try:
        serialized = json.dumps(
            value,
            ensure_ascii=False,
            default=str,
        )
    except (TypeError, ValueError, OverflowError):
        serialized = str(value)

    return serialized[
        :MAXIMUM_SERIALIZED_TEXT_LENGTH
    ]


def normalize_direction(signal_value: Any) -> Optional[str]:
    """
    Converts different signal formats into BUY or SELL.
    """

    if signal_value is None:
        return None

    value = str(signal_value).strip().upper()

    if value in {"BUY", "BULLISH", "LONG"}:
        return "BUY"

    if value in {"SELL", "BEARISH", "SHORT"}:
        return "SELL"

    return None


def get_confirmation_information(
    signal_data: dict[str, Any],
    direction: str,
) -> tuple[int, list[str]]:
    """
    Reads confirmation count and details from the signal-engine response.
    """

    validation = signal_data.get(
        "validation"
    ) or {}

    if not isinstance(
        validation,
        dict,
    ):
        validation = {}

    if direction == "BUY":
        count = validation.get("buy_confirmations", 0)
        details = validation.get("buy_confirmation_details", [])
    else:
        count = validation.get("sell_confirmations", 0)
        details = validation.get("sell_confirmation_details", [])

    count = safe_int(
        count
    )

    if not isinstance(
        details,
        list,
    ):
        details = [
            str(details)
        ]

    normalized_details = [
        str(detail).strip()[:500]
        for detail in details[:MAXIMUM_CONFIRMATIONS]
        if str(detail).strip()
    ]

    return count, normalized_details



def normalize_learning_result(
    result: Any,
    profit_loss_points: Any = None,
) -> Optional[str]:
    """
    Convert a completed trade result into a learning result.

    CANCELLED trades are classified using their realised P/L:
    - Positive P/L: WIN
    - Negative P/L: LOSS
    - Zero P/L: BREAKEVEN
    """

    normalized = str(result or "").strip().upper()

    if normalized in {
        "TP1_HIT",
        "TP2_HIT",
        "WIN",
        "WON",
        "PROFIT",
    }:
        return "WIN"

    if normalized in {
        "STOP_LOSS",
        "STOP_LOSS_HIT",
        "LOSS",
        "LOST",
    }:
        return "LOSS"

    if normalized in {
        "BREAKEVEN",
        "BREAK_EVEN",
        "BREAK-EVEN",
        "BE",
    }:
        return "BREAKEVEN"

    if normalized == "CANCELLED":
        realised_points = safe_float(
            profit_loss_points,
            0.0,
        )

        if realised_points > 0:
            return "WIN"

        if realised_points < 0:
            return "LOSS"

        return "BREAKEVEN"

    return None


def determine_learning_session(closed_at: datetime) -> str:
    """
    Determine Asian, European, or US session using Malaysia time.
    """

    resolved = closed_at

    if resolved.tzinfo is None:
        resolved = resolved.replace(tzinfo=timezone.utc)

    hour = resolved.astimezone(MALAYSIA_TIMEZONE).hour

    if hour >= 20 or hour < 5:
        return "us"

    if 15 <= hour < 20:
        return "european"

    return "asian"


def calculate_planned_risk_reward(
    trade: TradeHistory,
) -> float:
    """
    Calculate original TP2 reward-to-risk ratio.
    """

    entry = safe_float(
        trade.entry_price,
        default=float("nan"),
    )
    stop_loss = safe_float(
        trade.stop_loss,
        default=float("nan"),
    )
    take_profit_2 = safe_float(
        trade.take_profit_2,
        default=float("nan"),
    )

    if not all(
        math.isfinite(value)
        for value in (
            entry,
            stop_loss,
            take_profit_2,
        )
    ):
        return 0.0

    risk = abs(
        entry - stop_loss
    )

    if risk <= 0:
        return 0.0

    reward = abs(take_profit_2 - entry)
    return round(max(reward / risk, 0.0), 4)


def extract_learning_market_condition(
    trade: TradeHistory,
) -> str:
    """
    Read the persisted market condition.
    """

    value = getattr(trade, "market_condition", None)

    if not value:
        return "unknown"

    return str(value).strip().lower().replace(" ", "_")


def register_trade_outcome_for_learning(
    db: Session,
    trade: TradeHistory,
) -> bool:
    """
    Register a newly closed trade with Version 27.

    Persistent database fields prevent duplicate learning across restarts.
    """

    if not VERSION_27_LEARNING_ENABLED:
        return False

    if bool(getattr(trade, "learning_registered", False)):
        return False

    trade_status = str(
        getattr(trade, "status", "") or ""
    ).upper()

    if trade_status not in {"CLOSED", "CANCELLED"}:
        return False

    learning_result = normalize_learning_result(
        getattr(trade, "result", None),
        getattr(trade, "profit_loss_points", 0.0),
    )

    if learning_result is None:
        return False

    closed_at = getattr(trade, "closed_at", None) or utc_now()
    opened_at = getattr(trade, "created_at", None) or closed_at

    market_session = (
        str(getattr(trade, "market_session", "") or "").strip().lower()
        or determine_learning_session(closed_at)
    )

    if market_session not in {"asian", "european", "us"}:
        market_session = determine_learning_session(closed_at)

    try:
        learning_response = register_completed_trade(
            {
                "symbol": str(trade.symbol).strip().upper(),
                "session": market_session,
                "market_condition": (
                    extract_learning_market_condition(trade)
                ),
                "direction": str(trade.direction).strip().upper(),
                "confidence": max(
                    0.0,
                    min(
                        100.0,
                        safe_float(
                            trade.confidence,
                            0.0,
                        ),
                    ),
                ),
                "risk_reward": calculate_planned_risk_reward(
                    trade
                ),
                "result": learning_result,
                "entry_price": safe_float(
                    trade.entry_price,
                    0.0,
                ),
                "stop_loss": safe_float(
                    trade.stop_loss,
                    0.0,
                ),
                "take_profit": safe_float(
                    trade.take_profit_2,
                    0.0,
                ),
                "opened_at": opened_at,
                "closed_at": closed_at,
            }
        )

        adjustment = 0.0

        if isinstance(learning_response, dict):
            adjustment = safe_float(
                learning_response.get(
                    "confidence_adjustment",
                    0.0,
                ),
                0.0,
            )

        trade.learning_registered = True
        trade.learning_registered_at = utc_now()
        trade.learning_result = learning_result
        trade.learning_confidence_adjustment = max(
            -MAXIMUM_CONFIDENCE_ADJUSTMENT,
            min(
                MAXIMUM_CONFIDENCE_ADJUSTMENT,
                adjustment,
            ),
        )
        trade.market_session = market_session

        db.commit()
        db.refresh(trade)

        logger.info(
            "Version 30 learning registered trade %s as %s.",
            trade.signal_id,
            learning_result,
        )

        return True

    except Exception:
        db.rollback()

        logger.exception(
            "Version 30 learning registration failed for %s.",
            getattr(trade, "signal_id", "unknown"),
        )

        return False


def get_trade_by_signal_id(
    db: Session,
    signal_id: str,
) -> Optional[TradeHistory]:
    """
    Finds one trade using its public signal ID.
    """

    try:
        normalized_signal_id = (
            normalize_signal_id(
                signal_id
            )
        )
    except ValueError:
        return None

    return (
        db.query(TradeHistory)
        .filter(
            TradeHistory.signal_id
            == normalized_signal_id
        )
        .first()
    )


def signal_exists(
    db: Session,
    symbol: str,
    interval: str,
    direction: str,
    entry_price: float,
    stop_loss: float,
    take_profit_1: float,
    take_profit_2: float,
    market_session: Optional[str] = None,
    market_condition: Optional[str] = None,
    entry_tolerance: float = 0.0005,
) -> bool:
    """
    Checks whether a similar active signal already exists.

    This prevents duplicate BUY or SELL signals from being saved
    repeatedly when the setup and risk levels are almost identical.
    """

    normalized_symbol = normalize_public_text(
        symbol,
        maximum_length=MAXIMUM_SYMBOL_LENGTH,
    ).upper()
    normalized_interval = normalize_public_text(
        interval,
        maximum_length=MAXIMUM_INTERVAL_LENGTH,
    ).lower()
    normalized_direction = normalize_direction(
        direction
    )

    if (
        not normalized_symbol
        or not normalized_interval
        or normalized_direction not in {"BUY", "SELL"}
    ):
        return False

    tolerance = safe_float(
        entry_tolerance,
        DEFAULT_ENTRY_TOLERANCE,
    )

    if tolerance < 0.0:
        tolerance = DEFAULT_ENTRY_TOLERANCE

    requested_levels = (
        safe_float(
            entry_price,
            default=float("nan"),
        ),
        safe_float(
            stop_loss,
            default=float("nan"),
        ),
        safe_float(
            take_profit_1,
            default=float("nan"),
        ),
        safe_float(
            take_profit_2,
            default=float("nan"),
        ),
    )

    if not all(
        math.isfinite(value)
        for value in requested_levels
    ):
        return False

    (
        requested_entry,
        requested_stop,
        requested_tp1,
        requested_tp2,
    ) = requested_levels

    existing_trades = (
        db.query(TradeHistory)
        .filter(
            TradeHistory.symbol == normalized_symbol,
            TradeHistory.interval == normalized_interval,
            TradeHistory.direction == normalized_direction,
            TradeHistory.status == "ACTIVE",
            TradeHistory.trade_allowed.is_(True),
        )
        .order_by(
            TradeHistory.created_at.desc()
        )
        .limit(MAXIMUM_ACTIVE_TRADES)
        .all()
    )

    normalized_session = (
        str(market_session or "").strip().lower()
        or None
    )
    normalized_condition = (
        str(market_condition or "")
        .strip()
        .lower()
        .replace(" ", "_")
        or None
    )

    for trade in existing_trades:
        if (
            trade.entry_price is None
            or trade.stop_loss is None
            or trade.take_profit_1 is None
            or trade.take_profit_2 is None
        ):
            continue

        stored_session = (
            str(
                getattr(trade, "market_session", None)
                or ""
            )
            .strip()
            .lower()
            or None
        )
        stored_condition = (
            str(
                getattr(trade, "market_condition", None)
                or ""
            )
            .strip()
            .lower()
            .replace(" ", "_")
            or None
        )

        if (
            normalized_session is not None
            and stored_session is not None
            and normalized_session != stored_session
        ):
            continue

        if (
            normalized_condition is not None
            and stored_condition is not None
            and normalized_condition != stored_condition
        ):
            continue

        stored_entry = safe_float(
            trade.entry_price,
            default=float("nan"),
        )
        stored_stop = safe_float(
            trade.stop_loss,
            default=float("nan"),
        )
        stored_tp1 = safe_float(
            trade.take_profit_1,
            default=float("nan"),
        )
        stored_tp2 = safe_float(
            trade.take_profit_2,
            default=float("nan"),
        )

        if not all(
            math.isfinite(value)
            for value in (
                stored_entry,
                stored_stop,
                stored_tp1,
                stored_tp2,
            )
        ):
            continue

        price_reference = max(
            abs(
                requested_entry
            ),
            abs(
                stored_entry
            ),
            1.0,
        )

        allowed_difference = (
            price_reference
            * tolerance
        )

        entry_is_similar = (
            abs(
                stored_entry
                - requested_entry
            )
            <= allowed_difference
        )

        stop_loss_is_similar = (
            abs(
                stored_stop
                - requested_stop
            )
            <= allowed_difference
        )

        tp1_is_similar = (
            abs(
                stored_tp1
                - requested_tp1
            )
            <= allowed_difference
        )

        tp2_is_similar = (
            abs(
                stored_tp2
                - requested_tp2
            )
            <= allowed_difference
        )

        if (
            entry_is_similar
            and stop_loss_is_similar
            and tp1_is_similar
            and tp2_is_similar
        ):
            return True

    return False


def save_approved_signal(
    db: Session,
    symbol: str,
    interval: str,
    signal_data: dict[str, Any],
) -> Optional[TradeHistory]:
    """
    Saves only approved BUY or SELL signals.

    NO TRADE and blocked signals will not be saved.
    """

    if not isinstance(
        signal_data,
        dict,
    ):
        raise ValueError(
            "signal_data must be a dictionary."
        )

    normalized_symbol = normalize_public_text(
        symbol,
        maximum_length=MAXIMUM_SYMBOL_LENGTH,
    ).upper()
    normalized_interval = normalize_public_text(
        interval,
        maximum_length=MAXIMUM_INTERVAL_LENGTH,
    ).lower()

    direction = normalize_direction(
        signal_data.get(
            "signal",
            signal_data.get(
                "direction",
                signal_data.get(
                    "final_decision"
                ),
            ),
        )
    )

    if not normalized_symbol or not normalized_interval:
        return None

    trade_allowed = safe_bool(
        signal_data.get(
            "trade_allowed",
            False,
        )
    )

    if direction not in {"BUY", "SELL"}:
        return None

    if not trade_allowed:
        return None

    entry_price = signal_data.get("entry_price")
    stop_loss = signal_data.get("stop_loss")
    take_profit_1 = signal_data.get("take_profit_1")
    take_profit_2 = signal_data.get("take_profit_2")

    required_levels = [
        entry_price,
        stop_loss,
        take_profit_1,
        take_profit_2,
    ]

    if any(
        level is None
        for level in required_levels
    ):
        return None

    numeric_levels = [
        safe_float(
            level,
            default=float("nan"),
        )
        for level in required_levels
    ]

    if not all(
        math.isfinite(level)
        and level > 0.0
        for level in numeric_levels
    ):
        return None

    (
        entry_price,
        stop_loss,
        take_profit_1,
        take_profit_2,
    ) = numeric_levels

    supplied_signal_id = signal_data.get("signal_id")

    signal_id = (
        normalize_signal_id(
            supplied_signal_id
        )
        if supplied_signal_id is not None
        else generate_signal_id(
            symbol=normalized_symbol,
            interval=normalized_interval,
            direction=direction,
        )
    )

    existing_trade = get_trade_by_signal_id(
        db=db,
        signal_id=signal_id,
    )

    if existing_trade:
        return existing_trade

    duplicate_exists = signal_exists(
        db=db,
        symbol=normalized_symbol,
        interval=normalized_interval,
        direction=direction,
        market_session=(
            str(signal_data.get("learning_session") or "")
            .strip()
            .lower()
            or None
        ),
        market_condition=(
            str(signal_data.get("learning_market_condition") or "")
            .strip()
            .lower()
            .replace(" ", "_")
            or None
        ),
        entry_price=float(entry_price),
        stop_loss=float(stop_loss),
        take_profit_1=float(take_profit_1),
        take_profit_2=float(take_profit_2),
    )

    if duplicate_exists:
        return None

    confirmation_count, confirmation_details = (
        get_confirmation_information(
            signal_data=signal_data,
            direction=direction,
        )
    )

    trade_quality = signal_data.get(
        "trade_quality"
    ) or {}

    if not isinstance(
        trade_quality,
        dict,
    ):
        trade_quality = {}

    market_price = signal_data.get(
        "market_price",
        entry_price,
    )

    new_trade = TradeHistory(
        signal_id=signal_id,
        symbol=normalized_symbol,
        interval=normalized_interval,
        direction=direction,
        entry_price=float(entry_price),
        stop_loss=float(stop_loss),
        take_profit_1=float(take_profit_1),
        take_profit_2=float(take_profit_2),
        confidence=max(
            0.0,
            min(
                100.0,
                safe_float(
                    signal_data.get(
                        "confidence",
                        0,
                    ),
                    0.0,
                ),
            ),
        ),
        directional_confidence=max(
            0.0,
            min(
                100.0,
                safe_float(
                    signal_data.get(
                        "directional_confidence",
                        0,
                    ),
                    0.0,
                ),
            ),
        ),
        confirmation_count=confirmation_count,
        trade_quality_score=max(
            0.0,
            min(
                100.0,
                safe_float(
                    trade_quality.get(
                        "score",
                        0,
                    ),
                    0.0,
                ),
            ),
        ),
        trade_quality_grade=normalize_public_text(
            trade_quality.get(
                "grade",
                "UNRATED",
            ),
            maximum_length=MAXIMUM_TRADE_QUALITY_GRADE_LENGTH,
        )
        or "UNRATED",
        status="ACTIVE",
        result="PENDING",
        trade_allowed=True,
        current_price=safe_float(
            market_price,
            entry_price,
        ),
        exit_price=None,
        tp1_hit=False,
        tp2_hit=False,
        stop_loss_hit=False,
        profit_loss_points=0.0,
        risk_reward_achieved=None,
        trade_duration_seconds=None,
        reason=serialize_text(signal_data.get("reason")),
        confirmation_details=serialize_text(
            confirmation_details
        ),
        engine_version=(
            normalize_public_text(
                signal_data.get(
                    "engine_version"
                ),
                maximum_length=MAXIMUM_ENGINE_VERSION_LENGTH,
            )
            or None
        ),
        market_session=(
            normalize_public_text(
                signal_data.get(
                    "learning_session",
                    signal_data.get(
                        "market_session",
                        "",
                    ),
                ),
                maximum_length=MAXIMUM_MARKET_SESSION_LENGTH,
            ).lower()
            or None
        ),
        market_condition=(
            normalize_public_text(
                signal_data.get(
                    "learning_market_condition",
                    signal_data.get(
                        "market_condition",
                        "",
                    ),
                ),
                maximum_length=MAXIMUM_MARKET_CONDITION_LENGTH,
            )
            .lower()
            .replace(" ", "_")
            or None
        ),
        learning_registered=False,
        learning_registered_at=None,
        learning_result=None,
        learning_confidence_adjustment=0.0,
        created_at=utc_now(),
        updated_at=utc_now(),
    )

    try:
        db.add(new_trade)
        db.commit()
        db.refresh(new_trade)
        return new_trade

    except IntegrityError:
        db.rollback()

        existing_trade = (
            get_trade_by_signal_id(
                db=db,
                signal_id=signal_id,
            )
        )

        if existing_trade is not None:
            return existing_trade

        raise

    except SQLAlchemyError:
        db.rollback()
        raise


def get_trade_history(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    symbol: Optional[str] = None,
    interval: Optional[str] = None,
    direction: Optional[str] = None,
    status: Optional[str] = None,
    result: Optional[str] = None,
) -> tuple[int, list[TradeHistory]]:
    """
    Returns filtered and paginated signal history.
    """

    safe_skip = safe_pagination_int(
        skip,
        0,
        minimum=0,
        maximum=MAXIMUM_HISTORY_SKIP,
    )
    safe_limit = safe_pagination_int(
        limit,
        100,
        minimum=1,
        maximum=MAXIMUM_HISTORY_LIMIT,
    )

    query = db.query(TradeHistory)

    if symbol:
        normalized_symbol = normalize_public_text(
            symbol,
            maximum_length=MAXIMUM_SYMBOL_LENGTH,
        ).upper()

        if normalized_symbol:
            query = query.filter(
                TradeHistory.symbol
                == normalized_symbol
            )

    if interval:
        normalized_interval = normalize_public_text(
            interval,
            maximum_length=MAXIMUM_INTERVAL_LENGTH,
        ).lower()

        if normalized_interval:
            query = query.filter(
                TradeHistory.interval
                == normalized_interval
            )

    if direction:
        normalized_direction = normalize_direction(direction)

        if normalized_direction:
            query = query.filter(
                TradeHistory.direction
                == normalized_direction
            )

    if status:
        query = query.filter(
            TradeHistory.status == status.upper()
        )

    if result:
        query = query.filter(
            TradeHistory.result == result.upper()
        )

    total = query.count()

    trades = (
        query.order_by(TradeHistory.created_at.desc())
        .offset(safe_skip)
        .limit(safe_limit)
        .all()
    )

    return total, trades


def get_active_trades(
    db: Session,
    symbol: Optional[str] = None,
) -> list[TradeHistory]:
    """
    Returns all active trades.

    A symbol filter can be supplied when updating one market.
    """

    query = db.query(TradeHistory).filter(
        TradeHistory.status == "ACTIVE"
    )

    if symbol:
        normalized_symbol = normalize_public_text(
            symbol,
            maximum_length=MAXIMUM_SYMBOL_LENGTH,
        ).upper()

        if normalized_symbol:
            query = query.filter(
                TradeHistory.symbol
                == normalized_symbol
            )

    return (
        query.order_by(
            TradeHistory.created_at.asc()
        )
        .limit(
            MAXIMUM_ACTIVE_TRADES
        )
        .all()
    )


def calculate_profit_loss_points(
    direction: str,
    entry_price: float,
    exit_price: float,
) -> float:
    """
    Calculates price-distance profit or loss.

    BUY:
        Exit - Entry

    SELL:
        Entry - Exit
    """

    normalized_direction = normalize_direction(
        direction
    )

    entry = safe_float(
        entry_price,
        default=float("nan"),
    )
    exit_value = safe_float(
        exit_price,
        default=float("nan"),
    )

    if not (
        math.isfinite(entry)
        and math.isfinite(exit_value)
    ):
        return 0.0

    if normalized_direction == "BUY":
        return round(
            exit_value - entry,
            8,
        )

    if normalized_direction == "SELL":
        return round(
            entry - exit_value,
            8,
        )

    return 0.0


def calculate_trade_duration(
    trade: TradeHistory,
    closed_time: datetime,
) -> Optional[int]:
    """
    Calculates total trade duration in seconds.
    """

    if not trade.created_at:
        return None

    created_at = trade.created_at
    resolved_closed_time = closed_time

    if created_at.tzinfo is None:
        created_at = created_at.replace(
            tzinfo=timezone.utc
        )
    else:
        created_at = created_at.astimezone(
            timezone.utc
        )

    if resolved_closed_time.tzinfo is None:
        resolved_closed_time = resolved_closed_time.replace(
            tzinfo=timezone.utc
        )
    else:
        resolved_closed_time = resolved_closed_time.astimezone(
            timezone.utc
        )

    return max(
        int(
            (
                resolved_closed_time
                - created_at
            ).total_seconds()
        ),
        0,
    )


def calculate_risk_reward_achieved(
    trade: TradeHistory,
    exit_price: float,
) -> Optional[float]:
    """
    Calculates achieved reward divided by original risk.
    """

    entry = safe_float(
        trade.entry_price,
        default=float("nan"),
    )
    stop = safe_float(
        trade.stop_loss,
        default=float("nan"),
    )

    if not (
        math.isfinite(entry)
        and math.isfinite(stop)
    ):
        return None

    original_risk = abs(
        entry - stop
    )

    if original_risk <= 0:
        return None

    achieved_points = calculate_profit_loss_points(
        direction=trade.direction,
        entry_price=trade.entry_price,
        exit_price=exit_price,
    )

    return round(
        achieved_points / original_risk,
        4,
    )


def close_trade(
    db: Session,
    trade: TradeHistory,
    exit_price: float,
    result: str,
) -> TradeHistory:
    """
    Closes a trade and stores its final outcome.
    """

    closed_time = utc_now()

    normalized_exit_price = safe_float(
        exit_price,
        default=float("nan"),
    )

    if (
        not math.isfinite(
            normalized_exit_price
        )
        or normalized_exit_price <= 0.0
    ):
        raise ValueError(
            "Exit price must be a positive finite number."
        )

    normalized_result = normalize_public_text(
        result,
        maximum_length=32,
    ).upper()

    if not normalized_result:
        raise ValueError(
            "Trade result is required."
        )

    trade.current_price = normalized_exit_price
    trade.exit_price = normalized_exit_price
    trade.status = "CLOSED"
    trade.result = normalized_result
    trade.profit_loss_points = (
        calculate_profit_loss_points(
            direction=trade.direction,
            entry_price=trade.entry_price,
            exit_price=normalized_exit_price,
        )
    )
    trade.risk_reward_achieved = (
        calculate_risk_reward_achieved(
            trade=trade,
            exit_price=normalized_exit_price,
        )
    )
    trade.trade_duration_seconds = (
        calculate_trade_duration(
            trade=trade,
            closed_time=closed_time,
        )
    )
    trade.closed_at = closed_time
    trade.updated_at = closed_time

    return trade


def update_single_trade_price(
    trade: TradeHistory,
    current_price: float,
) -> bool:
    """
    Updates one active trade using the latest market price.

    Returns True when the trade was modified.
    """

    if trade.status != "ACTIVE":
        return False

    price = safe_float(
        current_price,
        default=float("nan"),
    )

    if (
        not math.isfinite(price)
        or price <= 0.0
    ):
        raise ValueError(
            "Current price must be a positive finite number."
        )

    direction = normalize_direction(
        trade.direction
    )

    entry_price = safe_float(
        trade.entry_price,
        default=float("nan"),
    )
    stop_loss = safe_float(
        trade.stop_loss,
        default=float("nan"),
    )
    take_profit_1 = safe_float(
        trade.take_profit_1,
        default=float("nan"),
    )
    take_profit_2 = safe_float(
        trade.take_profit_2,
        default=float("nan"),
    )

    if not all(
        math.isfinite(value)
        and value > 0.0
        for value in (
            entry_price,
            stop_loss,
            take_profit_1,
            take_profit_2,
        )
    ):
        raise ValueError(
            "Active trade contains invalid risk levels."
        )

    trade.current_price = price
    trade.updated_at = utc_now()

    if direction == "BUY":

        if price <= stop_loss:
            trade.stop_loss_hit = True
            close_trade(
                db=None,
                trade=trade,
                exit_price=stop_loss,
                result="STOP_LOSS",
            )
            return True

        if (
            not trade.tp1_hit
            and price >= take_profit_1
        ):
            trade.tp1_hit = True
            trade.result = "TP1_HIT"

        if price >= take_profit_2:
            trade.tp1_hit = True
            trade.tp2_hit = True
            close_trade(
                db=None,
                trade=trade,
                exit_price=take_profit_2,
                result="TP2_HIT",
            )
            return True

    elif direction == "SELL":

        if price >= stop_loss:
            trade.stop_loss_hit = True
            close_trade(
                db=None,
                trade=trade,
                exit_price=stop_loss,
                result="STOP_LOSS",
            )
            return True

        if (
            not trade.tp1_hit
            and price <= take_profit_1
        ):
            trade.tp1_hit = True
            trade.result = "TP1_HIT"

        if price <= take_profit_2:
            trade.tp1_hit = True
            trade.tp2_hit = True
            close_trade(
                db=None,
                trade=trade,
                exit_price=take_profit_2,
                result="TP2_HIT",
            )
            return True

    elif direction is None:
        raise ValueError(
            "Active trade contains an invalid direction."
        )

    return True


def update_active_trades(
    db: Session,
    symbol: str,
    current_price: float,
) -> list[TradeHistory]:
    """
    Update active trades and register newly completed outcomes with V27.
    """

    active_trades = get_active_trades(
        db=db,
        symbol=symbol,
    )

    updated_trades: list[TradeHistory] = []
    newly_closed_trades: list[TradeHistory] = []

    try:
        for trade in active_trades:
            previous_status = str(trade.status or "").upper()

            changed = update_single_trade_price(
                trade=trade,
                current_price=current_price,
            )

            if changed:
                updated_trades.append(trade)

            if (
                previous_status != "CLOSED"
                and str(trade.status or "").upper() == "CLOSED"
            ):
                newly_closed_trades.append(trade)

        db.commit()

        for trade in updated_trades:
            db.refresh(trade)

        for trade in newly_closed_trades:
            register_trade_outcome_for_learning(
                db=db,
                trade=trade,
            )

        return updated_trades

    except Exception:
        db.rollback()
        raise


def cancel_trade(
    db: Session,
    signal_id: str,
    current_price: Optional[float] = None,
) -> Optional[TradeHistory]:
    """
    Cancels an active trade manually.
    """

    trade = get_trade_by_signal_id(
        db=db,
        signal_id=signal_id,
    )

    if not trade:
        return None

    if trade.status != "ACTIVE":
        return trade

    cancelled_time = utc_now()

    exit_price = safe_float(
        current_price
        if current_price is not None
        else (
            trade.current_price
            or trade.entry_price
        ),
        default=float("nan"),
    )

    if (
        not math.isfinite(exit_price)
        or exit_price <= 0.0
    ):
        raise ValueError(
            "Cancellation price must be a positive finite number."
        )

    trade.current_price = exit_price
    trade.exit_price = exit_price
    trade.status = "CANCELLED"
    trade.result = "CANCELLED"
    trade.profit_loss_points = (
        calculate_profit_loss_points(
            direction=trade.direction,
            entry_price=trade.entry_price,
            exit_price=exit_price,
        )
    )
    trade.trade_duration_seconds = (
        calculate_trade_duration(
            trade=trade,
            closed_time=cancelled_time,
        )
    )
    trade.closed_at = cancelled_time
    trade.updated_at = cancelled_time

    try:
        db.commit()
        db.refresh(trade)

        register_trade_outcome_for_learning(
            db=db,
            trade=trade,
        )

        return trade

    except Exception:
        db.rollback()
        raise



def _safe_count(
    value: Any,
) -> int:
    if isinstance(value, bool):
        return 0

    try:
        resolved = int(value)
    except (TypeError, ValueError, OverflowError):
        return 0

    return max(
        0,
        resolved,
    )

def get_trade_statistics(
    db: Session,
) -> dict[str, Any]:
    """
    Calculates dashboard-ready trade statistics.
    """

    total_trades = db.query(
        func.count(TradeHistory.id)
    ).scalar() or 0

    active_trades = (
        db.query(func.count(TradeHistory.id))
        .filter(TradeHistory.status == "ACTIVE")
        .scalar()
        or 0
    )

    closed_trades = (
        db.query(func.count(TradeHistory.id))
        .filter(TradeHistory.status == "CLOSED")
        .scalar()
        or 0
    )

    tp1_trades = (
        db.query(func.count(TradeHistory.id))
        .filter(TradeHistory.tp1_hit.is_(True))
        .scalar()
        or 0
    )

    tp2_trades = (
        db.query(func.count(TradeHistory.id))
        .filter(TradeHistory.tp2_hit.is_(True))
        .scalar()
        or 0
    )

    stop_loss_trades = (
        db.query(func.count(TradeHistory.id))
        .filter(TradeHistory.stop_loss_hit.is_(True))
        .scalar()
        or 0
    )

    winning_trades = tp1_trades

    losing_trades = stop_loss_trades

    pending_trades = (
        db.query(func.count(TradeHistory.id))
        .filter(TradeHistory.result == "PENDING")
        .scalar()
        or 0
    )

    completed_for_rate = (
        winning_trades + losing_trades
    )

    win_rate = (
        round(
            winning_trades
            / completed_for_rate
            * 100,
            2,
        )
        if completed_for_rate > 0
        else 0.0
    )

    loss_rate = (
        round(
            losing_trades
            / completed_for_rate
            * 100,
            2,
        )
        if completed_for_rate > 0
        else 0.0
    )

    average_confidence = db.query(
        func.avg(TradeHistory.confidence)
    ).scalar() or 0.0

    average_trade_quality = db.query(
        func.avg(TradeHistory.trade_quality_score)
    ).scalar() or 0.0

    total_profit_loss_points = db.query(
        func.sum(TradeHistory.profit_loss_points)
    ).scalar() or 0.0

    return {
        "total_trades": _safe_count(total_trades),
        "active_trades": _safe_count(active_trades),
        "closed_trades": _safe_count(closed_trades),
        "winning_trades": _safe_count(winning_trades),
        "losing_trades": _safe_count(losing_trades),
        "pending_trades": _safe_count(pending_trades),
        "tp1_trades": _safe_count(tp1_trades),
        "tp2_trades": _safe_count(tp2_trades),
        "stop_loss_trades": _safe_count(stop_loss_trades),
        "win_rate": float(win_rate),
        "loss_rate": float(loss_rate),
        "average_confidence": round(
            safe_float(
                average_confidence,
                0.0,
            ),
            2,
        ),
        "average_trade_quality": round(
            safe_float(
                average_trade_quality,
                0.0,
            ),
            2,
        ),
        "total_profit_loss_points": round(
            safe_float(
                total_profit_loss_points,
                0.0,
            ),
            8,
        ),
    }

def get_version_30_learning_status(
    db: Session,
) -> dict[str, Any]:
    """
    Return persistent Version 30 trade-learning status.
    """

    registered_count = (
        db.query(func.count(TradeHistory.id))
        .filter(TradeHistory.learning_registered.is_(True))
        .scalar()
        or 0
    )

    pending_learning_count = (
        db.query(func.count(TradeHistory.id))
        .filter(
            TradeHistory.status.in_([
                "CLOSED",
                "CANCELLED",
            ]),
            TradeHistory.learning_registered.is_(False),
        )
        .scalar()
        or 0
    )

    return {
        "version": 30,
        "completed_trade_learning_enabled": (
            VERSION_27_LEARNING_ENABLED
        ),
        "registered_trade_count": _safe_count(
            registered_count
        ),
        "pending_learning_count": _safe_count(
            pending_learning_count
        ),
        "session_timezone": "Asia/Kuala_Lumpur",
        "supported_sessions": [
            "asian",
            "european",
            "us",
        ],
        "timeframe_performance_learning_enabled": False,
        "confidence_guardrail_enabled": (
            VERSION_30_GUARDRAIL_ENABLED
        ),
        "minimum_completed_trades": (
            MINIMUM_COMPLETED_TRADES
        ),
        "maximum_confidence_adjustment": (
            MAXIMUM_CONFIDENCE_ADJUSTMENT
        ),
        "minimum_signal_confidence": (
            MINIMUM_SIGNAL_CONFIDENCE
        ),
        "cancelled_trade_learning_enabled": True,
        "analysis_only": True,
        "broker_connection_enabled": False,
        "trade_execution_enabled": False,
    }

# Backward-compatible Version 27 name.
get_version_27_learning_status = get_version_30_learning_status

__all__ = [
    "DEFAULT_ENTRY_TOLERANCE",
    "MALAYSIA_TIMEZONE",
    "MAXIMUM_CONFIRMATIONS",
    "MAXIMUM_ACTIVE_TRADES",
    "MAXIMUM_HISTORY_LIMIT",
    "MAXIMUM_HISTORY_SKIP",
    "MAXIMUM_SIGNAL_ID_LENGTH",
    "VERSION_27_LEARNING_ENABLED",
    "VERSION_30_GUARDRAIL_ENABLED",
    "calculate_planned_risk_reward",
    "calculate_profit_loss_points",
    "calculate_risk_reward_achieved",
    "calculate_trade_duration",
    "cancel_trade",
    "close_trade",
    "determine_learning_session",
    "extract_learning_market_condition",
    "generate_signal_id",
    "get_active_trades",
    "get_confirmation_information",
    "get_trade_by_signal_id",
    "get_trade_history",
    "get_trade_statistics",
    "get_version_27_learning_status",
    "get_version_30_learning_status",
    "normalize_direction",
    "normalize_learning_result",
    "normalize_signal_id",
    "register_trade_outcome_for_learning",
    "safe_bool",
    "safe_float",
    "safe_int",
    "safe_pagination_int",
    "save_approved_signal",
    "serialize_text",
    "signal_exists",
    "update_active_trades",
    "update_single_trade_price",
    "utc_now",
]