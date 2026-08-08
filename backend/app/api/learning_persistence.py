"""
Blue-Trading-AI
Version 28
app/api/learning_persistence.py

FastAPI endpoints for Persistent Learning Intelligence.

Analysis only:

- No broker connection
- No order execution
- No automatic trade placement
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.admin_users import require_owner
from app.core.dependencies import get_db
from app.services.learning_persistence_service import (
    get_learning_persistence_status,
    rebuild_learning_from_database,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/learning-persistence",
    tags=["Learning Persistence V28"],
)


def _validate_result(
    result: Any,
    operation: str,
) -> dict[str, Any]:
    """Require persistence-service operations to return dictionaries."""

    if isinstance(result, dict):
        return result

    logger.error(
        "Learning Persistence service returned an invalid response type.",
        extra={
            "operation": operation,
            "result_type": type(result).__name__,
        },
    )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Learning Persistence returned an invalid response.",
    )


def _raise_service_error(
    operation: str,
    error: Exception,
) -> None:
    """Translate internal persistence failures into safe HTTP responses."""

    if isinstance(error, HTTPException):
        raise error

    if isinstance(error, SQLAlchemyError):
        logger.exception(
            "Database error during Learning Persistence operation.",
            extra={
                "operation": operation,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Learning Persistence database is temporarily unavailable."
            ),
        ) from error

    if isinstance(error, ValueError):
        logger.warning(
            "Invalid Learning Persistence request during %s: %s",
            operation,
            error,
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Learning Persistence request.",
        ) from error

    logger.exception(
        "Unexpected Learning Persistence operation failure.",
        extra={
            "operation": operation,
        },
    )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Learning Persistence operation failed.",
    ) from error


@router.get("/")
def learning_persistence_home() -> dict[str, Any]:
    """Return Version 28 persistence-engine information."""

    return {
        "status": "success",
        "project": "Blue-Trading-AI",
        "version": "28.0.0",
        "safety_version": 28,
        "module": "Persistent Learning Intelligence",
        "features": [
            "database_learning_restore",
            "automatic_restart_recovery",
            "completed_trade_rebuild",
            "symbol_performance_restore",
            "session_performance_restore",
            "market_condition_restore",
            "buy_sell_performance_restore",
            "confidence_calibration_restore",
            "risk_reward_restore",
            "win_loss_streak_restore",
            "duplicate_free_rebuild",
        ],
        "supported_sessions": [
            "asian",
            "european",
            "us",
        ],
        "supported_results": [
            "WIN",
            "LOSS",
            "BREAKEVEN",
        ],
        "timeframe_performance_learning_enabled": False,
        "analysis_only": True,
        "broker_connection_enabled": False,
        "trade_execution_enabled": False,
        "automatic_order_placement_enabled": False,
        "destructive_operations_require_owner": True,
    }


@router.get("/health")
def learning_persistence_health() -> dict[str, Any]:
    """Return a lightweight persistence health response."""

    return {
        "status": "healthy",
        "project": "Blue-Trading-AI",
        "version": 28,
        "service": "learning_persistence",
        "database_restore_ready": True,
        "analysis_only": True,
    }


@router.get("/status")
def learning_persistence_status(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Compare database-eligible trades with the current learning engine."""

    try:
        result = get_learning_persistence_status(
            db=db
        )
    except Exception as error:
        _raise_service_error(
            "status",
            error,
        )

    return _validate_result(
        result,
        "status",
    )


@router.post("/rebuild")
def rebuild_learning(
    reset_engine: bool = Query(
        default=True,
        description=(
            "Reset the in-memory learning engine before loading "
            "completed database trades."
        ),
    ),
    _owner: Any = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Manually rebuild learning from the trade-history database.

    OWNER authorization is required because this operation can reset and
    reconstruct shared in-memory learning state.
    """

    try:
        result = rebuild_learning_from_database(
            db=db,
            reset_engine=(
                reset_engine is True
            ),
        )
    except Exception as error:
        _raise_service_error(
            "rebuild",
            error,
        )

    return _validate_result(
        result,
        "rebuild",
    )


@router.post("/sync")
def sync_learning(
    _owner: Any = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Fully synchronize the learning engine with completed database trades.

    This endpoint always resets the current in-memory learning state first,
    preventing duplicate statistics. OWNER authorization is required because
    this operation mutates shared learning state.
    """

    try:
        rebuild_result = _validate_result(
            rebuild_learning_from_database(
                db=db,
                reset_engine=True,
            ),
            "sync.rebuild",
        )

        status_result = _validate_result(
            get_learning_persistence_status(
                db=db
            ),
            "sync.status",
        )
    except Exception as error:
        _raise_service_error(
            "sync",
            error,
        )

    return {
        "status": "success",
        "version": 28,
        "rebuild": rebuild_result,
        "persistence_status": status_result,
    }


__all__ = [
    "learning_persistence_health",
    "learning_persistence_home",
    "learning_persistence_status",
    "rebuild_learning",
    "router",
    "sync_learning",
]