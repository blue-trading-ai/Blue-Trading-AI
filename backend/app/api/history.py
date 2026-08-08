from __future__ import annotations

import logging
from typing import Any, Generator, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.schemas.trade_history import (
    TradeHistoryListResponse,
    TradeHistoryResponse,
    TradeStatisticsResponse,
)
from app.services.trade_history_service import (
    cancel_trade,
    get_active_trades,
    get_trade_by_signal_id,
    get_trade_history,
    get_trade_statistics,
    get_version_30_learning_status,
    register_trade_outcome_for_learning,
    update_active_trades,
)


logger = logging.getLogger(__name__)

PROJECT_NAME = "Blue-Trading-AI"
SAFETY_VERSION = 30

MINIMUM_SIGNAL_CONFIDENCE = 80.0
MINIMUM_CONFIRMATIONS = 3
MINIMUM_COMPLETED_TRADES = 20
MAXIMUM_CONFIDENCE_ADJUSTMENT = 4.0

BROKER_CONNECTION_ENABLED = False
TRADE_EXECUTION_ENABLED = False
AUTOMATIC_ORDER_PLACEMENT_ENABLED = False

MAXIMUM_IDENTIFIER_LENGTH = 128
MAXIMUM_FILTER_LENGTH = 32


router = APIRouter(
    prefix="/history",
    tags=["Signal History - Version 30"],
)


def get_db() -> Generator[Session, None, None]:
    """Provide one database session per API request."""

    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def _normalize_identifier(
    value: str,
    *,
    field_name: str,
) -> str:
    normalized = value.strip()

    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} cannot be empty.",
        )

    if len(normalized) > MAXIMUM_IDENTIFIER_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} is too long.",
        )

    return normalized


def _normalize_optional_filter(
    value: Optional[str],
) -> Optional[str]:
    if value is None:
        return None

    normalized = value.strip()

    if not normalized:
        return None

    if len(normalized) > MAXIMUM_FILTER_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="History filter value is too long.",
        )

    return normalized.upper()


def _raise_service_error(
    operation: str,
    error: Exception,
) -> None:
    if isinstance(
        error,
        HTTPException,
    ):
        raise error

    if isinstance(
        error,
        SQLAlchemyError,
    ):
        logger.exception(
            "Database error during history operation.",
            extra={
                "operation": operation,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Signal history is temporarily unavailable.",
        ) from error

    if isinstance(
        error,
        ValueError,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error) or "Invalid signal-history request.",
        ) from error

    logger.exception(
        "Unexpected Signal History API failure.",
        extra={
            "operation": operation,
        },
    )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Signal history operation failed.",
    ) from error


@router.get("/")
def history_home(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        learning_status = get_version_30_learning_status(
            db=db,
        )
    except Exception as error:
        _raise_service_error(
            "history_home",
            error,
        )

    if not isinstance(
        learning_status,
        dict,
    ):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Learning status returned an invalid response.",
        )

    return {
        "status": "success",
        "message": (
            "Blue-Trading-AI Version 30 Signal History "
            "API is working"
        ),
        "project": PROJECT_NAME,
        "module": "Signal History and Completed-Trade Learning",
        "version": "30.0.0",
        "safety_version": SAFETY_VERSION,
        "completed_trade_learning": "enabled",
        "confidence_guardrail": "enabled",
        "cancelled_trade_learning": "enabled",
        "session_performance_learning": "enabled",
        "timeframe_performance_learning": "disabled",
        "learning_status": learning_status,
        "analysis_only": True,
        "broker_connection_enabled": BROKER_CONNECTION_ENABLED,
        "trade_execution_enabled": TRADE_EXECUTION_ENABLED,
        "automatic_order_placement_enabled": (
            AUTOMATIC_ORDER_PLACEMENT_ENABLED
        ),
    }


@router.get("/test")
def history_api_test() -> dict[str, Any]:
    return {
        "status": "success",
        "message": (
            "Blue-Trading-AI Version 30 Signal History "
            "API is working"
        ),
        "project": PROJECT_NAME,
        "version": "30.0.0",
        "safety_version": SAFETY_VERSION,
        "features": [
            "active_trade_tracking",
            "tp1_tracking",
            "tp2_tracking",
            "stop_loss_tracking",
            "trade_cancellation",
            "completed_trade_learning",
            "cancelled_trade_learning",
            "duplicate_learning_prevention",
            "market_session_learning",
            "market_condition_learning",
            "confidence_adjustment_tracking",
            "confidence_guardrail_v30",
            "persistent_learning_status",
            "trade_statistics",
            "analysis_only",
            "no_broker_connection",
            "no_trade_execution",
        ],
        "minimum_signal_confidence": MINIMUM_SIGNAL_CONFIDENCE,
        "minimum_confirmations": MINIMUM_CONFIRMATIONS,
        "minimum_completed_trades": MINIMUM_COMPLETED_TRADES,
        "maximum_confidence_adjustment": (
            MAXIMUM_CONFIDENCE_ADJUSTMENT
        ),
        "timeframe_performance_learning_enabled": False,
        "strategy_optimization_enabled": False,
        "strategy_ranking_enabled": False,
        "analysis_only": True,
        "broker_connection_enabled": BROKER_CONNECTION_ENABLED,
        "trade_execution_enabled": TRADE_EXECUTION_ENABLED,
    }


@router.get("/learning-status")
def read_learning_status(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return persistent completed-trade learning status."""

    try:
        result = get_version_30_learning_status(
            db=db,
        )
    except Exception as error:
        _raise_service_error(
            "read_learning_status",
            error,
        )

    if not isinstance(
        result,
        dict,
    ):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Learning status returned an invalid response.",
        )

    return result


@router.post("/{signal_id}/register-learning")
def register_trade_learning(
    signal_id: str = Path(
        ...,
        min_length=1,
        max_length=MAXIMUM_IDENTIFIER_LENGTH,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Register one completed trade with learning.

    Duplicate registration is prevented by the persisted
    learning_registered field.
    """

    normalized_signal_id = _normalize_identifier(
        signal_id,
        field_name="Signal ID",
    )

    try:
        trade = get_trade_by_signal_id(
            db=db,
            signal_id=normalized_signal_id,
        )
    except Exception as error:
        _raise_service_error(
            "register_trade_learning.lookup",
            error,
        )

    if not trade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trade signal not found",
        )

    trade_status = str(
        trade.status or ""
    ).strip().upper()

    if trade_status not in {
        "CLOSED",
        "CANCELLED",
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Only CLOSED or CANCELLED trades can be "
                "registered for learning."
            ),
        )

    if bool(
        trade.learning_registered
    ):
        return {
            "status": "success",
            "registered": False,
            "duplicate_prevented": True,
            "message": (
                "This trade has already been registered "
                "for learning."
            ),
            "signal_id": trade.signal_id,
            "learning_result": trade.learning_result,
            "learning_confidence_adjustment": (
                trade.learning_confidence_adjustment
            ),
        }

    try:
        registered = register_trade_outcome_for_learning(
            db=db,
            trade=trade,
        )
    except Exception as error:
        _raise_service_error(
            "register_trade_learning.register",
            error,
        )

    if not registered:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The completed trade could not be registered "
                "for learning. Check its result and stored "
                "trade data."
            ),
        )

    return {
        "status": "success",
        "registered": True,
        "duplicate_prevented": False,
        "signal_id": trade.signal_id,
        "trade_status": trade.status,
        "trade_result": trade.result,
        "learning_result": trade.learning_result,
        "learning_registered_at": (
            trade.learning_registered_at
        ),
        "learning_confidence_adjustment": (
            trade.learning_confidence_adjustment
        ),
        "analysis_only": True,
    }


@router.get(
    "/statistics",
    response_model=TradeStatisticsResponse,
)
def read_trade_statistics(
    db: Session = Depends(get_db),
) -> Any:
    try:
        return get_trade_statistics(
            db=db,
        )
    except Exception as error:
        _raise_service_error(
            "read_trade_statistics",
            error,
        )


@router.get(
    "/active",
    response_model=list[TradeHistoryResponse],
)
def read_active_trades(
    symbol: Optional[str] = Query(
        default=None,
        min_length=1,
        max_length=MAXIMUM_FILTER_LENGTH,
    ),
    db: Session = Depends(get_db),
) -> Any:
    normalized_symbol = _normalize_optional_filter(
        symbol
    )

    try:
        return get_active_trades(
            db=db,
            symbol=normalized_symbol,
        )
    except Exception as error:
        _raise_service_error(
            "read_active_trades",
            error,
        )


@router.post(
    "/update-price",
    response_model=list[TradeHistoryResponse],
)
def update_trade_prices(
    symbol: str = Query(
        ...,
        min_length=1,
        max_length=MAXIMUM_FILTER_LENGTH,
    ),
    current_price: float = Query(
        ...,
        gt=0,
    ),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update active trades and check TP1, TP2, and stop loss.

    Newly completed trades are automatically registered
    for Version 30 learning by the service layer.
    """

    normalized_symbol = _normalize_optional_filter(
        symbol
    )

    if normalized_symbol is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Symbol cannot be empty.",
        )

    try:
        return update_active_trades(
            db=db,
            symbol=normalized_symbol,
            current_price=current_price,
        )
    except Exception as error:
        _raise_service_error(
            "update_trade_prices",
            error,
        )


@router.get(
    "/list",
    response_model=TradeHistoryListResponse,
)
def read_trade_history(
    skip: int = Query(
        default=0,
        ge=0,
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
    symbol: Optional[str] = Query(
        default=None,
        min_length=1,
        max_length=MAXIMUM_FILTER_LENGTH,
    ),
    interval: Optional[str] = Query(
        default=None,
        min_length=1,
        max_length=MAXIMUM_FILTER_LENGTH,
    ),
    direction: Optional[str] = Query(
        default=None,
        min_length=1,
        max_length=MAXIMUM_FILTER_LENGTH,
    ),
    trade_status: Optional[str] = Query(
        default=None,
        alias="status",
        min_length=1,
        max_length=MAXIMUM_FILTER_LENGTH,
    ),
    result: Optional[str] = Query(
        default=None,
        min_length=1,
        max_length=MAXIMUM_FILTER_LENGTH,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        total, trades = get_trade_history(
            db=db,
            skip=skip,
            limit=limit,
            symbol=_normalize_optional_filter(
                symbol
            ),
            interval=_normalize_optional_filter(
                interval
            ),
            direction=_normalize_optional_filter(
                direction
            ),
            status=_normalize_optional_filter(
                trade_status
            ),
            result=_normalize_optional_filter(
                result
            ),
        )
    except Exception as error:
        _raise_service_error(
            "read_trade_history",
            error,
        )

    return {
        "total": total,
        "trades": trades,
    }


# Backward-compatible history listing route.
@router.get(
    "/all",
    response_model=TradeHistoryListResponse,
)
def read_all_trade_history(
    skip: int = Query(
        default=0,
        ge=0,
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
    symbol: Optional[str] = Query(
        default=None,
        max_length=MAXIMUM_FILTER_LENGTH,
    ),
    interval: Optional[str] = Query(
        default=None,
        max_length=MAXIMUM_FILTER_LENGTH,
    ),
    direction: Optional[str] = Query(
        default=None,
        max_length=MAXIMUM_FILTER_LENGTH,
    ),
    trade_status: Optional[str] = Query(
        default=None,
        alias="status",
        max_length=MAXIMUM_FILTER_LENGTH,
    ),
    result: Optional[str] = Query(
        default=None,
        max_length=MAXIMUM_FILTER_LENGTH,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        total, trades = get_trade_history(
            db=db,
            skip=skip,
            limit=limit,
            symbol=_normalize_optional_filter(
                symbol
            ),
            interval=_normalize_optional_filter(
                interval
            ),
            direction=_normalize_optional_filter(
                direction
            ),
            status=_normalize_optional_filter(
                trade_status
            ),
            result=_normalize_optional_filter(
                result
            ),
        )
    except Exception as error:
        _raise_service_error(
            "read_all_trade_history",
            error,
        )

    return {
        "total": total,
        "trades": trades,
    }


@router.post(
    "/{signal_id}/cancel",
    response_model=TradeHistoryResponse,
)
def cancel_active_trade(
    signal_id: str = Path(
        ...,
        min_length=1,
        max_length=MAXIMUM_IDENTIFIER_LENGTH,
    ),
    current_price: Optional[float] = Query(
        default=None,
        gt=0,
    ),
    db: Session = Depends(get_db),
) -> Any:
    """
    Cancel an active trade.

    The Version 30 service classifies the realised P/L as
    WIN, LOSS, or BREAKEVEN and registers it for learning.
    """

    normalized_signal_id = _normalize_identifier(
        signal_id,
        field_name="Signal ID",
    )

    try:
        trade = get_trade_by_signal_id(
            db=db,
            signal_id=normalized_signal_id,
        )
    except Exception as error:
        _raise_service_error(
            "cancel_active_trade.lookup",
            error,
        )

    if not trade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trade signal not found",
        )

    if str(
        trade.status or ""
    ).strip().upper() != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only active trades can be cancelled.",
        )

    try:
        cancelled_trade = cancel_trade(
            db=db,
            signal_id=normalized_signal_id,
            current_price=current_price,
        )
    except Exception as error:
        _raise_service_error(
            "cancel_active_trade.cancel",
            error,
        )

    if not cancelled_trade:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to cancel trade",
        )

    return cancelled_trade


# Keep this dynamic route last.
@router.get(
    "/{signal_id}",
    response_model=TradeHistoryResponse,
)
def read_trade_by_signal_id(
    signal_id: str = Path(
        ...,
        min_length=1,
        max_length=MAXIMUM_IDENTIFIER_LENGTH,
    ),
    db: Session = Depends(get_db),
) -> Any:
    normalized_signal_id = _normalize_identifier(
        signal_id,
        field_name="Signal ID",
    )

    try:
        trade = get_trade_by_signal_id(
            db=db,
            signal_id=normalized_signal_id,
        )
    except Exception as error:
        _raise_service_error(
            "read_trade_by_signal_id",
            error,
        )

    if not trade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trade signal not found",
        )

    return trade


__all__ = [
    "AUTOMATIC_ORDER_PLACEMENT_ENABLED",
    "BROKER_CONNECTION_ENABLED",
    "MAXIMUM_CONFIDENCE_ADJUSTMENT",
    "MINIMUM_COMPLETED_TRADES",
    "MINIMUM_CONFIRMATIONS",
    "MINIMUM_SIGNAL_CONFIDENCE",
    "PROJECT_NAME",
    "SAFETY_VERSION",
    "TRADE_EXECUTION_ENABLED",
    "cancel_active_trade",
    "get_db",
    "history_api_test",
    "history_home",
    "read_active_trades",
    "read_all_trade_history",
    "read_learning_status",
    "read_trade_by_signal_id",
    "read_trade_history",
    "read_trade_statistics",
    "register_trade_learning",
    "router",
    "update_trade_prices",
]