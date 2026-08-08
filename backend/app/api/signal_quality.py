from __future__ import annotations

import logging
from typing import Any, Final

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.permission_dependencies import (
    require_permission_dependency,
)
from app.database.connection import get_db
from app.models.role_permission import (
    PERMISSION_SIGNAL_CREATE,
    PERMISSION_SIGNAL_READ,
)
from app.services.high_quality_signal_service import (
    HighQualitySignalRejected,
    create_high_quality_signal,
)
from app.services.signal_publication_service import (
    DAILY_SIGNAL_LIMIT,
    DUPLICATE_SIGNAL_COOLDOWN_HOURS,
    MINIMUM_SIGNAL_CONFIDENCE,
    MINIMUM_SIGNAL_CONFIRMATIONS,
    MINIMUM_SIGNAL_RISK_REWARD,
    PREFERRED_DAILY_SIGNAL_TARGET,
    get_published_signal_count_today,
    get_remaining_signal_slots,
)


logger = logging.getLogger(__name__)

QUALITY_API_VERSION: Final = 49
MAXIMUM_SYMBOL_LENGTH: Final = 40
MAXIMUM_TIMEFRAME_LENGTH: Final = 20
MAXIMUM_DIRECTION_LENGTH: Final = 10
MAXIMUM_CONFIRMATIONS: Final = 50
MAXIMUM_RISK_REWARD: Final = 100.0
MAXIMUM_STRATEGY_VERSION_LENGTH: Final = 100
MAXIMUM_SOURCE_LENGTH: Final = 100
MAXIMUM_REASONING_LENGTH: Final = 8000
MAXIMUM_NESTED_KEYS: Final = 500
MAXIMUM_CONFIRMATION_ITEMS: Final = 100

ALLOWED_SYMBOL_CHARACTERS: Final = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/"
)
ALLOWED_TIMEFRAME_CHARACTERS: Final = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)


router = APIRouter(
    prefix="/signals/quality",
    tags=["High-Quality Signals - Version 49"],
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
        "SHORT": "SELL",
        "BEARISH": "SELL",
    }

    normalized = aliases.get(
        normalized,
        normalized,
    )

    if normalized not in {
        "BUY",
        "SELL",
    }:
        raise ValueError(
            "direction must resolve to BUY or SELL"
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
        if len(
            value
        ) > MAXIMUM_NESTED_KEYS:
            raise ValueError(
                f"{field_name} contains too many fields"
            )

        return value

    if isinstance(
        value,
        list,
    ):
        if len(
            value
        ) > MAXIMUM_CONFIRMATION_ITEMS:
            raise ValueError(
                f"{field_name} contains too many items"
            )

        return value

    return value


def _safe_public_signal_payload(
    signal: Any,
) -> dict[str, Any]:
    if signal is None or not hasattr(
        signal,
        "to_public_dict",
    ):
        logger.error(
            "High-quality signal service returned an invalid signal object."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="High-quality signal service returned an invalid response.",
        )

    payload = signal.to_public_dict()

    if not isinstance(
        payload,
        dict,
    ):
        logger.error(
            "High-quality signal public payload is invalid.",
            extra={
                "payload_type": type(
                    payload
                ).__name__,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="High-quality signal service returned an invalid response.",
        )

    return payload


class HighQualitySignalCreateRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    symbol: str = Field(
        ...,
        min_length=2,
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
        le=MAXIMUM_CONFIRMATIONS,
    )
    risk_reward_ratio: float = Field(
        ...,
        ge=0.0,
        le=MAXIMUM_RISK_REWARD,
        allow_inf_nan=False,
    )

    multi_timeframe_agreement: bool
    market_structure_confirmed: bool
    fundamental_conflict: bool = False
    high_impact_news_risk: bool = False

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
        max_length=MAXIMUM_STRATEGY_VERSION_LENGTH,
    )
    market_structure: dict[str, Any] | None = None
    confirmations: list[Any] | dict[str, Any] | None = None
    analysis_details: dict[str, Any] | None = None
    reasoning: str | None = Field(
        default=None,
        max_length=MAXIMUM_REASONING_LENGTH,
    )
    source: str = Field(
        default="HIGH_QUALITY_API",
        min_length=1,
        max_length=MAXIMUM_SOURCE_LENGTH,
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


@router.get("/")
def quality_home() -> dict[str, Any]:
    return {
        "status": "ok",
        "quality_api_version": QUALITY_API_VERSION,
        "quality_over_quantity": True,
        "preferred_daily_target": (
            PREFERRED_DAILY_SIGNAL_TARGET
        ),
        "daily_signal_limit": DAILY_SIGNAL_LIMIT,
        "duplicate_cooldown_hours": (
            DUPLICATE_SIGNAL_COOLDOWN_HOURS
        ),
        "minimum_confidence": str(
            MINIMUM_SIGNAL_CONFIDENCE
        ),
        "minimum_confirmations": (
            MINIMUM_SIGNAL_CONFIRMATIONS
        ),
        "minimum_risk_reward": str(
            MINIMUM_SIGNAL_RISK_REWARD
        ),
        "broker_execution_enabled": False,
        "endpoints": [
            "GET /signals/quality/",
            "GET /signals/quality/status",
            "POST /signals/quality/create",
        ],
    }


@router.get(
    "/status",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SIGNAL_READ
            )
        )
    ],
)
def quality_status(
    db: Session = Depends(
        get_db
    ),
) -> dict[str, Any]:
    try:
        published_today = (
            get_published_signal_count_today(
                db
            )
        )
        remaining_slots = (
            get_remaining_signal_slots(
                db
            )
        )
    except SQLAlchemyError as error:
        logger.exception(
            "Signal quality status database query failed."
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Signal publication status is temporarily unavailable.",
        ) from error
    except Exception as error:
        logger.exception(
            "Signal quality status failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to load signal quality status.",
        ) from error

    try:
        published_today = max(
            0,
            int(
                published_today
            ),
        )
        remaining_slots = max(
            0,
            int(
                remaining_slots
            ),
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ) as error:
        logger.error(
            "Signal publication service returned invalid counters."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Signal publication status returned an invalid response.",
        ) from error

    return {
        "status": "success",
        "published_today": published_today,
        "preferred_daily_target": (
            PREFERRED_DAILY_SIGNAL_TARGET
        ),
        "daily_signal_limit": DAILY_SIGNAL_LIMIT,
        "remaining_signal_slots": (
            remaining_slots
        ),
        "quality_over_quantity": True,
        "broker_execution_enabled": False,
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
def create_quality_signal(
    payload: HighQualitySignalCreateRequest,
    db: Session = Depends(
        get_db
    ),
) -> dict[str, Any]:
    try:
        signal, publication = (
            create_high_quality_signal(
                db,
                symbol=payload.symbol,
                timeframe=payload.timeframe,
                direction=payload.direction,
                confidence=payload.confidence,
                confirmations_count=(
                    payload.confirmations_count
                ),
                risk_reward_ratio=(
                    payload.risk_reward_ratio
                ),
                multi_timeframe_agreement=(
                    payload.multi_timeframe_agreement
                ),
                market_structure_confirmed=(
                    payload.market_structure_confirmed
                ),
                fundamental_conflict=(
                    payload.fundamental_conflict
                ),
                high_impact_news_risk=(
                    payload.high_impact_news_risk
                ),
                entry_price=payload.entry_price,
                stop_loss=payload.stop_loss,
                take_profit_1=(
                    payload.take_profit_1
                ),
                take_profit_2=(
                    payload.take_profit_2
                ),
                take_profit_3=(
                    payload.take_profit_3
                ),
                strategy_version=(
                    payload.strategy_version
                ),
                market_structure=(
                    payload.market_structure
                ),
                confirmations=(
                    payload.confirmations
                ),
                analysis_details=(
                    payload.analysis_details
                ),
                reasoning=payload.reasoning,
                source=(
                    payload.source
                    or "HIGH_QUALITY_API"
                ),
                commit=True,
            )
        )
    except HighQualitySignalRejected as error:
        reasons = [
            reason.strip()
            for reason in str(
                error
            ).split(";")
            if reason.strip()
        ]

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": (
                    "Signal rejected by quality control."
                ),
                "reasons": (
                    reasons
                    or [
                        "Signal did not meet quality requirements."
                    ]
                ),
            },
        ) from error
    except SQLAlchemyError as error:
        logger.exception(
            "High-quality signal creation failed at the database layer.",
            extra={
                "symbol": payload.symbol,
                "timeframe": payload.timeframe,
                "direction": payload.direction,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Signal database is temporarily unavailable.",
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                str(error)
                or "Invalid high-quality signal request."
            ),
        ) from error
    except Exception as error:
        logger.exception(
            "Unexpected high-quality signal creation failure.",
            extra={
                "symbol": payload.symbol,
                "timeframe": payload.timeframe,
                "direction": payload.direction,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create high-quality signal.",
        ) from error

    if not isinstance(
        publication,
        dict,
    ):
        logger.error(
            "Signal publication service returned an invalid publication payload.",
            extra={
                "publication_type": type(
                    publication
                ).__name__,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Signal publication service returned an invalid response.",
        )

    return {
        "status": "success",
        "message": (
            "High-quality signal published successfully."
        ),
        "signal": _safe_public_signal_payload(
            signal
        ),
        "publication": publication,
    }


__all__ = [
    "HighQualitySignalCreateRequest",
    "QUALITY_API_VERSION",
    "create_quality_signal",
    "quality_home",
    "quality_status",
    "router",
]