from __future__ import annotations

from typing import Any, Final

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    status,
)

from app.core.permission_dependencies import (
    require_permission_dependency,
)
from app.models.role_permission import (
    PERMISSION_SYSTEM_MANAGE,
    PERMISSION_SYSTEM_READ,
)
from app.services.market_cache_service import (
    clear_market_cache,
    clear_symbol_cache,
    get_market_cache_stats,
    list_market_cache_entries,
    normalize_symbol,
    normalize_timeframe,
    remove_expired_market_cache,
)
from app.services.market_request_manager_service import (
    get_managed_market_data,
    get_market_request_statistics,
    reset_market_request_statistics,
)


CACHE_API_VERSION: Final[int] = 22
MAX_SYMBOL_LENGTH: Final[int] = 40
MAX_TIMEFRAME_LENGTH: Final[int] = 20


router = APIRouter(
    prefix="/cache",
    tags=["Market Cache - Version 22"],
)


def _normalise_symbol_or_422(
    symbol: str,
) -> str:
    try:
        return normalize_symbol(
            symbol
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail="Market symbol is invalid.",
        ) from exc


def _normalise_timeframe_or_422(
    timeframe: str,
) -> str:
    try:
        return normalize_timeframe(
            timeframe
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail="Market timeframe is invalid.",
        ) from exc


def _safe_non_negative_int(
    value: Any,
) -> int:
    try:
        return max(
            0,
            int(
                value
                or 0
            ),
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0


@router.get(
    "/",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_READ
            )
        )
    ],
)
async def cache_home() -> dict[str, Any]:
    """
    Return safe cache capability metadata.
    """

    return {
        "status": "ok",
        "cache_api_version": (
            CACHE_API_VERSION
        ),
        "market_cache_enabled": True,
        "request_manager_enabled": True,
        "broker_connection_enabled": False,
        "trade_execution_enabled": False,
        "permission_protected": True,
    }


@router.get(
    "/test",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_READ
            )
        )
    ],
)
async def test_cache_router() -> dict[str, Any]:
    """
    Confirm that the protected cache router is available.
    """

    return {
        "status": "success",
        "message": (
            "Market cache API is working."
        ),
        "version": CACHE_API_VERSION,
    }


@router.get(
    "/status",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_READ
            )
        )
    ],
)
async def get_cache_status() -> dict[str, Any]:
    """
    Return combined cache and request-manager statistics.
    """

    try:
        cache_stats = (
            get_market_cache_stats()
        )
        request_stats = (
            get_market_request_statistics()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Cache status is temporarily unavailable."
            ),
        ) from exc

    return {
        "status": "success",
        "cache": cache_stats,
        "request_manager": request_stats,
    }


@router.get(
    "/stats",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_READ
            )
        )
    ],
)
async def get_cache_statistics() -> dict[str, Any]:
    """
    Return detailed market-cache statistics.
    """

    try:
        statistics = (
            get_market_cache_stats()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Cache statistics are temporarily unavailable."
            ),
        ) from exc

    return {
        "status": "success",
        "data": statistics,
    }


@router.get(
    "/request-stats",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_READ
            )
        )
    ],
)
async def get_request_statistics() -> dict[str, Any]:
    """
    Return request-manager statistics.
    """

    try:
        statistics = (
            get_market_request_statistics()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Request statistics are temporarily unavailable."
            ),
        ) from exc

    return {
        "status": "success",
        "data": statistics,
    }


@router.get(
    "/entries",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_READ
            )
        )
    ],
)
async def get_cache_entries(
    include_expired: bool = Query(
        default=False,
    ),
) -> dict[str, Any]:
    """
    List protected market-cache entry metadata.
    """

    try:
        entries = (
            list_market_cache_entries(
                include_expired=(
                    include_expired
                ),
            )
        )
    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Cache entries are temporarily unavailable."
            ),
        ) from exc

    return {
        "status": "success",
        "count": len(
            entries
        ),
        "include_expired": (
            include_expired
        ),
        "entries": entries,
    }


@router.get(
    "/market/{symbol}",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_READ
            )
        )
    ],
)
async def get_market_data_through_cache(
    symbol: str = Path(
        ...,
        min_length=1,
        max_length=MAX_SYMBOL_LENGTH,
    ),
    timeframe: str = Query(
        default="H1",
        min_length=1,
        max_length=MAX_TIMEFRAME_LENGTH,
    ),
    force_refresh: bool = Query(
        default=False,
    ),
    allow_stale_on_error: bool = Query(
        default=True,
    ),
) -> dict[str, Any]:
    """
    Request market data through the managed cache layer.
    """

    normalized_symbol = (
        _normalise_symbol_or_422(
            symbol
        )
    )

    normalized_timeframe = (
        _normalise_timeframe_or_422(
            timeframe
        )
    )

    try:
        market_data = (
            await get_managed_market_data(
                symbol=normalized_symbol,
                timeframe=(
                    normalized_timeframe
                ),
                force_refresh=(
                    force_refresh
                ),
                allow_stale_on_error=(
                    allow_stale_on_error
                ),
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Managed market-data request is invalid."
            ),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Managed market data is temporarily unavailable."
            ),
        ) from exc

    return {
        "status": "success",
        "symbol": normalized_symbol,
        "timeframe": normalized_timeframe,
        "data": market_data,
    }


@router.delete(
    "/expired",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_MANAGE
            )
        )
    ],
)
async def delete_expired_cache_entries() -> dict[str, Any]:
    """
    Remove expired cache entries.
    """

    try:
        removed_count = (
            remove_expired_market_cache()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Expired cache entries could not be removed."
            ),
        ) from exc

    return {
        "status": "success",
        "message": (
            "Expired cache entries removed."
        ),
        "removed_count": (
            _safe_non_negative_int(
                removed_count
            )
        ),
    }


@router.delete(
    "/symbol/{symbol}",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_MANAGE
            )
        )
    ],
)
async def delete_symbol_cache(
    symbol: str = Path(
        ...,
        min_length=1,
        max_length=MAX_SYMBOL_LENGTH,
    ),
) -> dict[str, Any]:
    """
    Remove every cached timeframe for one symbol.
    """

    normalized_symbol = (
        _normalise_symbol_or_422(
            symbol
        )
    )

    try:
        removed_count = (
            clear_symbol_cache(
                normalized_symbol
            )
        )
    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Symbol cache could not be cleared."
            ),
        ) from exc

    return {
        "status": "success",
        "message": (
            "Symbol cache cleared."
        ),
        "symbol": normalized_symbol,
        "removed_count": (
            _safe_non_negative_int(
                removed_count
            )
        ),
    }


@router.delete(
    "/all",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_MANAGE
            )
        )
    ],
)
async def delete_all_cache_entries() -> dict[str, Any]:
    """
    Clear the complete in-memory market cache.
    """

    try:
        removed_count = (
            clear_market_cache()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Market cache could not be cleared."
            ),
        ) from exc

    return {
        "status": "success",
        "message": (
            "All market cache entries cleared."
        ),
        "removed_count": (
            _safe_non_negative_int(
                removed_count
            )
        ),
    }


@router.post(
    "/reset-request-stats",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_MANAGE
            )
        )
    ],
)
async def reset_request_statistics() -> dict[str, Any]:
    """
    Reset request-manager counters without clearing cached data.
    """

    try:
        reset_market_request_statistics()

        statistics = (
            get_market_request_statistics()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Request-manager statistics could not be reset."
            ),
        ) from exc

    return {
        "status": "success",
        "message": (
            "Request-manager statistics reset."
        ),
        "request_manager": statistics,
    }


__all__ = [
    "CACHE_API_VERSION",
    "MAX_SYMBOL_LENGTH",
    "MAX_TIMEFRAME_LENGTH",
    "router",
]