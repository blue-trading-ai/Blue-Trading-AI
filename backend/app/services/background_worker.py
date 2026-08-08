from __future__ import annotations

import asyncio
import inspect
import math
import os
import socket
import time
from datetime import timedelta
from typing import Any, Awaitable, Callable, Final

from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.connection import SessionLocal
from app.models.background_job import (
    BackgroundJob,
    JOB_STATUS_RUNNING,
    JOB_TYPE_LEARNING_REFRESH,
    JOB_TYPE_MARKET_REFRESH,
    JOB_TYPE_SIGNAL_EXPIRY,
    JOB_TYPE_SIGNAL_GENERATION,
)
from app.services.background_job_service import (
    BackgroundJobError,
    BackgroundJobStateError,
    claim_next_job,
    complete_job,
    fail_job,
    heartbeat_job,
    recover_stalled_jobs,
    utc_now,
)
from app.services.signal_performance_service import (
    get_overall_performance,
)
from app.services.trading_signal_service import (
    bulk_expire_pending_signals,
    create_signal,
)


WorkerHandler = Callable[
    [Session, BackgroundJob],
    dict[str, Any] | Awaitable[dict[str, Any]],
]


DEFAULT_POLL_INTERVAL_SECONDS: Final[float] = 2.0
DEFAULT_HEARTBEAT_INTERVAL_SECONDS: Final[float] = 15.0
DEFAULT_STALLED_RECOVERY_SECONDS: Final[int] = 300
DEFAULT_SIGNAL_EXPIRY_HOURS: Final[int] = 24
DEFAULT_RETRY_DELAY_SECONDS: Final[int] = 60

MIN_POLL_INTERVAL_SECONDS: Final[float] = 0.5
MAX_POLL_INTERVAL_SECONDS: Final[float] = 300.0
MIN_HEARTBEAT_INTERVAL_SECONDS: Final[float] = 1.0
MAX_HEARTBEAT_INTERVAL_SECONDS: Final[float] = 300.0
MAX_EXPIRY_HOURS: Final[int] = 24 * 30
MAX_WORKER_NAME_LENGTH: Final[int] = 100


class BackgroundWorkerError(Exception):
    """Base exception for worker-processing failures."""


class UnsupportedBackgroundJobError(
    BackgroundWorkerError
):
    pass


def _clean_worker_name(
    value: str,
) -> str:
    cleaned = "".join(
        character
        if character.isprintable()
        and character not in {
            "\r",
            "\n",
            "\t",
        }
        else "-"
        for character in str(
            value or ""
        )
    ).strip()

    return cleaned[
        :MAX_WORKER_NAME_LENGTH
    ]


def _bounded_float(
    value: Any,
    *,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    try:
        resolved = float(value)
    except (
        TypeError,
        ValueError,
    ):
        resolved = default

    if not math.isfinite(
        resolved
    ):
        resolved = default

    return max(
        minimum,
        min(
            resolved,
            maximum,
        ),
    )


def _safe_positive_int(
    value: Any,
    *,
    default: int,
    maximum: int,
) -> int:
    try:
        resolved = int(value)
    except (
        TypeError,
        ValueError,
    ):
        resolved = default

    return max(
        1,
        min(
            resolved,
            maximum,
        ),
    )


def _safe_exception_category(
    exc: Exception,
) -> str:
    """
    Return a bounded failure category without storing exception text.
    """

    if isinstance(
        exc,
        UnsupportedBackgroundJobError,
    ):
        return "Unsupported background job type."

    if isinstance(
        exc,
        BackgroundJobStateError,
    ):
        return "Background job state conflict."

    if isinstance(
        exc,
        BackgroundJobError,
    ):
        return "Background job service failure."

    if isinstance(
        exc,
        asyncio.TimeoutError,
    ):
        return "Background job operation timed out."

    return "Background job handler failed."


def default_worker_name() -> str:
    """
    Return a stable, sanitized local worker identifier.
    """

    configured = str(
        getattr(
            settings,
            "BACKGROUND_WORKER_NAME",
            "",
        )
        or ""
    ).strip()

    if configured:
        resolved = _clean_worker_name(
            configured
        )

        if resolved:
            return resolved

    hostname = _clean_worker_name(
        socket.gethostname()
    ) or "worker"

    process_id = os.getpid()

    return _clean_worker_name(
        f"{hostname}-{process_id}"
    ) or "default-worker"


async def _maybe_await(
    value: Any,
) -> Any:
    if inspect.isawaitable(
        value
    ):
        return await value

    return value


def _load_market_provider() -> Callable[..., Any]:
    """
    Import the existing market-data provider lazily.
    """

    try:
        from app.market.provider import get_market_data
    except ImportError as exc:
        raise BackgroundWorkerError(
            "Market-data provider is unavailable."
        ) from exc

    if not callable(
        get_market_data
    ):
        raise BackgroundWorkerError(
            "Market-data provider is invalid."
        )

    return get_market_data


def _load_signal_generator() -> Callable[..., Any]:
    """
    Import the existing signal engine lazily.
    """

    candidates = (
        (
            "app.trading.signal_engine",
            "generate_signal",
        ),
        (
            "app.trading.analysis",
            "generate_signal",
        ),
    )

    for (
        module_name,
        function_name,
    ) in candidates:
        try:
            module = __import__(
                module_name,
                fromlist=[
                    function_name
                ],
            )

            function = getattr(
                module,
                function_name,
                None,
            )

            if callable(
                function
            ):
                return function
        except ImportError:
            continue

    raise BackgroundWorkerError(
        "Signal-generation function is unavailable."
    )


def _first_present(
    source: dict[str, Any],
    *keys: str,
    default: Any = None,
) -> Any:
    """
    Return the first present non-None value.

    Unlike chained ``or``, this preserves legitimate numeric zeroes.
    """

    for key in keys:
        if (
            key in source
            and source[key] is not None
        ):
            return source[
                key
            ]

    return default


def _extract_signal_fields(
    payload: dict[str, Any],
    *,
    symbol: str,
    timeframe: str,
) -> dict[str, Any]:
    """
    Map an engine response into trading-signal storage fields.
    """

    signal_block = payload.get(
        "signal"
    )

    source = (
        signal_block
        if isinstance(
            signal_block,
            dict,
        )
        else payload
    )

    confirmations = _first_present(
        source,
        "confirmations",
        default=payload.get(
            "confirmations"
        ),
    )

    confirmations_count = _first_present(
        source,
        "confirmations_count",
        default=payload.get(
            "confirmations_count"
        ),
    )

    if confirmations_count is None:
        if isinstance(
            confirmations,
            (
                list,
                dict,
                tuple,
                set,
            ),
        ):
            confirmations_count = len(
                confirmations
            )
        else:
            confirmations_count = 0

    direction = _first_present(
        source,
        "direction",
        "signal",
        "action",
        default="NO_TRADE",
    )

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "direction": direction,
        "confidence": _first_present(
            source,
            "confidence",
            "confidence_score",
            default=0,
        ),
        "confirmations_count": (
            confirmations_count
        ),
        "risk_reward_ratio": _first_present(
            source,
            "risk_reward_ratio",
            "rr",
            "risk_reward",
        ),
        "entry_price": _first_present(
            source,
            "entry_price",
            "entry",
        ),
        "stop_loss": _first_present(
            source,
            "stop_loss",
            "sl",
        ),
        "take_profit_1": _first_present(
            source,
            "take_profit_1",
            "tp1",
        ),
        "take_profit_2": _first_present(
            source,
            "take_profit_2",
            "tp2",
        ),
        "take_profit_3": _first_present(
            source,
            "take_profit_3",
            "tp3",
        ),
        "strategy_version": _first_present(
            source,
            "strategy_version",
            default=(
                payload.get(
                    "strategy_version"
                )
                or "V46_BACKGROUND"
            ),
        ),
        "market_structure": _first_present(
            source,
            "market_structure",
            default=payload.get(
                "market_structure"
            ),
        ),
        "confirmations": confirmations,
        "analysis_details": payload,
        "reasoning": _first_present(
            source,
            "reasoning",
            "reason",
            default=payload.get(
                "reasoning"
            ),
        ),
        "rejection_reason": _first_present(
            source,
            "rejection_reason",
            default=payload.get(
                "rejection_reason"
            ),
        ),
        "source": "BACKGROUND_WORKER",
    }


async def handle_market_refresh(
    db: Session,
    job: BackgroundJob,
) -> dict[str, Any]:
    """
    Fetch current market data using the existing provider.
    """

    del db

    if not job.symbol:
        raise BackgroundWorkerError(
            "Market refresh requires a symbol."
        )

    timeframe = (
        job.timeframe
        or "1h"
    )

    provider = _load_market_provider()

    result = await _maybe_await(
        provider(
            job.symbol,
            timeframe,
        )
    )

    if result is None:
        raise BackgroundWorkerError(
            "Market-data provider returned no data."
        )

    row_count: int | None = None

    if isinstance(
        result,
        dict,
    ):
        for key in (
            "candles",
            "data",
            "prices",
        ):
            value = result.get(
                key
            )

            if isinstance(
                value,
                list,
            ):
                row_count = len(
                    value
                )
                break
    elif isinstance(
        result,
        list,
    ):
        row_count = len(
            result
        )

    return {
        "job_type": JOB_TYPE_MARKET_REFRESH,
        "symbol": job.symbol,
        "timeframe": timeframe,
        "market_data_received": True,
        "row_count": row_count,
    }


async def handle_signal_generation(
    db: Session,
    job: BackgroundJob,
) -> dict[str, Any]:
    """
    Generate and persist one analysis-only trading signal.
    """

    if not job.symbol:
        raise BackgroundWorkerError(
            "Signal generation requires a symbol."
        )

    timeframe = (
        job.timeframe
        or "1h"
    )

    provider = _load_market_provider()
    generator = _load_signal_generator()

    market_data = await _maybe_await(
        provider(
            job.symbol,
            timeframe,
        )
    )

    if market_data is None:
        raise BackgroundWorkerError(
            "Market data is unavailable for signal generation."
        )

    generated = await _maybe_await(
        generator(
            market_data,
            symbol=job.symbol,
            timeframe=timeframe,
        )
    )

    if not isinstance(
        generated,
        dict,
    ):
        raise BackgroundWorkerError(
            "Signal engine returned an unsupported response."
        )

    fields = _extract_signal_fields(
        generated,
        symbol=job.symbol,
        timeframe=timeframe,
    )

    signal = create_signal(
        db,
        **fields,
        commit=True,
    )

    return {
        "job_type": JOB_TYPE_SIGNAL_GENERATION,
        "symbol": job.symbol,
        "timeframe": timeframe,
        "signal_uid": signal.signal_uid,
        "signal_id": signal.id,
        "direction": signal.direction,
        "confidence": str(
            signal.confidence
        ),
        "confirmations_count": (
            signal.confirmations_count
        ),
        "risk_reward_ratio": (
            str(
                signal.risk_reward_ratio
            )
            if signal.risk_reward_ratio
            is not None
            else None
        ),
        "is_trade_allowed": bool(
            signal.is_trade_allowed
        ),
        "broker_execution_enabled": False,
    }


async def handle_signal_expiry(
    db: Session,
    job: BackgroundJob,
) -> dict[str, Any]:
    """
    Expire old pending or active signals.
    """

    payload = (
        job.payload
        if isinstance(
            job.payload,
            dict,
        )
        else {}
    )

    expiry_hours = _safe_positive_int(
        payload.get(
            "expiry_hours",
            DEFAULT_SIGNAL_EXPIRY_HOURS,
        ),
        default=DEFAULT_SIGNAL_EXPIRY_HOURS,
        maximum=MAX_EXPIRY_HOURS,
    )

    cutoff = utc_now() - timedelta(
        hours=expiry_hours
    )

    expired_count = (
        bulk_expire_pending_signals(
            db,
            before=cutoff,
            commit=True,
        )
    )

    return {
        "job_type": JOB_TYPE_SIGNAL_EXPIRY,
        "expiry_hours": expiry_hours,
        "cutoff": cutoff,
        "expired_signals": int(
            expired_count
            or 0
        ),
    }


async def handle_learning_refresh(
    db: Session,
    job: BackgroundJob,
) -> dict[str, Any]:
    """
    Refresh completed-trade learning readiness metrics.
    """

    del job

    performance = get_overall_performance(
        db
    )

    if not isinstance(
        performance,
        dict,
    ):
        raise BackgroundWorkerError(
            "Performance service returned an invalid response."
        )

    return {
        "job_type": JOB_TYPE_LEARNING_REFRESH,
        "learning_ready": bool(
            performance.get(
                "learning_ready",
                False,
            )
        ),
        "total_completed": int(
            performance.get(
                "total_completed",
                0,
            )
            or 0
        ),
        "learning_trades_remaining": int(
            performance.get(
                "learning_trades_remaining",
                0,
            )
            or 0
        ),
        "win_rate": str(
            performance.get(
                "win_rate",
                0,
            )
        ),
        "learning_uses_completed_trades_only": True,
    }


DEFAULT_HANDLERS: Final[
    dict[str, WorkerHandler]
] = {
    JOB_TYPE_MARKET_REFRESH: (
        handle_market_refresh
    ),
    JOB_TYPE_SIGNAL_GENERATION: (
        handle_signal_generation
    ),
    JOB_TYPE_SIGNAL_EXPIRY: (
        handle_signal_expiry
    ),
    JOB_TYPE_LEARNING_REFRESH: (
        handle_learning_refresh
    ),
}


async def _heartbeat_loop(
    *,
    job_id: int,
    worker_name: str,
    stop_event: asyncio.Event,
    heartbeat_interval_seconds: float,
) -> None:
    """
    Update a running job heartbeat without crashing the handler task.
    """

    interval = _bounded_float(
        heartbeat_interval_seconds,
        default=(
            DEFAULT_HEARTBEAT_INTERVAL_SECONDS
        ),
        minimum=(
            MIN_HEARTBEAT_INTERVAL_SECONDS
        ),
        maximum=(
            MAX_HEARTBEAT_INTERVAL_SECONDS
        ),
    )

    while not stop_event.is_set():
        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=interval,
            )

            break
        except asyncio.TimeoutError:
            db = SessionLocal()

            try:
                heartbeat_job(
                    db,
                    job_id=job_id,
                    worker_name=worker_name,
                    commit=True,
                )
            except BackgroundJobStateError:
                return
            except Exception:
                db.rollback()
                return
            finally:
                db.close()


async def _mark_claimed_job_failed(
    *,
    job_id: int,
    exc: Exception,
    started_monotonic: float,
) -> BackgroundJob | None:
    """
    Mark a claimed job failed using a fresh transaction.

    Raw exception text is never stored in the job record.
    """

    db = SessionLocal()

    try:
        job = (
            db.query(
                BackgroundJob
            )
            .filter(
                BackgroundJob.id
                == job_id
            )
            .first()
        )

        if (
            job is None
            or job.status
            != JOB_STATUS_RUNNING
        ):
            return job

        return fail_job(
            db,
            job_id=job_id,
            error_message=(
                _safe_exception_category(
                    exc
                )
            ),
            retry_delay_seconds=(
                DEFAULT_RETRY_DELAY_SECONDS
            ),
            started_monotonic=(
                started_monotonic
            ),
            commit=True,
        )
    except Exception:
        db.rollback()
        return None
    finally:
        db.close()


async def process_claimed_job(
    *,
    job: BackgroundJob,
    worker_name: str,
    handlers: dict[str, WorkerHandler] | None = None,
    heartbeat_interval_seconds: float = (
        DEFAULT_HEARTBEAT_INTERVAL_SECONDS
    ),
) -> BackgroundJob:
    """
    Execute one already-claimed job and always finalize its state.
    """

    if job.id is None:
        raise BackgroundWorkerError(
            "Claimed background job has no database ID."
        )

    job_id = int(
        job.id
    )

    resolved_handlers = (
        handlers
        if handlers is not None
        else DEFAULT_HANDLERS
    )

    started_monotonic = time.monotonic()
    stop_event = asyncio.Event()

    heartbeat_task = asyncio.create_task(
        _heartbeat_loop(
            job_id=job_id,
            worker_name=worker_name,
            stop_event=stop_event,
            heartbeat_interval_seconds=(
                heartbeat_interval_seconds
            ),
        )
    )

    db = SessionLocal()

    try:
        current_job = (
            db.query(
                BackgroundJob
            )
            .filter(
                BackgroundJob.id
                == job_id
            )
            .first()
        )

        if current_job is None:
            raise BackgroundWorkerError(
                "Claimed background job no longer exists."
            )

        if (
            current_job.status
            != JOB_STATUS_RUNNING
        ):
            raise BackgroundJobStateError(
                "Claimed background job is no longer running."
            )

        handler = resolved_handlers.get(
            current_job.job_type
        )

        if handler is None:
            raise UnsupportedBackgroundJobError(
                "No handler exists for this background job type."
            )

        result_payload = await _maybe_await(
            handler(
                db,
                current_job,
            )
        )

        if not isinstance(
            result_payload,
            dict,
        ):
            raise BackgroundWorkerError(
                "Background job handler returned an invalid result."
            )

        return complete_job(
            db,
            job_id=job_id,
            result_payload=result_payload,
            started_monotonic=(
                started_monotonic
            ),
            commit=True,
        )
    except asyncio.CancelledError as exc:
        db.rollback()

        failed = await _mark_claimed_job_failed(
            job_id=job_id,
            exc=exc,
            started_monotonic=(
                started_monotonic
            ),
        )

        if failed is not None:
            return failed

        raise
    except Exception as exc:
        db.rollback()

        failed = await _mark_claimed_job_failed(
            job_id=job_id,
            exc=exc,
            started_monotonic=(
                started_monotonic
            ),
        )

        if failed is not None:
            return failed

        raise BackgroundWorkerError(
            "Background job failed and could not be finalized."
        ) from exc
    finally:
        stop_event.set()

        try:
            await heartbeat_task
        except (
            asyncio.CancelledError,
            Exception,
        ):
            pass

        db.close()


async def run_worker_once(
    *,
    worker_name: str | None = None,
    handlers: dict[str, WorkerHandler] | None = None,
) -> BackgroundJob | None:
    """
    Claim and process at most one due job.
    """

    resolved_worker_name = (
        _clean_worker_name(
            worker_name
        )
        if worker_name
        else default_worker_name()
    )

    if not resolved_worker_name:
        resolved_worker_name = (
            "default-worker"
        )

    claim_db = SessionLocal()

    try:
        job = claim_next_job(
            claim_db,
            worker_name=(
                resolved_worker_name
            ),
            commit=True,
        )
    except Exception:
        claim_db.rollback()
        raise
    finally:
        claim_db.close()

    if job is None:
        return None

    return await process_claimed_job(
        job=job,
        worker_name=resolved_worker_name,
        handlers=handlers,
    )


async def run_background_worker(
    *,
    stop_event: asyncio.Event,
    worker_name: str | None = None,
    poll_interval_seconds: float = (
        DEFAULT_POLL_INTERVAL_SECONDS
    ),
    handlers: dict[str, WorkerHandler] | None = None,
) -> None:
    """
    Continuously process jobs until stopped.

    Individual job failures do not terminate the worker loop.
    """

    resolved_worker_name = (
        _clean_worker_name(
            worker_name
        )
        if worker_name
        else default_worker_name()
    )

    if not resolved_worker_name:
        resolved_worker_name = (
            "default-worker"
        )

    poll_interval = _bounded_float(
        poll_interval_seconds,
        default=(
            DEFAULT_POLL_INTERVAL_SECONDS
        ),
        minimum=(
            MIN_POLL_INTERVAL_SECONDS
        ),
        maximum=(
            MAX_POLL_INTERVAL_SECONDS
        ),
    )

    recovery_db = SessionLocal()

    try:
        recover_stalled_jobs(
            recovery_db,
            stalled_after_seconds=(
                DEFAULT_STALLED_RECOVERY_SECONDS
            ),
            commit=True,
        )
    except Exception:
        recovery_db.rollback()
    finally:
        recovery_db.close()

    while not stop_event.is_set():
        try:
            processed = await run_worker_once(
                worker_name=(
                    resolved_worker_name
                ),
                handlers=handlers,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            processed = None

        if processed is not None:
            continue

        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=poll_interval,
            )
        except asyncio.TimeoutError:
            continue


__all__ = [
    "DEFAULT_HANDLERS",
    "DEFAULT_HEARTBEAT_INTERVAL_SECONDS",
    "DEFAULT_POLL_INTERVAL_SECONDS",
    "DEFAULT_SIGNAL_EXPIRY_HOURS",
    "DEFAULT_STALLED_RECOVERY_SECONDS",
    "BackgroundWorkerError",
    "UnsupportedBackgroundJobError",
    "default_worker_name",
    "handle_learning_refresh",
    "handle_market_refresh",
    "handle_signal_expiry",
    "handle_signal_generation",
    "process_claimed_job",
    "run_background_worker",
    "run_worker_once",
]