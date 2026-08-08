from __future__ import annotations

from typing import Final, Literal, TypedDict

from fastapi import APIRouter
from fastapi.responses import JSONResponse


HEALTH_API_VERSION: Final[int] = 2


class HealthResponse(TypedDict):
    status: Literal["healthy"]
    service: str
    version: int


router = APIRouter(
    tags=["Health"],
)


@router.get(
    "/health",
    response_model=None,
    include_in_schema=True,
)
def health_check() -> JSONResponse:
    """
    Return a minimal public liveness response.

    This endpoint confirms only that the FastAPI process is running.
    Database, cache, worker, and external-service checks belong in
    protected readiness or monitoring endpoints.
    """

    payload: HealthResponse = {
        "status": "healthy",
        "service": "blue-trading-ai-backend",
        "version": HEALTH_API_VERSION,
    }

    return JSONResponse(
        status_code=200,
        content=payload,
        headers={
            "Cache-Control": (
                "no-store, max-age=0"
            ),
        },
    )


__all__ = [
    "HEALTH_API_VERSION",
    "HealthResponse",
    "health_check",
    "router",
]