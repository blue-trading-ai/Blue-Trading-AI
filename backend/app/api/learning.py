from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.services.learning_adjustment_service import (
    get_learning_adjustment,
)


logger = logging.getLogger(__name__)

Direction = Literal["BUY", "SELL"]
SignalAction = Literal["BUY", "SELL", "WAIT", "NO_TRADE"]

MAXIMUM_SYMBOL_LENGTH = 32
MAXIMUM_GRADE_LENGTH = 16
MAXIMUM_CONFIRMATIONS = 100


router = APIRouter(
    prefix="/learning",
    tags=["Learning"],
)


def _normalize_symbol(
    symbol: str,
) -> str:
    normalized = symbol.strip().upper()

    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Symbol cannot be empty.",
        )

    if len(normalized) > MAXIMUM_SYMBOL_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Symbol is too long.",
        )

    allowed_characters = set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/"
    )

    if any(
        character not in allowed_characters
        for character in normalized
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Symbol contains unsupported characters.",
        )

    return normalized


def _normalize_grade(
    grade: str,
) -> str:
    normalized = grade.strip().upper()

    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Trade-quality grade cannot be empty.",
        )

    if len(normalized) > MAXIMUM_GRADE_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Trade-quality grade is too long.",
        )

    return normalized


@router.get("/")
def learning_home() -> dict[str, Any]:
    return {
        "status": "success",
        "message": (
            "Blue-Trading-AI Controlled Learning API "
            "is working"
        ),
        "safety_version": 11,
    }


@router.get("/test")
def learning_test() -> dict[str, Any]:
    return {
        "status": "success",
        "module": "controlled_learning_adjustment",
        "features": [
            "minimum_20_completed_trades",
            "symbol_performance_learning",
            "direction_performance_learning",
            "trade_quality_learning",
            "maximum_confidence_increase_5",
            "maximum_confidence_decrease_10",
            "wait_signal_protection",
            "minimum_80_confidence_protection",
            "minimum_3_confirmations_protection",
        ],
        "safety_version": 11,
    }


@router.get("/adjustment")
def learning_adjustment(
    symbol: str = Query(
        ...,
        min_length=1,
        max_length=MAXIMUM_SYMBOL_LENGTH,
        description="Trading symbol, for example XAUUSD",
    ),
    direction: Direction = Query(
        ...,
        description="Signal direction",
    ),
    trade_quality_grade: str = Query(
        ...,
        min_length=1,
        max_length=MAXIMUM_GRADE_LENGTH,
        description="Trade-quality grade",
    ),
    base_confidence: float = Query(
        ...,
        ge=0.0,
        le=100.0,
        description="Original signal confidence",
    ),
    confirmations_count: int = Query(
        ...,
        ge=0,
        le=MAXIMUM_CONFIRMATIONS,
        description="Number of signal confirmations",
    ),
    signal_action: SignalAction = Query(
        ...,
        description="Original signal action",
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    normalized_symbol = _normalize_symbol(
        symbol
    )
    normalized_grade = _normalize_grade(
        trade_quality_grade
    )

    try:
        result = get_learning_adjustment(
            db=db,
            symbol=normalized_symbol,
            direction=direction.upper(),
            trade_quality_grade=normalized_grade,
            base_confidence=base_confidence,
            confirmations_count=confirmations_count,
            signal_action=signal_action.upper(),
        )
    except SQLAlchemyError as error:
        logger.exception(
            "Database failure during controlled learning adjustment."
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Learning adjustment is temporarily unavailable.",
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                str(error)
                or "Invalid learning-adjustment request."
            ),
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Controlled learning adjustment failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Learning adjustment failed.",
        ) from error

    if not isinstance(
        result,
        dict,
    ):
        logger.error(
            "Learning adjustment service returned invalid response type.",
            extra={
                "result_type": type(result).__name__,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Learning adjustment returned an invalid response.",
        )

    return result


__all__ = [
    "learning_adjustment",
    "learning_home",
    "learning_test",
    "router",
]