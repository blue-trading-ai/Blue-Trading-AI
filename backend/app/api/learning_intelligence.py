"""
Blue-Trading-AI
Version 27
app/api/learning_intelligence.py

FastAPI endpoints for the Version 27 Learning Intelligence engine.
Analysis only. No broker connection and no trade execution.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.api.admin_users import require_owner
from app.services.learning_intelligence_integration import (
    evaluate_learning_intelligence,
    get_learning_summary,
    register_completed_trade,
    reset_learning_intelligence_service,
)


logger = logging.getLogger(__name__)

SessionName = Literal[
    "asian",
    "european",
    "us",
]
Direction = Literal[
    "BUY",
    "SELL",
]
TradeResult = Literal[
    "WIN",
    "LOSS",
    "BREAKEVEN",
]

MAXIMUM_SYMBOL_LENGTH = 30
MAXIMUM_MARKET_CONDITION_LENGTH = 80


router = APIRouter(
    prefix="/learning-intelligence",
    tags=["Learning Intelligence V27"],
)


def _normalize_symbol(
    value: str,
) -> str:
    cleaned = (
        value.strip()
        .upper()
        .replace("/", "")
        .replace("-", "")
        .replace("_", "")
        .replace(" ", "")
    )

    if not cleaned:
        raise ValueError(
            "symbol is required"
        )

    if len(cleaned) > MAXIMUM_SYMBOL_LENGTH:
        raise ValueError(
            "symbol is too long"
        )

    if not cleaned.isalnum():
        raise ValueError(
            "symbol contains unsupported characters"
        )

    return cleaned


def _normalize_market_condition(
    value: str,
) -> str:
    cleaned = (
        value.strip()
        .lower()
        .replace(" ", "_")
    )

    if not cleaned:
        raise ValueError(
            "market_condition is required"
        )

    if len(cleaned) > MAXIMUM_MARKET_CONDITION_LENGTH:
        raise ValueError(
            "market_condition is too long"
        )

    allowed_characters = set(
        "abcdefghijklmnopqrstuvwxyz0123456789_-"
    )

    if any(
        character not in allowed_characters
        for character in cleaned
    ):
        raise ValueError(
            "market_condition contains unsupported characters"
        )

    return cleaned


def _validate_mapping_result(
    result: Any,
    operation: str,
) -> dict[str, Any]:
    if isinstance(
        result,
        dict,
    ):
        return result

    logger.error(
        "Learning Intelligence service returned an invalid response type.",
        extra={
            "operation": operation,
            "result_type": type(result).__name__,
        },
    )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=(
            "Learning Intelligence returned an invalid response."
        ),
    )


class CompletedTradeRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    symbol: str = Field(
        ...,
        min_length=1,
        max_length=MAXIMUM_SYMBOL_LENGTH,
    )
    session: SessionName
    market_condition: str = Field(
        ...,
        min_length=1,
        max_length=MAXIMUM_MARKET_CONDITION_LENGTH,
    )
    direction: Direction
    confidence: float = Field(
        ...,
        ge=0.0,
        le=100.0,
    )
    risk_reward: float = Field(
        ...,
        ge=0.0,
        le=100.0,
    )
    result: TradeResult

    entry_price: float = Field(
        ...,
        ge=0.0,
    )
    stop_loss: float = Field(
        ...,
        ge=0.0,
    )
    take_profit: float = Field(
        ...,
        ge=0.0,
    )

    opened_at: datetime
    closed_at: datetime

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
        "market_condition",
    )
    @classmethod
    def normalize_market_condition(
        cls,
        value: str,
    ) -> str:
        return _normalize_market_condition(
            value
        )

    @field_validator(
        "direction",
        "result",
        mode="before",
    )
    @classmethod
    def normalize_uppercase_fields(
        cls,
        value: Any,
    ) -> Any:
        if isinstance(
            value,
            str,
        ):
            return value.strip().upper()

        return value

    @field_validator(
        "session",
        mode="before",
    )
    @classmethod
    def normalize_session(
        cls,
        value: Any,
    ) -> Any:
        if isinstance(
            value,
            str,
        ):
            return value.strip().lower()

        return value

    @model_validator(
        mode="after",
    )
    def validate_trade_times(
        self,
    ) -> "CompletedTradeRequest":
        if self.closed_at < self.opened_at:
            raise ValueError(
                "closed_at cannot be earlier than opened_at"
            )

        return self


class LearningEvaluationRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    symbol: str = Field(
        ...,
        min_length=1,
        max_length=MAXIMUM_SYMBOL_LENGTH,
    )
    session: SessionName
    market_condition: str = Field(
        ...,
        min_length=1,
        max_length=MAXIMUM_MARKET_CONDITION_LENGTH,
    )
    direction: Direction
    current_confidence: float = Field(
        ...,
        ge=0.0,
        le=100.0,
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
        "market_condition",
    )
    @classmethod
    def normalize_market_condition(
        cls,
        value: str,
    ) -> str:
        return _normalize_market_condition(
            value
        )

    @field_validator(
        "direction",
        mode="before",
    )
    @classmethod
    def normalize_direction(
        cls,
        value: Any,
    ) -> Any:
        if isinstance(
            value,
            str,
        ):
            return value.strip().upper()

        return value

    @field_validator(
        "session",
        mode="before",
    )
    @classmethod
    def normalize_session(
        cls,
        value: Any,
    ) -> Any:
        if isinstance(
            value,
            str,
        ):
            return value.strip().lower()

        return value


class StandardResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    status: str
    version: int
    data: dict[str, Any]


@router.get(
    "/",
    response_model=StandardResponse,
    summary="Learning Intelligence status",
)
async def learning_intelligence_home() -> StandardResponse:
    return StandardResponse(
        status="ok",
        version=27,
        data={
            "engine": "AI Self-Learning Intelligence",
            "analysis_only": True,
            "minimum_completed_trades": 20,
            "maximum_confidence_adjustment": 4,
            "supported_sessions": [
                "asian",
                "european",
                "us",
            ],
            "timeframe_performance_enabled": False,
            "trade_execution_enabled": False,
            "learning_mutations_require_owner": True,
        },
    )


@router.get(
    "/health",
    response_model=StandardResponse,
    summary="Learning Intelligence health check",
)
async def learning_intelligence_health() -> StandardResponse:
    return StandardResponse(
        status="healthy",
        version=27,
        data={
            "service": "learning_intelligence",
            "ready": True,
            "analysis_only": True,
        },
    )


@router.post(
    "/completed-trades",
    response_model=StandardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a completed trade",
)
async def add_completed_trade(
    payload: CompletedTradeRequest,
    _owner: Any = Depends(require_owner),
) -> StandardResponse:
    try:
        result = register_completed_trade(
            payload.model_dump()
        )
    except ValueError as error:
        logger.warning(
            "Invalid completed-trade learning request: %s",
            error,
        )

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid completed trade.",
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Unable to register completed trade."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to register completed trade.",
        ) from error

    return StandardResponse(
        status="created",
        version=27,
        data=_validate_mapping_result(
            result,
            "completed-trades",
        ),
    )


@router.post(
    "/evaluate",
    response_model=StandardResponse,
    summary="Evaluate learning adjustment",
)
async def evaluate_learning(
    payload: LearningEvaluationRequest,
) -> StandardResponse:
    try:
        result = evaluate_learning_intelligence(
            symbol=payload.symbol,
            session=payload.session,
            market_condition=payload.market_condition,
            direction=payload.direction,
            current_confidence=payload.current_confidence,
        )
    except ValueError as error:
        logger.warning(
            "Invalid Learning Intelligence evaluation: %s",
            error,
        )

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid learning-intelligence evaluation.",
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Unable to evaluate Learning Intelligence."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to evaluate learning intelligence.",
        ) from error

    return StandardResponse(
        status="ok",
        version=27,
        data=_validate_mapping_result(
            result,
            "evaluate",
        ),
    )


@router.get(
    "/summary",
    response_model=StandardResponse,
    summary="Get learning summary",
)
async def learning_summary(
    symbol: Optional[str] = Query(
        default=None,
        min_length=1,
        max_length=MAXIMUM_SYMBOL_LENGTH,
        description="Optional symbol filter, for example XAUUSD.",
    ),
    session: Optional[SessionName] = Query(
        default=None,
        description="Optional session filter.",
    ),
    market_condition: Optional[str] = Query(
        default=None,
        min_length=1,
        max_length=MAXIMUM_MARKET_CONDITION_LENGTH,
        description="Optional market-condition filter.",
    ),
) -> StandardResponse:
    try:
        summary = _validate_mapping_result(
            get_learning_summary(),
            "summary",
        )

        # Work on a shallow copy so filtering does not mutate
        # any service-owned dictionary.
        summary = dict(
            summary
        )

        if symbol:
            normalized_symbol = _normalize_symbol(
                symbol
            )

            symbols = summary.get(
                "symbols",
                {},
            )

            if not isinstance(
                symbols,
                dict,
            ):
                symbols = {}

            summary["symbols"] = {
                normalized_symbol: symbols.get(
                    normalized_symbol
                )
            }

        if session:
            sessions = summary.get(
                "sessions",
                {},
            )

            if not isinstance(
                sessions,
                dict,
            ):
                sessions = {}

            summary["sessions"] = {
                session: sessions.get(
                    session
                )
            }

        if market_condition:
            normalized_condition = (
                _normalize_market_condition(
                    market_condition
                )
            )

            conditions = summary.get(
                "market_conditions",
                {},
            )

            if not isinstance(
                conditions,
                dict,
            ):
                conditions = {}

            summary["market_conditions"] = {
                normalized_condition: conditions.get(
                    normalized_condition
                )
            }

        return StandardResponse(
            status="ok",
            version=27,
            data=summary,
        )
    except ValueError as error:
        logger.warning(
            "Invalid Learning Intelligence summary filter: %s",
            error,
        )

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid learning-summary filter.",
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Unable to load Learning Intelligence summary."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to load learning summary.",
        ) from error


@router.delete(
    "/reset",
    response_model=StandardResponse,
    summary="Reset in-memory learning data",
)
async def reset_learning_data(
    confirm: bool = Query(
        default=False,
        description="Must be true to reset the in-memory learning engine.",
    ),
    _owner: Any = Depends(require_owner),
) -> StandardResponse:
    if confirm is not True:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Set confirm=true to reset learning data.",
        )

    try:
        reset_learning_intelligence_service()
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Unable to reset Learning Intelligence service."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to reset learning intelligence.",
        ) from error

    return StandardResponse(
        status="reset",
        version=27,
        data={
            "message": "In-memory learning data has been cleared.",
            "persistent_database_changed": False,
        },
    )


__all__ = [
    "CompletedTradeRequest",
    "LearningEvaluationRequest",
    "StandardResponse",
    "add_completed_trade",
    "evaluate_learning",
    "learning_intelligence_health",
    "learning_intelligence_home",
    "learning_summary",
    "reset_learning_data",
    "router",
]