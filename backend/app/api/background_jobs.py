from __future__ import annotations

import re
from datetime import datetime, timezone
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
from sqlalchemy.orm import Session

from app.core.permission_dependencies import (
    require_permission_dependency,
)
from app.database.connection import get_db
from app.models.background_job import (
    JOB_TYPE_LEARNING_REFRESH,
    JOB_TYPE_MARKET_REFRESH,
    JOB_TYPE_SIGNAL_EXPIRY,
    JOB_TYPE_SIGNAL_GENERATION,
)
from app.models.role_permission import (
    PERMISSION_SIGNAL_CREATE,
    PERMISSION_SIGNAL_MANAGE,
    PERMISSION_SYSTEM_MANAGE,
    PERMISSION_SYSTEM_READ,
)
from app.services.background_job_service import (
    BackgroundJobStateError,
    BackgroundJobValidationError,
    cancel_job,
    enqueue_job,
    get_job_by_uid,
    job_public_payload,
    jobs_public_payload,
    list_jobs,
    requeue_job,
)
from app.services.background_worker import (
    run_worker_once,
)


BACKGROUND_API_VERSION = 46
MAX_BACKGROUND_JOB_OFFSET: Final[int] = 100_000
MAX_JOB_UID_LENGTH: Final[int] = 64
MAX_PAYLOAD_KEYS: Final[int] = 100

JOB_UID_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$"
)

SUPPORTED_JOB_TYPES: Final[set[str]] = {
    JOB_TYPE_MARKET_REFRESH,
    JOB_TYPE_SIGNAL_GENERATION,
    JOB_TYPE_SIGNAL_EXPIRY,
    JOB_TYPE_LEARNING_REFRESH,
}


router = APIRouter(
    prefix="/background-jobs",
    tags=["Background Processing - Version 46"],
)


def _normalise_utc_datetime(
    value: datetime | None,
) -> datetime | None:
    """
    Normalize one optional timestamp to timezone-aware UTC.
    """

    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


def _clean_optional_text(
    value: str | None,
    *,
    maximum_length: int,
    upper: bool = False,
) -> str | None:
    if value is None:
        return None

    cleaned = "".join(
        character
        if character.isprintable()
        and character not in {
            "\r",
            "\n",
            "\t",
        }
        else " "
        for character in str(value)
    ).strip()[:maximum_length]

    if not cleaned:
        return None

    return (
        cleaned.upper()
        if upper
        else cleaned
    )


def _normalise_job_uid(
    value: str,
) -> str:
    resolved = str(
        value or ""
    ).strip()

    if (
        not resolved
        or len(resolved)
        > MAX_JOB_UID_LENGTH
        or not JOB_UID_PATTERN.fullmatch(
            resolved
        )
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Background job identifier is invalid."
            ),
        )

    return resolved


class BackgroundJobCreateRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    job_type: str = Field(
        ...,
        min_length=3,
        max_length=40,
    )

    symbol: str | None = Field(
        default=None,
        max_length=40,
    )

    timeframe: str | None = Field(
        default=None,
        max_length=20,
    )

    payload: dict[str, Any] | None = None

    scheduled_at: datetime | None = None

    max_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
    )

    priority: int = Field(
        default=100,
        ge=1,
        le=1000,
    )

    is_recurring: bool = False

    @field_validator("job_type")
    @classmethod
    def validate_job_type(
        cls,
        value: str,
    ) -> str:
        resolved = _clean_optional_text(
            value,
            maximum_length=40,
            upper=True,
        )

        if (
            resolved is None
            or resolved
            not in SUPPORTED_JOB_TYPES
        ):
            raise ValueError(
                "Unsupported background job type."
            )

        return resolved

    @field_validator("symbol")
    @classmethod
    def validate_symbol(
        cls,
        value: str | None,
    ) -> str | None:
        return _clean_optional_text(
            value,
            maximum_length=40,
            upper=True,
        )

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(
        cls,
        value: str | None,
    ) -> str | None:
        return _clean_optional_text(
            value,
            maximum_length=20,
        )

    @field_validator("scheduled_at")
    @classmethod
    def validate_scheduled_at(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        return _normalise_utc_datetime(
            value
        )

    @field_validator("payload")
    @classmethod
    def validate_payload(
        cls,
        value: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if value is None:
            return None

        if len(value) > MAX_PAYLOAD_KEYS:
            raise ValueError(
                "Background job payload contains too many fields."
            )

        return value


class BackgroundJobRequeueRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    scheduled_at: datetime | None = None
    reset_attempts: bool = False

    @field_validator("scheduled_at")
    @classmethod
    def validate_scheduled_at(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        return _normalise_utc_datetime(
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
def background_api_home() -> dict[str, Any]:
    return {
        "status": "ok",
        "background_api_version": (
            BACKGROUND_API_VERSION
        ),
        "persistent_queue_enabled": True,
        "worker_heartbeat_enabled": True,
        "automatic_retry_enabled": True,
        "stalled_job_recovery_enabled": True,
        "broker_execution_enabled": False,
        "permission_protected": True,
        "supported_job_types": sorted(
            SUPPORTED_JOB_TYPES
        ),
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
def create_background_job(
    payload: BackgroundJobCreateRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        job = enqueue_job(
            db,
            job_type=payload.job_type,
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            payload=payload.payload,
            scheduled_at=payload.scheduled_at,
            max_attempts=payload.max_attempts,
            priority=payload.priority,
            is_recurring=payload.is_recurring,
            commit=True,
        )
    except BackgroundJobValidationError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(exc),
        ) from exc

    return {
        "status": "success",
        "message": (
            "Background job queued successfully."
        ),
        "job": job_public_payload(
            job
        ),
    }


@router.get(
    "/list",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_READ
            )
        )
    ],
)
def get_background_jobs(
    job_type: str | None = Query(
        default=None,
        max_length=40,
    ),
    job_status: str | None = Query(
        default=None,
        alias="status",
        max_length=30,
    ),
    symbol: str | None = Query(
        default=None,
        max_length=40,
    ),
    timeframe: str | None = Query(
        default=None,
        max_length=20,
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
    offset: int = Query(
        default=0,
        ge=0,
        le=MAX_BACKGROUND_JOB_OFFSET,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        jobs = list_jobs(
            db,
            job_type=(
                _clean_optional_text(
                    job_type,
                    maximum_length=40,
                    upper=True,
                )
            ),
            status=(
                _clean_optional_text(
                    job_status,
                    maximum_length=30,
                    upper=True,
                )
            ),
            symbol=(
                _clean_optional_text(
                    symbol,
                    maximum_length=40,
                    upper=True,
                )
            ),
            timeframe=(
                _clean_optional_text(
                    timeframe,
                    maximum_length=20,
                )
            ),
            limit=limit,
            offset=offset,
        )
    except BackgroundJobValidationError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(exc),
        ) from exc

    return {
        "status": "success",
        "count": len(jobs),
        "limit": limit,
        "offset": offset,
        "jobs": jobs_public_payload(
            jobs
        ),
    }


@router.get(
    "/{job_uid}",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_READ
            )
        )
    ],
)
def get_background_job(
    job_uid: str = Path(
        ...,
        min_length=1,
        max_length=MAX_JOB_UID_LENGTH,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    resolved_uid = _normalise_job_uid(
        job_uid
    )

    job = get_job_by_uid(
        db,
        job_uid=resolved_uid,
    )

    if job is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Background job does not exist."
            ),
        )

    return {
        "status": "success",
        "job": job_public_payload(
            job
        ),
    }


@router.post(
    "/{job_uid}/cancel",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SIGNAL_MANAGE
            )
        )
    ],
)
def cancel_background_job(
    job_uid: str = Path(
        ...,
        min_length=1,
        max_length=MAX_JOB_UID_LENGTH,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    resolved_uid = _normalise_job_uid(
        job_uid
    )

    job = get_job_by_uid(
        db,
        job_uid=resolved_uid,
    )

    if (
        job is None
        or job.id is None
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Background job does not exist."
            ),
        )

    try:
        updated = cancel_job(
            db,
            job_id=int(job.id),
            commit=True,
        )
    except BackgroundJobStateError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=str(exc),
        ) from exc
    except BackgroundJobValidationError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(exc),
        ) from exc

    return {
        "status": "success",
        "message": (
            "Background job cancelled."
        ),
        "job": job_public_payload(
            updated
        ),
    }


@router.post(
    "/{job_uid}/requeue",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SIGNAL_MANAGE
            )
        )
    ],
)
def requeue_background_job(
    payload: BackgroundJobRequeueRequest,
    job_uid: str = Path(
        ...,
        min_length=1,
        max_length=MAX_JOB_UID_LENGTH,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    resolved_uid = _normalise_job_uid(
        job_uid
    )

    job = get_job_by_uid(
        db,
        job_uid=resolved_uid,
    )

    if (
        job is None
        or job.id is None
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Background job does not exist."
            ),
        )

    try:
        updated = requeue_job(
            db,
            job_id=int(job.id),
            scheduled_at=(
                payload.scheduled_at
            ),
            reset_attempts=(
                payload.reset_attempts
            ),
            commit=True,
        )
    except BackgroundJobStateError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=str(exc),
        ) from exc
    except BackgroundJobValidationError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(exc),
        ) from exc

    return {
        "status": "success",
        "message": (
            "Background job requeued."
        ),
        "job": job_public_payload(
            updated
        ),
    }


@router.post(
    "/process-one",
    dependencies=[
        Depends(
            require_permission_dependency(
                PERMISSION_SYSTEM_MANAGE
            )
        )
    ],
)
async def process_one_background_job() -> dict[str, Any]:
    """
    Manually process at most one due background job.
    """

    try:
        processed = await run_worker_once()
    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "The background worker could not process a job."
            ),
        ) from exc

    if processed is None:
        return {
            "status": "success",
            "message": (
                "No due background jobs were available."
            ),
            "processed": False,
            "job": None,
        }

    return {
        "status": "success",
        "message": (
            "Background job processed."
        ),
        "processed": True,
        "job": job_public_payload(
            processed
        ),
    }


__all__ = [
    "BACKGROUND_API_VERSION",
    "BackgroundJobCreateRequest",
    "BackgroundJobRequeueRequest",
    "JOB_UID_PATTERN",
    "MAX_BACKGROUND_JOB_OFFSET",
    "MAX_JOB_UID_LENGTH",
    "SUPPORTED_JOB_TYPES",
    "router",
]