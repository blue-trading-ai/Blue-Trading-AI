"""
Blue-Trading-AI
Version 27
learning_intelligence_integration.py

Integration layer for the Version 27 Learning Intelligence engine.
This module does not execute trades or connect to a broker.
"""

from __future__ import annotations

import logging
import math
from dataclasses import asdict
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Dict, Final, Mapping, Optional

from app.services.learning_intelligence_service import (
    LearningIntelligenceService,
    LearningRecommendation,
    LearningTrade,
)


logger = logging.getLogger(__name__)

LEARNING_INTEGRATION_VERSION: Final[int] = 27
MAXIMUM_SYMBOL_LENGTH: Final[int] = 30
MAXIMUM_MARKET_CONDITION_LENGTH: Final[int] = 80
MAXIMUM_TRADE_HISTORY: Final[int] = 100_000
MAXIMUM_SIGNAL_KEYS: Final[int] = 500
MAXIMUM_STATISTICS_ENTRIES: Final[int] = 10_000
MAXIMUM_SESSION_STATISTICS_ENTRIES: Final[int] = 100

# Shared in-memory learning engine.
# Persistent learning should use the project's persistence/repository layer.
_learning_service = LearningIntelligenceService()
_learning_service_lock = RLock()


def get_learning_intelligence_service() -> LearningIntelligenceService:
    """Return the shared Version 27 learning service instance."""

    with _learning_service_lock:
        return _learning_service


def reset_learning_intelligence_service() -> LearningIntelligenceService:
    """
    Reset the in-memory learning engine.

    Intended for tests, controlled maintenance, or development only.
    """

    global _learning_service

    with _learning_service_lock:
        _learning_service = LearningIntelligenceService()
        return _learning_service


def _validate_service(
    service: Optional[LearningIntelligenceService],
) -> LearningIntelligenceService:
    engine = (
        service
        if service is not None
        else get_learning_intelligence_service()
    )

    if not isinstance(
        engine,
        LearningIntelligenceService,
    ):
        raise ValueError(
            "Learning Intelligence service is invalid."
        )

    return engine


def _normalize_symbol(value: Any) -> str:
    symbol = (
        str(value or "")
        .strip()
        .upper()
        .replace("/", "")
        .replace("-", "")
        .replace("_", "")
        .replace(" ", "")
        .replace(".", "")
    )

    if not symbol:
        raise ValueError(
            "symbol is required"
        )

    if len(symbol) > MAXIMUM_SYMBOL_LENGTH:
        raise ValueError(
            "symbol is too long"
        )

    if not symbol.isalnum():
        raise ValueError(
            "symbol contains unsupported characters"
        )

    return symbol


def _normalize_session(value: Any) -> str:
    raw = str(
        value or ""
    ).strip().lower()

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

    session = aliases.get(
        raw,
        raw,
    )

    if session not in {
        "asian",
        "european",
        "us",
    }:
        raise ValueError(
            "session must be asian, european, or us"
        )

    return session


def _normalize_market_condition(value: Any) -> str:
    condition = (
        str(value or "")
        .strip()
        .lower()
        .replace(" ", "_")
    )

    if not condition:
        condition = "unknown"

    if len(condition) > MAXIMUM_MARKET_CONDITION_LENGTH:
        raise ValueError(
            "market_condition is too long"
        )

    allowed_characters = set(
        "abcdefghijklmnopqrstuvwxyz0123456789_-"
    )

    if any(
        character not in allowed_characters
        for character in condition
    ):
        raise ValueError(
            "market_condition contains unsupported characters"
        )

    return condition


def _normalize_direction(value: Any) -> str:
    direction = str(
        value or ""
    ).strip().upper()

    aliases = {
        "LONG": "BUY",
        "BULLISH": "BUY",
        "SHORT": "SELL",
        "BEARISH": "SELL",
    }

    direction = aliases.get(
        direction,
        direction,
    )

    if direction not in {
        "BUY",
        "SELL",
    }:
        raise ValueError(
            "direction must be BUY or SELL"
        )

    return direction


def _normalize_result(value: Any) -> str:
    result = str(
        value or ""
    ).strip().upper()

    aliases = {
        "WON": "WIN",
        "PROFIT": "WIN",
        "PROFITABLE": "WIN",
        "SUCCESS": "WIN",
        "TP": "WIN",
        "TAKE_PROFIT": "WIN",
        "LOST": "LOSS",
        "FAIL": "LOSS",
        "FAILED": "LOSS",
        "SL": "LOSS",
        "STOP_LOSS": "LOSS",
        "BE": "BREAKEVEN",
        "BREAK_EVEN": "BREAKEVEN",
        "BREAK-EVEN": "BREAKEVEN",
        "DRAW": "BREAKEVEN",
        "FLAT": "BREAKEVEN",
    }

    result = aliases.get(
        result,
        result,
    )

    if result not in {
        "WIN",
        "LOSS",
        "BREAKEVEN",
    }:
        raise ValueError(
            "result must be WIN, LOSS, or BREAKEVEN"
        )

    return result


def _to_float(
    value: Any,
    field_name: str,
    *,
    minimum: Optional[float] = None,
    maximum: Optional[float] = None,
) -> float:
    try:
        parsed = float(
            value
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ) as exc:
        raise ValueError(
            f"{field_name} must be a valid number"
        ) from exc

    if not math.isfinite(
        parsed
    ):
        raise ValueError(
            f"{field_name} must be a finite number"
        )

    if (
        minimum is not None
        and parsed < minimum
    ):
        raise ValueError(
            f"{field_name} must be at least {minimum}"
        )

    if (
        maximum is not None
        and parsed > maximum
    ):
        raise ValueError(
            f"{field_name} must be at most {maximum}"
        )

    return parsed


def _to_datetime(
    value: Any,
    field_name: str,
) -> datetime:
    if isinstance(
        value,
        datetime,
    ):
        resolved = value

    elif isinstance(
        value,
        str,
    ):
        cleaned = value.strip()

        if not cleaned:
            raise ValueError(
                f"{field_name} is required"
            )

        if cleaned.endswith(
            "Z"
        ):
            cleaned = (
                cleaned[:-1]
                + "+00:00"
            )

        try:
            resolved = datetime.fromisoformat(
                cleaned
            )
        except (
            TypeError,
            ValueError,
            OverflowError,
        ) as exc:
            raise ValueError(
                f"{field_name} must be a valid ISO-8601 datetime"
            ) from exc

    else:
        raise ValueError(
            f"{field_name} must be a datetime or ISO-8601 string"
        )

    if resolved.tzinfo is None:
        resolved = resolved.replace(
            tzinfo=timezone.utc
        )
    else:
        resolved = resolved.astimezone(
            timezone.utc
        )

    return resolved


def _bounded_confidence(
    value: Any,
) -> float:
    return max(
        0.0,
        min(
            100.0,
            _to_float(
                value,
                "confidence",
            ),
        ),
    )


def _safe_positive_int(
    value: Any,
    *,
    default: int,
    maximum: int = 1_000_000,
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
        1,
        min(
            resolved,
            maximum,
        ),
    )


def _recommendation_to_dict(
    recommendation: LearningRecommendation,
) -> Dict[str, Any]:
    if not isinstance(
        recommendation,
        LearningRecommendation,
    ):
        raise ValueError(
            "Learning recommendation returned an invalid type."
        )

    payload = asdict(
        recommendation
    )

    if not isinstance(
        payload,
        dict,
    ):
        raise ValueError(
            "Learning recommendation returned an invalid payload."
        )

    return payload


def _trade_history_count(
    engine: LearningIntelligenceService,
) -> int:
    trade_history = getattr(
        engine,
        "trade_history",
        [],
    )

    if not isinstance(
        trade_history,
        list,
    ):
        return 0

    return len(
        trade_history
    )


def register_completed_trade(
    trade_data: Mapping[str, Any],
    *,
    service: Optional[LearningIntelligenceService] = None,
) -> Dict[str, Any]:
    """
    Validate and register one completed trade in the learning engine.
    """

    if not isinstance(
        trade_data,
        Mapping,
    ):
        raise ValueError(
            "trade_data must be a mapping"
        )

    if len(
        trade_data
    ) > MAXIMUM_SIGNAL_KEYS:
        raise ValueError(
            "trade_data contains too many fields"
        )

    engine = _validate_service(
        service
    )

    if _trade_history_count(
        engine
    ) >= MAXIMUM_TRADE_HISTORY:
        raise ValueError(
            "Maximum in-memory learning trade history reached."
        )

    opened_at = _to_datetime(
        trade_data.get(
            "opened_at"
        ),
        "opened_at",
    )
    closed_at = _to_datetime(
        trade_data.get(
            "closed_at"
        ),
        "closed_at",
    )

    if closed_at < opened_at:
        raise ValueError(
            "closed_at cannot be earlier than opened_at"
        )

    trade = LearningTrade(
        symbol=_normalize_symbol(
            trade_data.get(
                "symbol"
            )
        ),
        session=_normalize_session(
            trade_data.get(
                "session"
            )
        ),
        market_condition=_normalize_market_condition(
            trade_data.get(
                "market_condition"
            )
        ),
        direction=_normalize_direction(
            trade_data.get(
                "direction"
            )
        ),
        confidence=_bounded_confidence(
            trade_data.get(
                "confidence"
            )
        ),
        risk_reward=_to_float(
            trade_data.get(
                "risk_reward"
            ),
            "risk_reward",
            minimum=0.0,
            maximum=100.0,
        ),
        result=_normalize_result(
            trade_data.get(
                "result"
            )
        ),
        entry_price=_to_float(
            trade_data.get(
                "entry_price"
            ),
            "entry_price",
            minimum=0.0,
        ),
        stop_loss=_to_float(
            trade_data.get(
                "stop_loss"
            ),
            "stop_loss",
            minimum=0.0,
        ),
        take_profit=_to_float(
            trade_data.get(
                "take_profit"
            ),
            "take_profit",
            minimum=0.0,
        ),
        opened_at=opened_at,
        closed_at=closed_at,
    )

    engine.add_completed_trade(
        trade
    )

    total_learning_trades = (
        _trade_history_count(
            engine
        )
    )

    if (
        total_learning_trades
        > MAXIMUM_TRADE_HISTORY
    ):
        logger.error(
            "Learning trade history exceeded configured safety cap."
        )
        raise RuntimeError(
            "Learning trade history exceeded its safety limit."
        )

    logger.info(
        "Version 27 completed trade registered: %s %s %s",
        trade.symbol,
        trade.direction,
        trade.result,
    )

    return {
        "status": "registered",
        "version": LEARNING_INTEGRATION_VERSION,
        "trade": asdict(
            trade
        ),
        "total_learning_trades": (
            total_learning_trades
        ),
        "analysis_only": True,
        "broker_connection_enabled": False,
        "trade_execution_enabled": False,
    }


def evaluate_learning_intelligence(
    *,
    symbol: str,
    session: str,
    market_condition: str,
    direction: str,
    current_confidence: float,
    service: Optional[LearningIntelligenceService] = None,
) -> Dict[str, Any]:
    """
    Evaluate historical learning and return an adjusted confidence.

    The confidence adjustment is controlled by Version 27 and this function
    never executes a trade.
    """

    engine = _validate_service(
        service
    )

    normalized_symbol = _normalize_symbol(
        symbol
    )
    normalized_session = _normalize_session(
        session
    )
    normalized_condition = _normalize_market_condition(
        market_condition
    )
    normalized_direction = _normalize_direction(
        direction
    )
    base_confidence = _bounded_confidence(
        current_confidence
    )

    recommendation = engine.evaluate_learning(
        symbol=normalized_symbol,
        session=normalized_session,
        market_condition=normalized_condition,
        direction=normalized_direction,
    )

    recommendation_payload = (
        _recommendation_to_dict(
            recommendation
        )
    )

    maximum_adjustment = _safe_positive_int(
        getattr(
            engine,
            "MAX_ADJUSTMENT",
            4,
        ),
        default=4,
        maximum=100,
    )

    try:
        raw_adjustment = int(
            recommendation.confidence_adjustment
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ) as exc:
        raise ValueError(
            "Learning recommendation contains an invalid confidence adjustment."
        ) from exc

    bounded_adjustment = max(
        -maximum_adjustment,
        min(
            maximum_adjustment,
            raw_adjustment,
        ),
    )

    adjusted_confidence = max(
        0.0,
        min(
            100.0,
            base_confidence
            + bounded_adjustment,
        ),
    )

    return {
        "version": LEARNING_INTEGRATION_VERSION,
        "engine": "AI Self-Learning Intelligence",
        "analysis_only": True,
        "broker_connection_enabled": False,
        "trade_execution_enabled": False,
        "symbol": normalized_symbol,
        "session": normalized_session,
        "market_condition": normalized_condition,
        "direction": normalized_direction,
        "base_confidence": round(
            base_confidence,
            2,
        ),
        "confidence_adjustment": (
            bounded_adjustment
        ),
        "adjusted_confidence": round(
            adjusted_confidence,
            2,
        ),
        "recommendation": (
            recommendation_payload
        ),
    }


def integrate_learning_intelligence(
    signal: Mapping[str, Any],
    *,
    session: str,
    market_condition: str,
    service: Optional[LearningIntelligenceService] = None,
) -> Dict[str, Any]:
    """
    Apply Version 27 learning intelligence to an existing signal payload.

    The original mapping is copied and never modified in place.
    """

    if not isinstance(
        signal,
        Mapping,
    ):
        raise ValueError(
            "signal must be a mapping"
        )

    if len(
        signal
    ) > MAXIMUM_SIGNAL_KEYS:
        raise ValueError(
            "signal contains too many top-level fields"
        )

    direction = signal.get(
        "direction",
        signal.get(
            "signal"
        ),
    )

    confidence_value = signal.get(
        "confidence",
        signal.get(
            "confidence_score",
            signal.get(
                "final_confidence",
                0.0,
            ),
        ),
    )

    learning_result = evaluate_learning_intelligence(
        symbol=str(
            signal.get(
                "symbol",
                ""
            )
        ),
        session=session,
        market_condition=market_condition,
        direction=str(
            direction or ""
        ),
        current_confidence=confidence_value,
        service=service,
    )

    integrated_signal = dict(
        signal
    )

    integrated_signal[
        "confidence_before_learning"
    ] = learning_result[
        "base_confidence"
    ]
    integrated_signal[
        "confidence"
    ] = learning_result[
        "adjusted_confidence"
    ]
    integrated_signal[
        "confidence_score"
    ] = learning_result[
        "adjusted_confidence"
    ]
    integrated_signal[
        "learning_intelligence"
    ] = learning_result
    integrated_signal[
        "learning_intelligence_applied"
    ] = True
    integrated_signal[
        "learning_intelligence_version"
    ] = LEARNING_INTEGRATION_VERSION
    integrated_signal[
        "analysis_only"
    ] = True
    integrated_signal[
        "broker_connection_enabled"
    ] = False
    integrated_signal[
        "trade_execution_enabled"
    ] = False

    return integrated_signal


def _serialise_statistics(
    statistics: Mapping[str, Any],
    *,
    key_limit: int,
    key_length: int,
) -> Dict[str, Any]:
    result: Dict[
        str,
        Any,
    ] = {}

    for key, value in list(
        statistics.items()
    )[:key_limit]:
        if not hasattr(
            value,
            "__dataclass_fields__",
        ):
            continue

        try:
            payload = asdict(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            continue

        result[
            str(
                key
            )[:key_length]
        ] = payload

    return result


def get_learning_summary(
    *,
    service: Optional[LearningIntelligenceService] = None,
) -> Dict[str, Any]:
    """Return a serializable summary of the Version 27 learning state."""

    engine = _validate_service(
        service
    )

    symbol_statistics = getattr(
        engine,
        "symbol_statistics",
        {},
    )
    session_statistics = getattr(
        engine,
        "session_statistics",
        {},
    )
    market_statistics = getattr(
        engine,
        "market_statistics",
        {},
    )

    if not isinstance(
        symbol_statistics,
        Mapping,
    ):
        symbol_statistics = {}

    if not isinstance(
        session_statistics,
        Mapping,
    ):
        session_statistics = {}

    if not isinstance(
        market_statistics,
        Mapping,
    ):
        market_statistics = {}

    minimum_trades = _safe_positive_int(
        getattr(
            engine,
            "MINIMUM_TRADES",
            20,
        ),
        default=20,
        maximum=MAXIMUM_TRADE_HISTORY,
    )
    maximum_adjustment = _safe_positive_int(
        getattr(
            engine,
            "MAX_ADJUSTMENT",
            4,
        ),
        default=4,
        maximum=100,
    )

    total_completed_trades = min(
        _trade_history_count(
            engine
        ),
        MAXIMUM_TRADE_HISTORY,
    )

    return {
        "version": LEARNING_INTEGRATION_VERSION,
        "analysis_only": True,
        "broker_connection_enabled": False,
        "trade_execution_enabled": False,
        "minimum_trades": minimum_trades,
        "maximum_confidence_adjustment": (
            maximum_adjustment
        ),
        "total_completed_trades": (
            total_completed_trades
        ),
        "symbols": _serialise_statistics(
            symbol_statistics,
            key_limit=MAXIMUM_STATISTICS_ENTRIES,
            key_length=MAXIMUM_SYMBOL_LENGTH,
        ),
        "sessions": _serialise_statistics(
            session_statistics,
            key_limit=MAXIMUM_SESSION_STATISTICS_ENTRIES,
            key_length=32,
        ),
        "market_conditions": _serialise_statistics(
            market_statistics,
            key_limit=MAXIMUM_STATISTICS_ENTRIES,
            key_length=MAXIMUM_MARKET_CONDITION_LENGTH,
        ),
    }


__all__ = [
    "LEARNING_INTEGRATION_VERSION",
    "MAXIMUM_MARKET_CONDITION_LENGTH",
    "MAXIMUM_SIGNAL_KEYS",
    "MAXIMUM_SYMBOL_LENGTH",
    "MAXIMUM_TRADE_HISTORY",
    "evaluate_learning_intelligence",
    "get_learning_intelligence_service",
    "get_learning_summary",
    "integrate_learning_intelligence",
    "register_completed_trade",
    "reset_learning_intelligence_service",
]