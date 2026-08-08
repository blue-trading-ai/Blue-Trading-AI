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
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.core.permission_dependencies import (
    require_permission_dependency,
)
from app.models.role_permission import (
    PERMISSION_SYSTEM_MANAGE,
    PERMISSION_SYSTEM_READ,
)
from app.services.market_cache_refresh_service import (
    DEFAULT_REFRESH_BEFORE_EXPIRY_SECONDS,
    get_market_cache_refresh_status,
    list_market_cache_refresh_subscriptions,
    market_cache_refresh_service,
    register_market_cache_refresh,
    run_market_cache_refresh_cycle,
    start_market_cache_refresh_service,
    stop_market_cache_refresh_service,
    unregister_market_cache_refresh,
)
from app.services.market_cache_service import (
    MAX_SYMBOL_LENGTH,
    normalize_symbol,
    normalize_timeframe,
)


CACHE_REFRESH_API_VERSION: Final[int] = 22
MAX_TIMEFRAME_LENGTH: Final[int] = 20
MAX_REFRESH_BEFORE_EXPIRY_SECONDS: Final[int] = 86_400


router = APIRouter(
    prefix="/cache-refresh",
    tags=["Cache Refresh - Version 22"],
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


class RefreshSubscriptionRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    symbol: str = Field(
        ...,
        min_length=1,
        max_length=MAX_SYMBOL_LENGTH,
    )

    timeframe: str = Field(
        default="H1",
        min_length=1,
        max_length=MAX_TIMEFRAME_LENGTH,
    )

    refresh_before_expiry_seconds: int = Field(
        default=(
            DEFAULT_REFRESH_BEFORE_EXPIRY_SECONDS
        ),
        ge=0,
        le=MAX_REFRESH_BEFORE_EXPIRY_SECONDS,
    )

    enabled: bool = True

    @field_validator("symbol")
    @classmethod
    def validate_symbol(
        cls,
        value: str,
    ) -> str:
        return normalize_symbol(
            value
        )

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(
        cls,
        value: str,
    ) -> str:
        return normalize_timeframe(
            value
        )


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
async def cache_refresh_home() -> dict[str, Any]:
    """
    Return safe cache-refresh capability metadata.
    """

    return {
        "status": "ok",
        "cache_refresh_api_version": (
            CACHE_REFRESH_API_VERSION
        ),
        "automatic_refresh_enabled": True,
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
async def test_cache_refresh_router() -> dict[str, Any]:
    """
    Confirm that the protected cache-refresh router is available.
    """

    return {
        "status": "success",
        "message": (
            "Cache-refresh API is working."
        ),
        "version": CACHE_REFRESH_API_VERSION,
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
async def get_refresh_status() -> dict[str, Any]:
    """
    Return protected cache-refresh service statistics.
    """

    try:
        service_status = (
            get_market_cache_refresh_status()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Cache-refresh status is temporarily unavailable."
            ),
        ) from exc

    return {
        "status": "success",
        "data": service_status,
    }


@router.get(
    "/subscriptions",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_READ
            )
        )
    ],
)
async def get_refresh_subscriptions() -> dict[str, Any]:
    """
    List protected cache-refresh subscriptions.
    """

    try:
        subscriptions = (
            list_market_cache_refresh_subscriptions()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Refresh subscriptions are temporarily unavailable."
            ),
        ) from exc

    return {
        "status": "success",
        "count": len(
            subscriptions
        ),
        "subscriptions": subscriptions,
    }


@router.post(
    "/subscriptions",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_MANAGE
            )
        )
    ],
)
async def create_refresh_subscription(
    request: RefreshSubscriptionRequest,
) -> dict[str, Any]:
    """
    Register a symbol and timeframe for automatic refreshing.
    """

    try:
        subscription = (
            register_market_cache_refresh(
                symbol=request.symbol,
                timeframe=request.timeframe,
                refresh_before_expiry_seconds=(
                    request.refresh_before_expiry_seconds
                ),
                enabled=request.enabled,
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Refresh subscription is invalid."
            ),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Refresh subscription could not be registered."
            ),
        ) from exc

    return {
        "status": "success",
        "message": (
            "Refresh subscription registered."
        ),
        "subscription": subscription,
    }


@router.delete(
    "/subscriptions/{symbol}/{timeframe}",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_MANAGE
            )
        )
    ],
)
async def delete_refresh_subscription(
    symbol: str = Path(
        ...,
        min_length=1,
        max_length=MAX_SYMBOL_LENGTH,
    ),
    timeframe: str = Path(
        ...,
        min_length=1,
        max_length=MAX_TIMEFRAME_LENGTH,
    ),
) -> dict[str, Any]:
    """
    Remove one automatic refresh subscription.
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
        removed = (
            unregister_market_cache_refresh(
                symbol=normalized_symbol,
                timeframe=normalized_timeframe,
            )
        )
    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Refresh subscription could not be removed."
            ),
        ) from exc

    if not removed:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Refresh subscription was not found."
            ),
        )

    return {
        "status": "success",
        "message": (
            "Refresh subscription removed."
        ),
        "symbol": normalized_symbol,
        "timeframe": normalized_timeframe,
    }


@router.delete(
    "/subscriptions/symbol/{symbol}",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_MANAGE
            )
        )
    ],
)
async def delete_symbol_refresh_subscriptions(
    symbol: str = Path(
        ...,
        min_length=1,
        max_length=MAX_SYMBOL_LENGTH,
    ),
) -> dict[str, Any]:
    """
    Remove all refresh subscriptions for one symbol.
    """

    normalized_symbol = (
        _normalise_symbol_or_422(
            symbol
        )
    )

    try:
        removed_count = (
            market_cache_refresh_service.unregister_symbol(
                normalized_symbol
            )
        )
    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Symbol refresh subscriptions could not be removed."
            ),
        ) from exc

    return {
        "status": "success",
        "message": (
            "Symbol refresh subscriptions removed."
        ),
        "symbol": normalized_symbol,
        "removed_count": (
            _safe_non_negative_int(
                removed_count
            )
        ),
    }


@router.delete(
    "/subscriptions",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_MANAGE
            )
        )
    ],
)
async def delete_all_refresh_subscriptions() -> dict[str, Any]:
    """
    Remove every automatic cache-refresh subscription.
    """

    try:
        removed_count = (
            market_cache_refresh_service.clear_subscriptions()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Refresh subscriptions could not be cleared."
            ),
        ) from exc

    return {
        "status": "success",
        "message": (
            "All refresh subscriptions removed."
        ),
        "removed_count": (
            _safe_non_negative_int(
                removed_count
            )
        ),
    }


@router.patch(
    "/subscriptions/{symbol}/{timeframe}/enable",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_MANAGE
            )
        )
    ],
)
async def enable_refresh_subscription(
    symbol: str = Path(
        ...,
        min_length=1,
        max_length=MAX_SYMBOL_LENGTH,
    ),
    timeframe: str = Path(
        ...,
        min_length=1,
        max_length=MAX_TIMEFRAME_LENGTH,
    ),
) -> dict[str, Any]:
    """
    Enable an existing refresh subscription.
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
        enabled = (
            market_cache_refresh_service.enable(
                normalized_symbol,
                normalized_timeframe,
            )
        )
    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Refresh subscription could not be enabled."
            ),
        ) from exc

    if not enabled:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Refresh subscription was not found."
            ),
        )

    return {
        "status": "success",
        "message": (
            "Refresh subscription enabled."
        ),
        "symbol": normalized_symbol,
        "timeframe": normalized_timeframe,
    }


@router.patch(
    "/subscriptions/{symbol}/{timeframe}/disable",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_MANAGE
            )
        )
    ],
)
async def disable_refresh_subscription(
    symbol: str = Path(
        ...,
        min_length=1,
        max_length=MAX_SYMBOL_LENGTH,
    ),
    timeframe: str = Path(
        ...,
        min_length=1,
        max_length=MAX_TIMEFRAME_LENGTH,
    ),
) -> dict[str, Any]:
    """
    Disable an existing refresh subscription.
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
        disabled = (
            market_cache_refresh_service.disable(
                normalized_symbol,
                normalized_timeframe,
            )
        )
    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Refresh subscription could not be disabled."
            ),
        ) from exc

    if not disabled:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Refresh subscription was not found."
            ),
        )

    return {
        "status": "success",
        "message": (
            "Refresh subscription disabled."
        ),
        "symbol": normalized_symbol,
        "timeframe": normalized_timeframe,
    }


@router.post(
    "/cycle",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_MANAGE
            )
        )
    ],
)
async def execute_refresh_cycle() -> dict[str, Any]:
    """
    Run one cache-refresh cycle immediately.
    """

    try:
        result = await (
            run_market_cache_refresh_cycle()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Cache-refresh cycle could not be completed."
            ),
        ) from exc

    if not isinstance(
        result,
        dict,
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Cache-refresh cycle returned an invalid result."
            ),
        )

    return result


@router.post(
    "/refresh/{symbol}/{timeframe}",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_MANAGE
            )
        )
    ],
)
async def refresh_one_subscription(
    symbol: str = Path(
        ...,
        min_length=1,
        max_length=MAX_SYMBOL_LENGTH,
    ),
    timeframe: str = Path(
        ...,
        min_length=1,
        max_length=MAX_TIMEFRAME_LENGTH,
    ),
    force_refresh: bool = Query(
        default=True,
    ),
) -> dict[str, Any]:
    """
    Refresh one registered subscription immediately.
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

    subscription = (
        market_cache_refresh_service.get_subscription(
            normalized_symbol,
            normalized_timeframe,
        )
    )

    if subscription is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Refresh subscription was not found."
            ),
        )

    try:
        result = await (
            market_cache_refresh_service.refresh_subscription(
                subscription,
                force_refresh=force_refresh,
            )
        )
    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Subscription refresh could not be completed."
            ),
        ) from exc

    if not isinstance(
        result,
        dict,
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Subscription refresh returned an invalid result."
            ),
        )

    if str(
        result.get(
            "status",
            "",
        )
    ).strip().lower() == "failed":
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Subscription refresh failed."
            ),
        )

    return result


@router.post(
    "/service/start",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_MANAGE
            )
        )
    ],
)
async def start_refresh_service() -> dict[str, Any]:
    """
    Start the background refresh service manually.
    """

    try:
        started = await (
            start_market_cache_refresh_service()
        )

        service_status = (
            get_market_cache_refresh_status()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Cache-refresh service could not be started."
            ),
        ) from exc

    return {
        "status": "success",
        "started": bool(
            started
        ),
        "message": (
            "Cache-refresh service started."
            if started
            else (
                "Cache-refresh service is already running."
            )
        ),
        "service": service_status,
    }


@router.post(
    "/service/stop",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_MANAGE
            )
        )
    ],
)
async def stop_refresh_service() -> dict[str, Any]:
    """
    Stop the background refresh service manually.
    """

    try:
        stopped = await (
            stop_market_cache_refresh_service()
        )

        service_status = (
            get_market_cache_refresh_status()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Cache-refresh service could not be stopped."
            ),
        ) from exc

    return {
        "status": "success",
        "stopped": bool(
            stopped
        ),
        "message": (
            "Cache-refresh service stopped."
            if stopped
            else (
                "Cache-refresh service is already stopped."
            )
        ),
        "service": service_status,
    }


__all__ = [
    "CACHE_REFRESH_API_VERSION",
    "MAX_REFRESH_BEFORE_EXPIRY_SECONDS",
    "MAX_TIMEFRAME_LENGTH",
    "RefreshSubscriptionRequest",
    "router",
]