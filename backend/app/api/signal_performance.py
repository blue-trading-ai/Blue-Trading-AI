from __future__ import annotations

import logging
from typing import Any, Final

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.permission_dependencies import (
    require_permission_dependency,
)
from app.database.connection import get_db
from app.models.role_permission import (
    PERMISSION_SIGNAL_READ,
)
from app.services.signal_performance_service import (
    LEARNING_MINIMUM_COMPLETED_TRADES,
    get_overall_performance,
    get_performance_snapshot,
    get_recent_completed_signals,
    get_symbol_performance,
    get_timeframe_performance,
)


logger = logging.getLogger(__name__)

PERFORMANCE_API_VERSION: Final = 44
MAXIMUM_RECENT_LIMIT: Final = 500


router = APIRouter(
    prefix="/signals/performance",
    tags=["Signal Performance - Version 44"],
)


signal_read_guard = require_permission_dependency(
    PERMISSION_SIGNAL_READ
)


def _raise_database_error(
    operation: str,
    error: SQLAlchemyError,
) -> None:
    logger.exception(
        "Signal performance database operation failed.",
        extra={
            "operation": operation,
        },
    )

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Signal performance data is temporarily unavailable.",
    ) from error


def _validate_dict_result(
    value: Any,
    *,
    operation: str,
) -> dict[str, Any]:
    if isinstance(
        value,
        dict,
    ):
        return value

    logger.error(
        "Signal performance service returned an invalid dictionary response.",
        extra={
            "operation": operation,
            "result_type": type(value).__name__,
        },
    )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Signal performance service returned an invalid response.",
    )


def _validate_list_result(
    value: Any,
    *,
    operation: str,
) -> list[Any]:
    if isinstance(
        value,
        list,
    ):
        return value

    logger.error(
        "Signal performance service returned an invalid list response.",
        extra={
            "operation": operation,
            "result_type": type(value).__name__,
        },
    )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Signal performance service returned an invalid response.",
    )


@router.get(
    "/",
    dependencies=[
        Depends(
            signal_read_guard
        ),
    ],
)
def performance_home() -> dict[str, Any]:
    """Return Version 44 performance API capabilities."""

    return {
        "status": "ok",
        "performance_api_version": (
            PERFORMANCE_API_VERSION
        ),
        "persistent_history_enabled": True,
        "learning_minimum_completed_trades": (
            LEARNING_MINIMUM_COMPLETED_TRADES
        ),
        "broker_execution_enabled": False,
        "endpoints": [
            "GET /signals/performance/",
            "GET /signals/performance/overview",
            "GET /signals/performance/overall",
            "GET /signals/performance/by-symbol",
            "GET /signals/performance/by-timeframe",
            "GET /signals/performance/recent",
        ],
    }


@router.get(
    "/overview",
    dependencies=[
        Depends(
            signal_read_guard
        ),
    ],
)
def performance_overview(
    recent_limit: int = Query(
        default=50,
        ge=1,
        le=MAXIMUM_RECENT_LIMIT,
    ),
    db: Session = Depends(
        get_db
    ),
) -> dict[str, Any]:
    """Return the complete Version 44 performance snapshot."""

    try:
        snapshot = get_performance_snapshot(
            db,
            recent_limit=recent_limit,
        )
    except SQLAlchemyError as error:
        _raise_database_error(
            "overview",
            error,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                str(error)
                or "Invalid signal performance request."
            ),
        ) from error
    except Exception as error:
        logger.exception(
            "Signal performance overview failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to load signal performance overview.",
        ) from error

    return {
        "status": "success",
        "performance_version": (
            PERFORMANCE_API_VERSION
        ),
        "snapshot": _validate_dict_result(
            snapshot,
            operation="overview",
        ),
    }


@router.get(
    "/overall",
    dependencies=[
        Depends(
            signal_read_guard
        ),
    ],
)
def performance_overall(
    db: Session = Depends(
        get_db
    ),
) -> dict[str, Any]:
    """Return overall completed-signal performance."""

    try:
        performance = get_overall_performance(
            db
        )
    except SQLAlchemyError as error:
        _raise_database_error(
            "overall",
            error,
        )
    except Exception as error:
        logger.exception(
            "Signal overall performance failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to load overall signal performance.",
        ) from error

    return {
        "status": "success",
        "performance": _validate_dict_result(
            performance,
            operation="overall",
        ),
    }


@router.get(
    "/by-symbol",
    dependencies=[
        Depends(
            signal_read_guard
        ),
    ],
)
def performance_by_symbol(
    db: Session = Depends(
        get_db
    ),
) -> dict[str, Any]:
    """Return completed performance grouped by symbol."""

    try:
        rows = get_symbol_performance(
            db
        )
    except SQLAlchemyError as error:
        _raise_database_error(
            "by_symbol",
            error,
        )
    except Exception as error:
        logger.exception(
            "Signal symbol performance failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to load symbol performance.",
        ) from error

    resolved_rows = _validate_list_result(
        rows,
        operation="by_symbol",
    )

    return {
        "status": "success",
        "count": len(
            resolved_rows
        ),
        "performance": resolved_rows,
    }


@router.get(
    "/by-timeframe",
    dependencies=[
        Depends(
            signal_read_guard
        ),
    ],
)
def performance_by_timeframe(
    db: Session = Depends(
        get_db
    ),
) -> dict[str, Any]:
    """Return completed performance grouped by timeframe."""

    try:
        rows = get_timeframe_performance(
            db
        )
    except SQLAlchemyError as error:
        _raise_database_error(
            "by_timeframe",
            error,
        )
    except Exception as error:
        logger.exception(
            "Signal timeframe performance failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to load timeframe performance.",
        ) from error

    resolved_rows = _validate_list_result(
        rows,
        operation="by_timeframe",
    )

    return {
        "status": "success",
        "count": len(
            resolved_rows
        ),
        "performance": resolved_rows,
    }


@router.get(
    "/recent",
    dependencies=[
        Depends(
            signal_read_guard
        ),
    ],
)
def performance_recent(
    limit: int = Query(
        default=50,
        ge=1,
        le=MAXIMUM_RECENT_LIMIT,
    ),
    db: Session = Depends(
        get_db
    ),
) -> dict[str, Any]:
    """Return recent completed-signal history."""

    try:
        signals = get_recent_completed_signals(
            db,
            limit=limit,
        )
    except SQLAlchemyError as error:
        _raise_database_error(
            "recent",
            error,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                str(error)
                or "Invalid recent performance request."
            ),
        ) from error
    except Exception as error:
        logger.exception(
            "Recent signal performance failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to load recent completed signals.",
        ) from error

    resolved_signals = _validate_list_result(
        signals,
        operation="recent",
    )

    return {
        "status": "success",
        "count": len(
            resolved_signals
        ),
        "limit": limit,
        "signals": resolved_signals,
    }


__all__ = [
    "MAXIMUM_RECENT_LIMIT",
    "PERFORMANCE_API_VERSION",
    "performance_by_symbol",
    "performance_by_timeframe",
    "performance_home",
    "performance_overall",
    "performance_overview",
    "performance_recent",
    "router",
    "signal_read_guard",
]