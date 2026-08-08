from __future__ import annotations

import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Final, Iterable

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.background_job import (
    BackgroundJob,
    JOB_STATUS_CANCELLED,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_PENDING,
    JOB_STATUS_RETRY_WAIT,
    JOB_STATUS_RUNNING,
    MAX_ATTEMPTS,
    MAX_DURATION_MS,
    MAX_PRIORITY,
    TERMINAL_JOB_STATUSES,
    VALID_JOB_STATUSES,
    VALID_JOB_TYPES,
)


DEFAULT_MAX_ATTEMPTS: Final[int] = 3
DEFAULT_PRIORITY: Final[int] = 100
DEFAULT_RETRY_DELAY_SECONDS: Final[int] = 60
DEFAULT_STALLED_AFTER_SECONDS: Final[int] = 300

MAX_RETRY_DELAY_SECONDS: Final[int] = 86_400
MAX_STALLED_AFTER_SECONDS: Final[int] = 86_400
MAX_LIST_LIMIT: Final[int] = 500
MAX_LIST_OFFSET: Final[int] = 100_000
MAX_RECOVERY_BATCH: Final[int] = 500
MAX_JOB_UID_LENGTH: Final[int] = 64
MAX_PAYLOAD_KEYS: Final[int] = 100

JOB_UID_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$"
)


class BackgroundJobError(Exception):
    """Base exception for background-job failures."""


class BackgroundJobNotFoundError(
    BackgroundJobError
):
    pass


class BackgroundJobValidationError(
    BackgroundJobError
):
    pass


class BackgroundJobStateError(
    BackgroundJobError
):
    pass


def utc_now() -> datetime:
    """Return one timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def _as_utc(
    value: datetime | None,
) -> datetime | None:
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


def _bounded_int(
    value: Any,
    *,
    field_name: str,
    minimum: int,
    maximum: int,
) -> int:
    try:
        resolved = int(value)
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise BackgroundJobValidationError(
            f"{field_name} must be an integer."
        ) from exc

    if not minimum <= resolved <= maximum:
        raise BackgroundJobValidationError(
            f"{field_name} must be between "
            f"{minimum} and {maximum}."
        )

    return resolved


def _normalise_uid(
    value: str,
) -> str:
    resolved = str(
        value or ""
    ).strip()

    if (
        not resolved
        or len(resolved) > MAX_JOB_UID_LENGTH
        or not JOB_UID_PATTERN.fullmatch(
            resolved
        )
    ):
        raise BackgroundJobValidationError(
            "Background job UID is invalid."
        )

    return resolved


def _normalise_symbol(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    resolved = str(
        value
    ).strip().upper()[:40]

    return resolved or None


def _normalise_timeframe(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    resolved = str(
        value
    ).strip()[:20]

    return resolved or None


def _validate_payload(
    payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if payload is None:
        return None

    if not isinstance(
        payload,
        dict,
    ):
        raise BackgroundJobValidationError(
            "Background job payload must be an object."
        )

    if len(payload) > MAX_PAYLOAD_KEYS:
        raise BackgroundJobValidationError(
            "Background job payload contains too many fields."
        )

    return payload


def _commit_or_flush(
    db: Session,
    *,
    commit: bool,
    refresh: BackgroundJob | None = None,
) -> None:
    try:
        if commit:
            db.commit()

            if refresh is not None:
                db.refresh(
                    refresh
                )
        else:
            db.flush()
    except Exception:
        db.rollback()
        raise


def _duration_ms(
    started_monotonic: float | None,
) -> int | None:
    if started_monotonic is None:
        return None

    try:
        elapsed = (
            time.monotonic()
            - float(
                started_monotonic
            )
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise BackgroundJobValidationError(
            "started_monotonic is invalid."
        ) from exc

    return min(
        MAX_DURATION_MS,
        max(
            0,
            int(
                elapsed * 1000
            ),
        ),
    )


def generate_job_uid() -> str:
    """
    Generate one random public background-job identifier.
    """

    token = secrets.token_hex(
        20
    ).upper()

    return f"JOB-{token}"


def normalise_job_type(
    job_type: str,
) -> str:
    resolved = str(
        job_type or ""
    ).strip().upper()

    if resolved not in VALID_JOB_TYPES:
        raise BackgroundJobValidationError(
            "Background job type is invalid."
        )

    return resolved


def normalise_job_status(
    job_status: str,
) -> str:
    resolved = str(
        job_status or ""
    ).strip().upper()

    if resolved not in VALID_JOB_STATUSES:
        raise BackgroundJobValidationError(
            "Background job status is invalid."
        )

    return resolved


def enqueue_job(
    db: Session,
    *,
    job_type: str,
    symbol: str | None = None,
    timeframe: str | None = None,
    payload: dict[str, Any] | None = None,
    scheduled_at: datetime | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    priority: int = DEFAULT_PRIORITY,
    is_recurring: bool = False,
    job_uid: str | None = None,
    commit: bool = True,
) -> BackgroundJob:
    """
    Persist one background job in PENDING state.
    """

    resolved_type = normalise_job_type(
        job_type
    )

    resolved_uid = _normalise_uid(
        job_uid
        or generate_job_uid()
    )

    resolved_max_attempts = _bounded_int(
        max_attempts,
        field_name="Maximum attempts",
        minimum=1,
        maximum=MAX_ATTEMPTS,
    )

    resolved_priority = _bounded_int(
        priority,
        field_name="Priority",
        minimum=1,
        maximum=MAX_PRIORITY,
    )

    resolved_schedule = (
        _as_utc(
            scheduled_at
        )
        or utc_now()
    )

    resolved_payload = _validate_payload(
        payload
    )

    job = BackgroundJob(
        job_uid=resolved_uid,
        job_type=resolved_type,
        status=JOB_STATUS_PENDING,
        symbol=_normalise_symbol(
            symbol
        ),
        timeframe=_normalise_timeframe(
            timeframe
        ),
        payload=resolved_payload,
        result_payload=None,
        error_message=None,
        attempt_count=0,
        max_attempts=resolved_max_attempts,
        priority=resolved_priority,
        is_recurring=bool(
            is_recurring
        ),
        scheduled_at=resolved_schedule,
    )

    try:
        job.validate_state()
    except ValueError as exc:
        raise BackgroundJobValidationError(
            str(exc)
        ) from exc

    db.add(
        job
    )

    try:
        _commit_or_flush(
            db,
            commit=commit,
            refresh=job,
        )
    except IntegrityError as exc:
        raise BackgroundJobValidationError(
            "Background job UID already exists."
        ) from exc

    return job


def get_job_by_id(
    db: Session,
    *,
    job_id: int,
) -> BackgroundJob | None:
    resolved_id = _bounded_int(
        job_id,
        field_name="Job ID",
        minimum=1,
        maximum=2_147_483_647,
    )

    return (
        db.query(
            BackgroundJob
        )
        .filter(
            BackgroundJob.id
            == resolved_id
        )
        .first()
    )


def get_job_by_uid(
    db: Session,
    *,
    job_uid: str,
) -> BackgroundJob | None:
    resolved_uid = _normalise_uid(
        job_uid
    )

    return (
        db.query(
            BackgroundJob
        )
        .filter(
            BackgroundJob.job_uid
            == resolved_uid
        )
        .first()
    )


def require_job(
    db: Session,
    *,
    job_id: int | None = None,
    job_uid: str | None = None,
) -> BackgroundJob:
    if job_id is not None:
        job = get_job_by_id(
            db,
            job_id=job_id,
        )
    elif job_uid is not None:
        job = get_job_by_uid(
            db,
            job_uid=job_uid,
        )
    else:
        raise BackgroundJobValidationError(
            "Job ID or job UID is required."
        )

    if job is None:
        raise BackgroundJobNotFoundError(
            "Background job does not exist."
        )

    return job


def list_jobs(
    db: Session,
    *,
    job_type: str | None = None,
    status: str | None = None,
    symbol: str | None = None,
    timeframe: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[BackgroundJob]:
    """
    Return filtered background-job history.
    """

    query = db.query(
        BackgroundJob
    )

    if job_type:
        query = query.filter(
            BackgroundJob.job_type
            == normalise_job_type(
                job_type
            )
        )

    if status:
        query = query.filter(
            BackgroundJob.status
            == normalise_job_status(
                status
            )
        )

    resolved_symbol = _normalise_symbol(
        symbol
    )

    if resolved_symbol:
        query = query.filter(
            BackgroundJob.symbol
            == resolved_symbol
        )

    resolved_timeframe = _normalise_timeframe(
        timeframe
    )

    if resolved_timeframe:
        query = query.filter(
            BackgroundJob.timeframe
            == resolved_timeframe
        )

    resolved_limit = _bounded_int(
        limit,
        field_name="Limit",
        minimum=1,
        maximum=MAX_LIST_LIMIT,
    )

    resolved_offset = _bounded_int(
        offset,
        field_name="Offset",
        minimum=0,
        maximum=MAX_LIST_OFFSET,
    )

    return (
        query.order_by(
            BackgroundJob.created_at.desc(),
            BackgroundJob.id.desc(),
        )
        .offset(
            resolved_offset
        )
        .limit(
            resolved_limit
        )
        .all()
    )


def claim_next_job(
    db: Session,
    *,
    worker_name: str,
    allowed_job_types: Iterable[str] | None = None,
    now: datetime | None = None,
    commit: bool = True,
) -> BackgroundJob | None:
    """
    Claim the next due PENDING or RETRY_WAIT job.

    Row locking protects supported production databases. SQLite does
    not provide equivalent row-level locking, so production workers
    must use a supported production database.
    """

    resolved_now = (
        _as_utc(
            now
        )
        or utc_now()
    )

    query = (
        db.query(
            BackgroundJob
        )
        .filter(
            or_(
                (
                    BackgroundJob.status
                    == JOB_STATUS_PENDING
                )
                & (
                    BackgroundJob.scheduled_at
                    <= resolved_now
                ),
                (
                    BackgroundJob.status
                    == JOB_STATUS_RETRY_WAIT
                )
                & (
                    BackgroundJob.retry_at
                    <= resolved_now
                ),
            )
        )
    )

    if allowed_job_types is not None:
        resolved_types = list(
            dict.fromkeys(
                normalise_job_type(
                    job_type
                )
                for job_type in allowed_job_types
            )
        )

        if not resolved_types:
            return None

        query = query.filter(
            BackgroundJob.job_type.in_(
                resolved_types
            )
        )

    try:
        job = (
            query.order_by(
                BackgroundJob.priority.asc(),
                BackgroundJob.scheduled_at.asc(),
                BackgroundJob.id.asc(),
            )
            .with_for_update(
                skip_locked=True
            )
            .first()
        )
    except Exception:
        db.rollback()
        raise

    if job is None:
        return None

    if int(
        job.attempt_count or 0
    ) >= int(
        job.max_attempts or 1
    ):
        job.status = JOB_STATUS_FAILED
        job.error_message = (
            "Maximum retry attempts reached."
        )
        job.finished_at = resolved_now
        job.retry_at = None
        job.updated_at = resolved_now

        _commit_or_flush(
            db,
            commit=commit,
            refresh=job,
        )

        return None

    try:
        job.mark_running(
            worker_name=worker_name
        )
    except ValueError as exc:
        raise BackgroundJobStateError(
            str(exc)
        ) from exc

    _commit_or_flush(
        db,
        commit=commit,
        refresh=job,
    )

    return job


def heartbeat_job(
    db: Session,
    *,
    job_id: int,
    worker_name: str | None = None,
    commit: bool = True,
) -> BackgroundJob:
    """
    Refresh a RUNNING job heartbeat.
    """

    job = require_job(
        db,
        job_id=job_id,
    )

    if (
        job.status
        != JOB_STATUS_RUNNING
    ):
        raise BackgroundJobStateError(
            "Only RUNNING jobs can receive heartbeats."
        )

    if (
        worker_name is not None
        and job.worker_name
        and str(
            worker_name
        ).strip()
        != job.worker_name
    ):
        raise BackgroundJobStateError(
            "Worker name does not match the claimed job."
        )

    try:
        job.touch_heartbeat()
    except ValueError as exc:
        raise BackgroundJobStateError(
            str(exc)
        ) from exc

    _commit_or_flush(
        db,
        commit=commit,
        refresh=job,
    )

    return job


def complete_job(
    db: Session,
    *,
    job_id: int,
    result_payload: dict[str, Any] | None = None,
    started_monotonic: float | None = None,
    commit: bool = True,
) -> BackgroundJob:
    """
    Complete one RUNNING background job.
    """

    job = require_job(
        db,
        job_id=job_id,
    )

    if (
        job.status
        != JOB_STATUS_RUNNING
    ):
        raise BackgroundJobStateError(
            "Only RUNNING jobs can be completed."
        )

    resolved_result = _validate_payload(
        result_payload
    )

    try:
        job.mark_completed(
            result_payload=resolved_result,
            duration_ms=_duration_ms(
                started_monotonic
            ),
        )
    except ValueError as exc:
        raise BackgroundJobStateError(
            str(exc)
        ) from exc

    _commit_or_flush(
        db,
        commit=commit,
        refresh=job,
    )

    return job


def fail_job(
    db: Session,
    *,
    job_id: int,
    error_message: str,
    retry_delay_seconds: int = DEFAULT_RETRY_DELAY_SECONDS,
    started_monotonic: float | None = None,
    commit: bool = True,
) -> BackgroundJob:
    """
    Fail one RUNNING job and schedule a future retry when attempts remain.
    """

    job = require_job(
        db,
        job_id=job_id,
    )

    if (
        job.status
        != JOB_STATUS_RUNNING
    ):
        raise BackgroundJobStateError(
            "Only RUNNING jobs can fail."
        )

    resolved_delay = _bounded_int(
        retry_delay_seconds,
        field_name="Retry delay",
        minimum=1,
        maximum=MAX_RETRY_DELAY_SECONDS,
    )

    retry_at = None

    if int(
        job.attempt_count or 0
    ) < int(
        job.max_attempts or 1
    ):
        retry_at = utc_now() + timedelta(
            seconds=resolved_delay
        )

    try:
        job.mark_failed(
            error_message=error_message,
            retry_at=retry_at,
            duration_ms=_duration_ms(
                started_monotonic
            ),
        )
    except ValueError as exc:
        raise BackgroundJobStateError(
            str(exc)
        ) from exc

    _commit_or_flush(
        db,
        commit=commit,
        refresh=job,
    )

    return job


def cancel_job(
    db: Session,
    *,
    job_id: int,
    commit: bool = True,
) -> BackgroundJob:
    """
    Cancel one non-terminal background job.
    """

    job = require_job(
        db,
        job_id=job_id,
    )

    if job.status in TERMINAL_JOB_STATUSES:
        raise BackgroundJobStateError(
            "Finalized background job cannot be cancelled."
        )

    try:
        job.cancel()
    except ValueError as exc:
        raise BackgroundJobStateError(
            str(exc)
        ) from exc

    _commit_or_flush(
        db,
        commit=commit,
        refresh=job,
    )

    return job


def recover_stalled_jobs(
    db: Session,
    *,
    stalled_after_seconds: int = DEFAULT_STALLED_AFTER_SECONDS,
    retry_delay_seconds: int = DEFAULT_RETRY_DELAY_SECONDS,
    commit: bool = True,
) -> int:
    """
    Recover a bounded batch of RUNNING jobs with stale heartbeats.
    """

    stalled_after = _bounded_int(
        stalled_after_seconds,
        field_name="Stalled threshold",
        minimum=1,
        maximum=MAX_STALLED_AFTER_SECONDS,
    )

    retry_delay = _bounded_int(
        retry_delay_seconds,
        field_name="Retry delay",
        minimum=1,
        maximum=MAX_RETRY_DELAY_SECONDS,
    )

    now = utc_now()
    cutoff = now - timedelta(
        seconds=stalled_after
    )

    jobs = (
        db.query(
            BackgroundJob
        )
        .filter(
            BackgroundJob.status
            == JOB_STATUS_RUNNING,
            or_(
                BackgroundJob.heartbeat_at.is_(
                    None
                ),
                BackgroundJob.heartbeat_at
                < cutoff,
            ),
        )
        .order_by(
            BackgroundJob.heartbeat_at.asc(),
            BackgroundJob.id.asc(),
        )
        .limit(
            MAX_RECOVERY_BATCH
        )
        .with_for_update(
            skip_locked=True
        )
        .all()
    )

    for job in jobs:
        retry_at = None

        if int(
            job.attempt_count or 0
        ) < int(
            job.max_attempts or 1
        ):
            retry_at = now + timedelta(
                seconds=retry_delay
            )

        try:
            job.mark_failed(
                error_message=(
                    "Background worker heartbeat expired."
                ),
                retry_at=retry_at,
            )
        except ValueError as exc:
            db.rollback()
            raise BackgroundJobStateError(
                str(exc)
            ) from exc

    if jobs:
        _commit_or_flush(
            db,
            commit=commit,
        )

    return len(
        jobs
    )


def requeue_job(
    db: Session,
    *,
    job_id: int,
    scheduled_at: datetime | None = None,
    reset_attempts: bool = False,
    commit: bool = True,
) -> BackgroundJob:
    """
    Requeue a FAILED, CANCELLED, or COMPLETED job.
    """

    job = require_job(
        db,
        job_id=job_id,
    )

    if job.status not in TERMINAL_JOB_STATUSES:
        raise BackgroundJobStateError(
            "Only finalized jobs can be manually requeued."
        )

    resolved_schedule = (
        _as_utc(
            scheduled_at
        )
        or utc_now()
    )

    attempts = int(
        job.attempt_count or 0
    )

    if (
        not reset_attempts
        and attempts
        >= int(
            job.max_attempts or 1
        )
    ):
        raise BackgroundJobStateError(
            "Maximum attempts reached; reset_attempts is required."
        )

    job.status = JOB_STATUS_PENDING
    job.scheduled_at = resolved_schedule
    job.started_at = None
    job.finished_at = None
    job.retry_at = None
    job.heartbeat_at = None
    job.duration_ms = None
    job.error_message = None
    job.result_payload = None
    job.worker_name = None
    job.updated_at = utc_now()

    if reset_attempts:
        job.attempt_count = 0

    try:
        job.validate_state()
    except ValueError as exc:
        raise BackgroundJobStateError(
            str(exc)
        ) from exc

    _commit_or_flush(
        db,
        commit=commit,
        refresh=job,
    )

    return job


def delete_job(
    db: Session,
    *,
    job_id: int,
    commit: bool = True,
) -> None:
    """
    Delete one finalized job for controlled owner maintenance.
    """

    job = require_job(
        db,
        job_id=job_id,
    )

    if job.status not in TERMINAL_JOB_STATUSES:
        raise BackgroundJobStateError(
            "Only finalized background jobs can be deleted."
        )

    db.delete(
        job
    )

    _commit_or_flush(
        db,
        commit=commit,
    )


def job_public_payload(
    job: BackgroundJob,
) -> dict[str, object]:
    return job.to_public_dict()


def jobs_public_payload(
    jobs: Iterable[BackgroundJob],
) -> list[dict[str, object]]:
    return [
        job_public_payload(
            job
        )
        for job in jobs
    ]


__all__ = [
    "DEFAULT_MAX_ATTEMPTS",
    "DEFAULT_PRIORITY",
    "DEFAULT_RETRY_DELAY_SECONDS",
    "DEFAULT_STALLED_AFTER_SECONDS",
    "BackgroundJobError",
    "BackgroundJobNotFoundError",
    "BackgroundJobStateError",
    "BackgroundJobValidationError",
    "cancel_job",
    "claim_next_job",
    "complete_job",
    "delete_job",
    "enqueue_job",
    "fail_job",
    "generate_job_uid",
    "get_job_by_id",
    "get_job_by_uid",
    "heartbeat_job",
    "job_public_payload",
    "jobs_public_payload",
    "list_jobs",
    "normalise_job_status",
    "normalise_job_type",
    "recover_stalled_jobs",
    "requeue_job",
    "require_job",
    "utc_now",
]