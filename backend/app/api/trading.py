"""
Blue-Trading-AI
Version 30 - Trading API

Purpose:
- Retrieve live market data.
- Update active trade records.
- Generate the existing AI trading signal.
- Apply Version 25 Market Regime Intelligence.
- Apply Version 26 Symbol Win Rate Intelligence.
- Apply Version 27 AI Self-Learning Intelligence.
- Apply Version 30 Confidence Guardrail Intelligence.
- Save only approved BUY or SELL signals with complete risk levels.
- Keep the platform analysis-only with no broker execution.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, Final, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, require_approved_user
from app.market.provider import get_market_data
from app.services.confidence_guardrail_integration import (
    apply_complete_confidence_guardrail,
)
from app.services.learning_intelligence_integration import (
    integrate_learning_intelligence,
)
from app.services.market_regime_integration import (
    integrate_market_regime_into_signal,
)
from app.services.symbol_winrate_integration import (
    evaluate_symbol_winrate,
)
from app.services.trade_history_service import (
    save_approved_signal,
    update_active_trades,
)
from app.trading.signal_engine import generate_signal


logger = logging.getLogger(__name__)

PROJECT_NAME: Final = "Blue-Trading-AI"
SAFETY_VERSION: Final[int] = 30
API_VERSION: Final = "30.0.0"

MINIMUM_CONFIDENCE: Final[float] = 80.0
MINIMUM_CONFIRMATIONS: Final[int] = 3
MAXIMUM_SYMBOL_LENGTH: Final[int] = 40
MAXIMUM_INTERVAL_LENGTH: Final[int] = 20
MAXIMUM_TRACKING_UPDATES: Final[int] = 500

PRIMARY_ANALYSIS_INTERVAL: Final = "1h"
AUTOMATIC_ANALYSIS_TIMEFRAMES: Final[tuple[str, ...]] = (
    "5min",
    "15min",
    "30min",
    "1h",
    "4h",
    "1day",
)

BROKER_CONNECTION_ENABLED: Final[bool] = False
TRADE_EXECUTION_ENABLED: Final[bool] = False
AUTOMATIC_ORDER_PLACEMENT_ENABLED: Final[bool] = False


router = APIRouter(
    prefix="/trading",
    tags=["Trading AI - Version 30"],
)


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """Convert a value into a finite float without crashing the route."""

    try:
        resolved = float(
            value
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        resolved = float(
            default
        )

    if not math.isfinite(
        resolved
    ):
        try:
            fallback = float(
                default
            )
        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            fallback = 0.0

        return (
            fallback
            if math.isfinite(
                fallback
            )
            else 0.0
        )

    return resolved


def _normalise_interval(
    interval: str,
) -> str:
    """Return a bounded provider interval while preserving provider format."""

    cleaned = str(
        interval or "1h"
    ).strip()

    if not cleaned:
        return "1h"

    if len(
        cleaned
    ) > MAXIMUM_INTERVAL_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Interval is too long.",
        )

    allowed = set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
    )

    if any(
        character not in allowed
        for character in cleaned
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Interval contains unsupported characters.",
        )

    return cleaned


def _normalise_symbol(
    symbol: str,
) -> str:
    """Return a clean uppercase market symbol."""

    cleaned = str(
        symbol or ""
    ).strip().upper()

    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Symbol is required.",
        )

    if len(
        cleaned
    ) > MAXIMUM_SYMBOL_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Symbol is too long.",
        )

    allowed = set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/"
    )

    if any(
        character not in allowed
        for character in cleaned
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Symbol contains unsupported characters.",
        )

    return cleaned


def _require_signal_dict(
    value: Any,
    *,
    stage: str,
) -> Dict[str, Any]:
    if isinstance(
        value,
        dict,
    ):
        return value

    logger.error(
        "Trading intelligence stage returned an invalid response.",
        extra={
            "stage": stage,
            "result_type": type(
                value
            ).__name__,
        },
    )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Trading intelligence pipeline returned an invalid response.",
    )


def _extract_signal_direction(
    signal: Dict[str, Any],
) -> str:
    """Extract BUY or SELL direction from a signal payload."""

    direction = str(
        signal.get(
            "direction",
            signal.get(
                "signal",
                signal.get(
                    "final_decision",
                    "WAIT",
                ),
            ),
        )
        or "WAIT"
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
        return "WAIT"

    return direction


def _extract_signal_confidence(
    signal: Dict[str, Any],
) -> float:
    """Extract the best available finite confidence value from a signal."""

    for field in (
        "confidence",
        "final_confidence",
        "dynamic_confidence",
        "confidence_score",
    ):
        if field in signal:
            return max(
                0.0,
                min(
                    100.0,
                    _safe_float(
                        signal.get(
                            field
                        )
                    ),
                ),
            )

    return 0.0


def _extract_market_condition(
    signal: Dict[str, Any],
) -> str:
    """
    Extract one normalized scalar market condition for Version 27 learning.

    Complex dictionaries/lists are deliberately ignored so learning
    categories cannot be polluted by stringified analysis payloads.
    """

    possible_sources = (
        signal.get(
            "market_regime"
        ),
        signal.get(
            "market_regime_intelligence"
        ),
        signal.get(
            "regime"
        ),
        signal,
    )

    for source in possible_sources:
        if not isinstance(
            source,
            dict,
        ):
            continue

        for field in (
            "market_condition",
            "primary_regime",
            "regime_type",
            "regime",
            "condition",
        ):
            value = source.get(
                field
            )

            if not isinstance(
                value,
                str,
            ):
                continue

            normalized = (
                value.strip()
                .lower()
                .replace(
                    " ",
                    "_",
                )
            )

            if normalized:
                return normalized[
                    :100
                ]

    return "unknown"


def _extract_market_session(
    signal: Dict[str, Any],
) -> str:
    """
    Extract one normalized market session for Version 27 learning.

    Session analysis is preferred over compatibility fields. Unknown or
    off-session values are preserved instead of being mislabeled as Asian.
    """

    possible_sources = (
        signal.get(
            "session_analysis"
        ),
        signal.get(
            "market_session"
        ),
        signal.get(
            "session_intelligence"
        ),
        signal.get(
            "session"
        ),
        signal,
    )

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
        "off_session": "off_session",
        "off session": "off_session",
    }

    for source in possible_sources:
        if isinstance(
            source,
            str,
        ):
            raw = source.strip().lower()
            session = aliases.get(
                raw
            )

            if session:
                return session

            continue

        if not isinstance(
            source,
            dict,
        ):
            continue

        for field in (
            "current_session",
            "primary_session",
            "active_session",
            "session",
            "market_session",
        ):
            value = source.get(
                field
            )

            if not isinstance(
                value,
                str,
            ):
                continue

            raw = value.strip().lower()
            session = aliases.get(
                raw
            )

            if session:
                return session

    return "unknown"


def _extract_market_payload(
    market_data: Dict[str, Any],
) -> tuple[
    List[Any],
    List[Dict[str, Any]],
    float,
]:
    """Validate and extract prices, candles, and the current price."""

    prices = market_data.get(
        "prices",
        [],
    )
    candles = market_data.get(
        "candles",
        [],
    )
    current_price = market_data.get(
        "current_price"
    )

    if not isinstance(
        prices,
        list,
    ) or not prices:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No price data available.",
        )

    if not isinstance(
        candles,
        list,
    ) or not candles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No OHLC candle data available.",
        )

    if not all(
        isinstance(
            candle,
            dict,
        )
        for candle in candles
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OHLC candle data.",
        )

    if current_price is None:
        current_price = prices[
            -1
        ]

    current_price_float = _safe_float(
        current_price,
        default=float(
            "nan"
        ),
    )

    if (
        not math.isfinite(
            current_price_float
        )
        or current_price_float <= 0.0
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid current market price.",
        )

    return (
        prices,
        candles,
        current_price_float,
    )


def _build_tracking_updates(
    updated_trades: List[Any],
) -> List[
    Dict[str, Any]
]:
    """Convert updated SQLAlchemy trade records into API-safe dictionaries."""

    if not isinstance(
        updated_trades,
        list,
    ):
        return []

    result: List[
        Dict[str, Any]
    ] = []

    for trade in updated_trades[
        :MAXIMUM_TRACKING_UPDATES
    ]:
        if trade is None:
            continue

        result.append(
            {
                "signal_id": getattr(
                    trade,
                    "signal_id",
                    None,
                ),
                "direction": getattr(
                    trade,
                    "direction",
                    None,
                ),
                "status": getattr(
                    trade,
                    "status",
                    None,
                ),
                "result": getattr(
                    trade,
                    "result",
                    None,
                ),
                "current_price": getattr(
                    trade,
                    "current_price",
                    None,
                ),
                "tp1_hit": bool(
                    getattr(
                        trade,
                        "tp1_hit",
                        False,
                    )
                ),
                "tp2_hit": bool(
                    getattr(
                        trade,
                        "tp2_hit",
                        False,
                    )
                ),
                "stop_loss_hit": bool(
                    getattr(
                        trade,
                        "stop_loss_hit",
                        False,
                    )
                ),
            }
        )

    return result


@router.get("/")
def trading_home() -> Dict[
    str,
    Any,
]:
    return {
        "status": "success",
        "project": PROJECT_NAME,
        "module": "Trading AI API",
        "version": API_VERSION,
        "safety_version": SAFETY_VERSION,
        "market_regime_intelligence": "enabled",
        "symbol_winrate_intelligence": "enabled",
        "learning_intelligence": "enabled",
        "confidence_guardrail": "enabled",
        "session_performance_learning": "enabled",
        "timeframe_performance_learning": "disabled",
        "signal_history": "enabled",
        "signal_generation_method": "POST",
        "signal_generation_requires_approved_user": True,
        "analysis_mode": "MULTI_TIMEFRAME",
        "automatic_timeframes": list(AUTOMATIC_ANALYSIS_TIMEFRAMES),
        "primary_analysis_interval": PRIMARY_ANALYSIS_INTERVAL,
        "user_selects_timeframe": False,
        "analysis_only": True,
        "broker_connection_enabled": (
            BROKER_CONNECTION_ENABLED
        ),
        "trade_execution_enabled": (
            TRADE_EXECUTION_ENABLED
        ),
    }


@router.get("/test")
def trading_test() -> Dict[
    str,
    Any,
]:
    return {
        "status": "success",
        "message": "Trading AI API is working",
        "project": PROJECT_NAME,
        "version": API_VERSION,
        "safety_version": SAFETY_VERSION,
        "market_regime_intelligence": "enabled",
        "symbol_winrate_intelligence": "enabled",
        "learning_intelligence": "enabled",
        "confidence_guardrail": "enabled",
        "session_performance_learning": "enabled",
        "timeframe_performance_learning": "disabled",
        "signal_history": "enabled",
        "signal_generation_method": "POST",
        "signal_generation_requires_approved_user": True,
        "analysis_mode": "MULTI_TIMEFRAME",
        "automatic_timeframes": list(AUTOMATIC_ANALYSIS_TIMEFRAMES),
        "primary_analysis_interval": PRIMARY_ANALYSIS_INTERVAL,
        "user_selects_timeframe": False,
        "analysis_only": True,
    }


@router.post("/signal/{symbol:path}")
def trading_signal(
    symbol: str,
    force_refresh: bool = Query(
        default=False,
        description=(
            "Reserved for the managed market-data pipeline. "
            "The current provider call remains backward compatible."
        ),
    ),
    _current_user: Any = Depends(
        require_approved_user
    ),
    db: Session = Depends(
        get_db
    ),
) -> Dict[
    str,
    Any,
]:
    """
    Generate a Version 30 guardrail-protected multi-timeframe signal.

    The user selects only the market symbol. Blue-Trading-AI automatically
    analyzes M5, M15, M30, H1, H4 and D1 internally. H1 remains the primary
    candle set for the base signal while the signal engine performs the full
    weighted multi-timeframe confirmation.

    This operation is POST-only because it can update active trade records
    and persist an approved signal. Approved authentication is required.
    """

    resolved_symbol = _normalise_symbol(
        symbol
    )
    resolved_interval = PRIMARY_ANALYSIS_INTERVAL

    try:
        market_data = get_market_data(
            symbol=resolved_symbol,
            interval=resolved_interval,
        )

        if not isinstance(
            market_data,
            dict,
        ):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Invalid market data response.",
            )

        if market_data.get(
            "error"
        ):
            logger.warning(
                "Market-data provider returned an error.",
                extra={
                    "symbol": resolved_symbol,
                    "interval": resolved_interval,
                },
            )

            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Market data is currently unavailable.",
            )

        prices, candles, current_price = (
            _extract_market_payload(
                market_data
            )
        )

        updated_trades = update_active_trades(
            db=db,
            symbol=resolved_symbol,
            current_price=current_price,
        )

        if not isinstance(
            updated_trades,
            list,
        ):
            logger.warning(
                "Active-trade update service returned a non-list response.",
                extra={
                    "symbol": resolved_symbol,
                    "result_type": type(
                        updated_trades
                    ).__name__,
                },
            )

            updated_trades = []

        base_signal = _require_signal_dict(
            generate_signal(
                symbol=resolved_symbol,
                prices=prices,
                candles=candles,
            ),
            stage="base_signal",
        )

        if base_signal.get(
            "error"
        ):
            logger.warning(
                "Base signal engine rejected market input.",
                extra={
                    "symbol": resolved_symbol,
                    "interval": resolved_interval,
                },
            )

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Trading signal could not be generated from the supplied market data.",
            )

        signal = _require_signal_dict(
            integrate_market_regime_into_signal(
                signal_result=base_signal,
                candles=candles,
                symbol=resolved_symbol,
                timeframe=resolved_interval,
            ),
            stage="market_regime",
        )

        signal_for_symbol_winrate = dict(
            signal
        )
        signal_for_symbol_winrate[
            "symbol"
        ] = resolved_symbol
        signal_for_symbol_winrate[
            "confidence"
        ] = _extract_signal_confidence(
            signal
        )

        signal = _require_signal_dict(
            evaluate_symbol_winrate(
                signal=signal_for_symbol_winrate,
            ),
            stage="symbol_winrate",
        )

        signal_direction = (
            _extract_signal_direction(
                signal
            )
        )
        signal_confidence = (
            _extract_signal_confidence(
                signal
            )
        )
        market_condition = (
            _extract_market_condition(
                signal
            )
        )
        market_session = (
            _extract_market_session(
                signal
            )
        )

        if signal_direction in {
            "BUY",
            "SELL",
        }:
            signal_for_learning = dict(
                signal
            )
            signal_for_learning[
                "symbol"
            ] = resolved_symbol
            signal_for_learning[
                "direction"
            ] = signal_direction
            signal_for_learning[
                "confidence"
            ] = signal_confidence

            signal = _require_signal_dict(
                integrate_learning_intelligence(
                    signal_for_learning,
                    session=market_session,
                    market_condition=market_condition,
                ),
                stage="learning_intelligence",
            )
        else:
            signal[
                "learning_intelligence"
            ] = {
                "version": 27,
                "analysis_only": True,
                "applied": False,
                "reason": (
                    "Learning adjustment applies only to BUY or SELL signals."
                ),
                "session": market_session,
                "market_condition": market_condition,
            }

        signal_for_guardrail = dict(
            signal
        )
        signal_for_guardrail[
            "symbol"
        ] = resolved_symbol
        signal_for_guardrail[
            "market_session"
        ] = market_session
        signal_for_guardrail[
            "market_condition"
        ] = market_condition

        signal = _require_signal_dict(
            apply_complete_confidence_guardrail(
                signal_for_guardrail
            ),
            stage="confidence_guardrail",
        )

        signal[
            "project"
        ] = PROJECT_NAME
        signal[
            "version"
        ] = API_VERSION
        signal[
            "safety_version"
        ] = SAFETY_VERSION
        signal[
            "symbol"
        ] = resolved_symbol
        signal[
            "interval"
        ] = resolved_interval
        signal[
            "analysis_mode"
        ] = "MULTI_TIMEFRAME"
        signal[
            "automatic_timeframes"
        ] = list(
            AUTOMATIC_ANALYSIS_TIMEFRAMES
        )
        signal[
            "user_selects_timeframe"
        ] = False
        signal[
            "analysis_only"
        ] = True
        signal[
            "broker_connection_enabled"
        ] = BROKER_CONNECTION_ENABLED
        signal[
            "trade_execution_enabled"
        ] = TRADE_EXECUTION_ENABLED
        signal[
            "automatic_order_placement_enabled"
        ] = AUTOMATIC_ORDER_PLACEMENT_ENABLED
        signal[
            "confidence_guardrail_enabled"
        ] = True
        signal[
            "maximum_guardrail_adjustment"
        ] = 4.0
        signal[
            "minimum_guardrail_completed_trades"
        ] = 20
        signal[
            "minimum_final_confidence"
        ] = MINIMUM_CONFIDENCE
        signal[
            "force_refresh_requested"
        ] = bool(
            force_refresh
        )
        signal[
            "force_refresh_applied"
        ] = False

        saved_trade = save_approved_signal(
            db=db,
            symbol=resolved_symbol,
            interval=resolved_interval,
            signal_data=signal,
        )

        if saved_trade is not None:
            history_record: Dict[
                str,
                Any,
            ] = {
                "saved": True,
                "signal_id": getattr(
                    saved_trade,
                    "signal_id",
                    None,
                ),
                "database_id": getattr(
                    saved_trade,
                    "id",
                    None,
                ),
                "status": getattr(
                    saved_trade,
                    "status",
                    None,
                ),
                "result": getattr(
                    saved_trade,
                    "result",
                    None,
                ),
                "direction": getattr(
                    saved_trade,
                    "direction",
                    None,
                ),
                "created_at": getattr(
                    saved_trade,
                    "created_at",
                    None,
                ),
            }
        else:
            history_record = {
                "saved": False,
                "signal_id": None,
                "reason": (
                    "Only approved BUY or SELL signals with at least "
                    f"{MINIMUM_CONFIDENCE}% confidence, at least "
                    f"{MINIMUM_CONFIRMATIONS} confirmations, Market Regime "
                    "approval, Version 27 learning safety, Version 30 "
                    "confidence guardrail approval and complete risk "
                    "levels are saved."
                ),
            }

        tracking_updates = (
            _build_tracking_updates(
                updated_trades
            )
        )

        return {
            "status": "success",
            "project": PROJECT_NAME,
            "version": API_VERSION,
            "safety_version": SAFETY_VERSION,
            "symbol": resolved_symbol,
            "interval": resolved_interval,
            "analysis_mode": "MULTI_TIMEFRAME",
            "automatic_timeframes": list(
                AUTOMATIC_ANALYSIS_TIMEFRAMES
            ),
            "user_selects_timeframe": False,
            "current_price": current_price,
            "prices_received": len(
                prices
            ),
            "candles_received": len(
                candles
            ),
            "market_regime_intelligence_enabled": True,
            "symbol_winrate_intelligence_enabled": True,
            "learning_intelligence_enabled": True,
            "confidence_guardrail_enabled": True,
            "session_performance_learning_enabled": True,
            "timeframe_performance_learning_enabled": False,
            "learning_session": market_session,
            "learning_market_condition": market_condition,
            "signal": signal,
            "signal_history": history_record,
            "active_trade_updates": {
                "updated_count": len(
                    updated_trades
                ),
                "returned_count": len(
                    tracking_updates
                ),
                "maximum_returned": (
                    MAXIMUM_TRACKING_UPDATES
                ),
                "truncated": (
                    len(updated_trades)
                    > len(tracking_updates)
                ),
                "trades": tracking_updates,
            },
            "safety": {
                "analysis_only": True,
                "minimum_confidence": (
                    MINIMUM_CONFIDENCE
                ),
                "minimum_confirmations": (
                    MINIMUM_CONFIRMATIONS
                ),
                "maximum_learning_confidence_adjustment": 4.0,
                "maximum_guardrail_confidence_adjustment": 4.0,
                "minimum_guardrail_completed_trades": 20,
                "minimum_final_guarded_confidence": 80.0,
                "confidence_guardrail_is_analysis_only": True,
                "learning_is_analysis_only": True,
                "broker_connection_enabled": (
                    BROKER_CONNECTION_ENABLED
                ),
                "trade_execution_enabled": (
                    TRADE_EXECUTION_ENABLED
                ),
                "automatic_order_placement_enabled": (
                    AUTOMATIC_ORDER_PLACEMENT_ENABLED
                ),
            },
            "important_notice": (
                "Blue-Trading-AI provides market analysis and signal "
                "recommendations only. It does not connect to brokers or "
                "execute trades."
            ),
        }

    except HTTPException:
        raise

    except SQLAlchemyError as error:
        db.rollback()

        logger.exception(
            "Trading signal database operation failed.",
            extra={
                "symbol": resolved_symbol,
                "interval": resolved_interval,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Trading signal storage is temporarily unavailable.",
        ) from error

    except Exception as error:
        db.rollback()

        logger.exception(
            "Trading signal generation failed.",
            extra={
                "symbol": resolved_symbol,
                "interval": resolved_interval,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Trading signal generation failed.",
        ) from error


__all__ = [
    "API_VERSION",
    "AUTOMATIC_ORDER_PLACEMENT_ENABLED",
    "BROKER_CONNECTION_ENABLED",
    "MINIMUM_CONFIDENCE",
    "MINIMUM_CONFIRMATIONS",
    "PRIMARY_ANALYSIS_INTERVAL",
    "AUTOMATIC_ANALYSIS_TIMEFRAMES",
    "PROJECT_NAME",
    "SAFETY_VERSION",
    "TRADE_EXECUTION_ENABLED",
    "router",
    "trading_home",
    "trading_signal",
    "trading_test",
]