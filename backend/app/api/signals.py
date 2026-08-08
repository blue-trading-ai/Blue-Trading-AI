from __future__ import annotations

import logging
from typing import Any, Final

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.permission_dependencies import (
    require_permission_dependency,
)
from app.database.connection import get_db
from app.models.role_permission import (
    PERMISSION_SIGNAL_CREATE,
    PERMISSION_SIGNAL_MANAGE,
    PERMISSION_SIGNAL_READ,
)
from app.models.trading_signal import (
    SIGNAL_RESULT_BREAKEVEN,
    SIGNAL_RESULT_LOSS,
    SIGNAL_RESULT_WIN,
)
from app.models.user import User
from app.services.trading_signal_service import (
    TradingSignalNotFoundError,
    TradingSignalStateError,
    TradingSignalValidationError,
    cancel_signal,
    complete_signal,
    create_signal,
    expire_signal,
    get_signal_by_uid,
    list_signals,
    signal_public_payload,
    signals_public_payload,
)


logger = logging.getLogger(__name__)

SIGNAL_API_VERSION: Final = 43
MAXIMUM_SIGNAL_UID_LENGTH: Final = 128
MAXIMUM_SYMBOL_LENGTH: Final = 40
MAXIMUM_TIMEFRAME_LENGTH: Final = 20
MAXIMUM_DIRECTION_LENGTH: Final = 20
MAXIMUM_TEXT_LENGTH: Final = 4000
MAXIMUM_NESTED_KEYS: Final = 500
MAXIMUM_CONFIRMATION_ITEMS: Final = 100
MAXIMUM_LIST_LIMIT: Final = 500
MAXIMUM_OFFSET: Final = 1_000_000

ALLOWED_SYMBOL_CHARACTERS: Final = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/"
)
ALLOWED_TIMEFRAME_CHARACTERS: Final = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)


router = APIRouter(
    prefix="/signals",
    tags=["Trading Signal Database - Version 43"],
)


def _normalize_symbol(
    value: str,
) -> str:
    normalized = str(
        value or ""
    ).strip().upper()

    if not normalized:
        raise ValueError(
            "symbol cannot be empty"
        )

    if len(normalized) > MAXIMUM_SYMBOL_LENGTH:
        raise ValueError(
            "symbol is too long"
        )

    if any(
        character not in ALLOWED_SYMBOL_CHARACTERS
        for character in normalized
    ):
        raise ValueError(
            "symbol contains unsupported characters"
        )

    return normalized


def _normalize_timeframe(
    value: str,
) -> str:
    normalized = str(
        value or ""
    ).strip().upper()

    if not normalized:
        raise ValueError(
            "timeframe cannot be empty"
        )

    if len(normalized) > MAXIMUM_TIMEFRAME_LENGTH:
        raise ValueError(
            "timeframe is too long"
        )

    if any(
        character not in ALLOWED_TIMEFRAME_CHARACTERS
        for character in normalized
    ):
        raise ValueError(
            "timeframe contains unsupported characters"
        )

    return normalized


def _normalize_direction(
    value: str,
) -> str:
    normalized = str(
        value or ""
    ).strip().upper()

    aliases = {
        "LONG": "BUY",
        "BULLISH": "BUY",
        "UP": "BUY",
        "SHORT": "SELL",
        "BEARISH": "SELL",
        "DOWN": "SELL",
    }

    normalized = aliases.get(
        normalized,
        normalized,
    )

    if normalized not in {
        "BUY",
        "SELL",
        "WAIT",
    }:
        raise ValueError(
            "direction must resolve to BUY, SELL, or WAIT"
        )

    return normalized


def _normalize_signal_uid(
    value: str,
) -> str:
    normalized = str(
        value or ""
    ).strip()

    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="signal_uid cannot be empty.",
        )

    if len(normalized) > MAXIMUM_SIGNAL_UID_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="signal_uid is too long.",
        )

    return normalized


def _validate_nested_payload(
    value: Any,
    field_name: str,
) -> Any:
    if value is None:
        return None

    if isinstance(
        value,
        dict,
    ):
        if len(value) > MAXIMUM_NESTED_KEYS:
            raise ValueError(
                f"{field_name} contains too many fields"
            )
        return value

    if isinstance(
        value,
        list,
    ):
        if len(value) > MAXIMUM_CONFIRMATION_ITEMS:
            raise ValueError(
                f"{field_name} contains too many items"
            )
        return value

    return value


def _raise_database_error(
    operation: str,
    error: SQLAlchemyError,
) -> None:
    logger.exception(
        "Trading signal database operation failed.",
        extra={
            "operation": operation,
        },
    )

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Trading signal database is temporarily unavailable.",
    ) from error


class SignalCreateRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    symbol: str = Field(
        ...,
        min_length=1,
        max_length=MAXIMUM_SYMBOL_LENGTH,
    )
    timeframe: str = Field(
        ...,
        min_length=1,
        max_length=MAXIMUM_TIMEFRAME_LENGTH,
    )
    direction: str = Field(
        ...,
        min_length=3,
        max_length=MAXIMUM_DIRECTION_LENGTH,
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        allow_inf_nan=False,
    )
    confirmations_count: int = Field(
        ...,
        ge=0,
        le=100,
    )
    risk_reward_ratio: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        allow_inf_nan=False,
    )
    entry_price: float | None = Field(
        default=None,
        ge=0.0,
        allow_inf_nan=False,
    )
    stop_loss: float | None = Field(
        default=None,
        ge=0.0,
        allow_inf_nan=False,
    )
    take_profit_1: float | None = Field(
        default=None,
        ge=0.0,
        allow_inf_nan=False,
    )
    take_profit_2: float | None = Field(
        default=None,
        ge=0.0,
        allow_inf_nan=False,
    )
    take_profit_3: float | None = Field(
        default=None,
        ge=0.0,
        allow_inf_nan=False,
    )
    strategy_version: str | None = Field(
        default=None,
        max_length=50,
    )
    market_structure: dict[str, Any] | None = None
    confirmations: list[Any] | dict[str, Any] | None = None
    analysis_details: dict[str, Any] | None = None
    reasoning: str | None = Field(
        default=None,
        max_length=MAXIMUM_TEXT_LENGTH,
    )
    rejection_reason: str | None = Field(
        default=None,
        max_length=MAXIMUM_TEXT_LENGTH,
    )
    source: str = Field(
        default="MARKETMIND_AI",
        min_length=1,
        max_length=50,
    )

    @field_validator(
        "symbol",
    )
    @classmethod
    def normalize_symbol(
        cls,
        value: str,
    ) -> str:
        return _normalize_symbol(
            value
        )

    @field_validator(
        "timeframe",
    )
    @classmethod
    def normalize_timeframe(
        cls,
        value: str,
    ) -> str:
        return _normalize_timeframe(
            value
        )

    @field_validator(
        "direction",
    )
    @classmethod
    def normalize_direction(
        cls,
        value: str,
    ) -> str:
        return _normalize_direction(
            value
        )

    @field_validator(
        "market_structure",
        "confirmations",
        "analysis_details",
    )
    @classmethod
    def validate_nested_payloads(
        cls,
        value: Any,
        info,
    ) -> Any:
        return _validate_nested_payload(
            value,
            info.field_name,
        )

    @field_validator(
        "strategy_version",
        "reasoning",
        "rejection_reason",
        "source",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        normalized = value.strip()

        return (
            normalized
            if normalized
            else None
        )


class SignalCompleteRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    result: str = Field(
        ...,
        min_length=3,
        max_length=20,
    )

    @field_validator(
        "result",
    )
    @classmethod
    def normalize_result(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip().upper()

        if normalized not in {
            SIGNAL_RESULT_WIN,
            SIGNAL_RESULT_LOSS,
            SIGNAL_RESULT_BREAKEVEN,
        }:
            raise ValueError(
                "result must be WIN, LOSS, or BREAKEVEN"
            )

        return normalized


@router.get("/")
def signal_api_home() -> dict[str, Any]:
    return {
        "status": "ok",
        "signal_api_version": SIGNAL_API_VERSION,
        "persistent_storage_enabled": True,
        "broker_execution_enabled": False,
        "minimum_confidence": 80,
        "minimum_confirmations": 3,
        "minimum_risk_reward": 1.5,
        "endpoints": [
            "GET /signals/",
            "GET /signals/list",
            "GET /signals/{signal_uid}",
            "POST /signals/create",
            "POST /signals/{signal_uid}/complete",
            "POST /signals/{signal_uid}/cancel",
            "POST /signals/{signal_uid}/expire",
        ],
    }


@router.post(
    "/create",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SIGNAL_CREATE
            )
        )
    ],
)
def create_saved_signal(
    payload: SignalCreateRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(
        get_db
    ),
) -> dict[str, Any]:
    try:
        signal = create_signal(
            db,
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            direction=payload.direction,
            confidence=payload.confidence,
            confirmations_count=payload.confirmations_count,
            risk_reward_ratio=payload.risk_reward_ratio,
            entry_price=payload.entry_price,
            stop_loss=payload.stop_loss,
            take_profit_1=payload.take_profit_1,
            take_profit_2=payload.take_profit_2,
            take_profit_3=payload.take_profit_3,
            created_by_user_id=int(
                current_user.id
            ),
            strategy_version=payload.strategy_version,
            market_structure=payload.market_structure,
            confirmations=payload.confirmations,
            analysis_details=payload.analysis_details,
            reasoning=payload.reasoning,
            rejection_reason=payload.rejection_reason,
            source=payload.source or "MARKETMIND_AI",
            commit=True,
        )
    except TradingSignalValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except SQLAlchemyError as error:
        _raise_database_error(
            "create",
            error,
        )

    return {
        "status": "success",
        "message": "Trading signal saved successfully.",
        "signal": signal_public_payload(
            signal
        ),
    }


@router.get(
    "/list",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SIGNAL_READ
            )
        )
    ],
)
def get_saved_signals(
    symbol: str | None = Query(
        default=None,
        max_length=MAXIMUM_SYMBOL_LENGTH,
    ),
    timeframe: str | None = Query(
        default=None,
        max_length=MAXIMUM_TIMEFRAME_LENGTH,
    ),
    direction: str | None = Query(
        default=None,
        max_length=MAXIMUM_DIRECTION_LENGTH,
    ),
    signal_status: str | None = Query(
        default=None,
        alias="status",
        max_length=20,
    ),
    result: str | None = Query(
        default=None,
        max_length=20,
    ),
    trade_allowed: bool | None = Query(
        default=None,
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=MAXIMUM_LIST_LIMIT,
    ),
    offset: int = Query(
        default=0,
        ge=0,
        le=MAXIMUM_OFFSET,
    ),
    db: Session = Depends(
        get_db
    ),
) -> dict[str, Any]:
    normalized_symbol = (
        _normalize_symbol(
            symbol
        )
        if symbol
        else None
    )
    normalized_timeframe = (
        _normalize_timeframe(
            timeframe
        )
        if timeframe
        else None
    )
    normalized_direction = (
        _normalize_direction(
            direction
        )
        if direction
        else None
    )
    normalized_status = (
        signal_status.strip().upper()
        if signal_status
        else None
    )
    normalized_result = (
        result.strip().upper()
        if result
        else None
    )

    try:
        signals = list_signals(
            db,
            symbol=normalized_symbol,
            timeframe=normalized_timeframe,
            direction=normalized_direction,
            status=normalized_status,
            result=normalized_result,
            trade_allowed=trade_allowed,
            limit=limit,
            offset=offset,
        )
    except TradingSignalValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except SQLAlchemyError as error:
        _raise_database_error(
            "list",
            error,
        )

    return {
        "status": "success",
        "count": len(
            signals
        ),
        "limit": limit,
        "offset": offset,
        "signals": signals_public_payload(
            signals
        ),
    }


@router.get(
    "/{signal_uid}",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SIGNAL_READ
            )
        )
    ],
)
def get_saved_signal(
    signal_uid: str,
    db: Session = Depends(
        get_db
    ),
) -> dict[str, Any]:
    resolved_uid = _normalize_signal_uid(
        signal_uid
    )

    try:
        signal = get_signal_by_uid(
            db,
            signal_uid=resolved_uid,
        )
    except SQLAlchemyError as error:
        _raise_database_error(
            "get",
            error,
        )

    if signal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trading signal does not exist.",
        )

    return {
        "status": "success",
        "signal": signal_public_payload(
            signal
        ),
    }


@router.post(
    "/{signal_uid}/complete",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SIGNAL_MANAGE
            )
        )
    ],
)
def complete_saved_signal(
    signal_uid: str,
    payload: SignalCompleteRequest,
    db: Session = Depends(
        get_db
    ),
) -> dict[str, Any]:
    resolved_uid = _normalize_signal_uid(
        signal_uid
    )
    resolved_result = payload.result

    try:
        signal = get_signal_by_uid(
            db,
            signal_uid=resolved_uid,
        )
    except SQLAlchemyError as error:
        _raise_database_error(
            "complete_lookup",
            error,
        )

    if signal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trading signal does not exist.",
        )

    try:
        updated = complete_signal(
            db,
            signal_id=int(
                signal.id
            ),
            result=resolved_result,
            commit=True,
        )
    except TradingSignalStateError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except TradingSignalNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except SQLAlchemyError as error:
        _raise_database_error(
            "complete",
            error,
        )

    return {
        "status": "success",
        "message": "Trading signal completed.",
        "signal": signal_public_payload(
            updated
        ),
    }


@router.post(
    "/{signal_uid}/cancel",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SIGNAL_MANAGE
            )
        )
    ],
)
def cancel_saved_signal(
    signal_uid: str,
    db: Session = Depends(
        get_db
    ),
) -> dict[str, Any]:
    resolved_uid = _normalize_signal_uid(
        signal_uid
    )

    try:
        signal = get_signal_by_uid(
            db,
            signal_uid=resolved_uid,
        )
    except SQLAlchemyError as error:
        _raise_database_error(
            "cancel_lookup",
            error,
        )

    if signal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trading signal does not exist.",
        )

    try:
        updated = cancel_signal(
            db,
            signal_id=int(
                signal.id
            ),
            commit=True,
        )
    except TradingSignalStateError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except TradingSignalNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except SQLAlchemyError as error:
        _raise_database_error(
            "cancel",
            error,
        )

    return {
        "status": "success",
        "message": "Trading signal cancelled.",
        "signal": signal_public_payload(
            updated
        ),
    }


@router.post(
    "/{signal_uid}/expire",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SIGNAL_MANAGE
            )
        )
    ],
)
def expire_saved_signal(
    signal_uid: str,
    db: Session = Depends(
        get_db
    ),
) -> dict[str, Any]:
    resolved_uid = _normalize_signal_uid(
        signal_uid
    )

    try:
        signal = get_signal_by_uid(
            db,
            signal_uid=resolved_uid,
        )
    except SQLAlchemyError as error:
        _raise_database_error(
            "expire_lookup",
            error,
        )

    if signal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trading signal does not exist.",
        )

    try:
        updated = expire_signal(
            db,
            signal_id=int(
                signal.id
            ),
            commit=True,
        )
    except TradingSignalStateError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except TradingSignalNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except SQLAlchemyError as error:
        _raise_database_error(
            "expire",
            error,
        )

    return {
        "status": "success",
        "message": "Trading signal expired.",
        "signal": signal_public_payload(
            updated
        ),
    }


__all__ = [
    "SIGNAL_API_VERSION",
    "SignalCompleteRequest",
    "SignalCreateRequest",
    "cancel_saved_signal",
    "complete_saved_signal",
    "create_saved_signal",
    "expire_saved_signal",
    "get_saved_signal",
    "get_saved_signals",
    "router",
    "signal_api_home",
]