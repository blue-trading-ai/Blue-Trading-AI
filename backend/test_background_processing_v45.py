from __future__ import annotations

import asyncio
import os
import sys
from datetime import timedelta
from typing import Any

import requests

from app.database.connection import SessionLocal
from app.models.background_job import (
    BackgroundJob,
    JOB_STATUS_CANCELLED,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_PENDING,
    JOB_STATUS_RETRY_WAIT,
    JOB_STATUS_RUNNING,
    JOB_TYPE_LEARNING_REFRESH,
    JOB_TYPE_MARKET_REFRESH,
)
from app.services.background_job_service import (
    cancel_job,
    claim_next_job,
    complete_job,
    enqueue_job,
    fail_job,
    heartbeat_job,
    recover_stalled_jobs,
    requeue_job,
    utc_now,
)
from app.services.background_worker import (
    process_claimed_job,
)


BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

TIMEOUT = 20


class ValidationFailure(Exception):
    pass


def print_step(
    number: int,
    title: str,
) -> None:
    print(f"\n[{number}/10] {title}")


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise ValidationFailure(message)


def json_body(
    response: requests.Response,
) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception as exc:
        raise ValidationFailure(
            f"Response was not JSON: {response.text[:500]}"
        ) from exc

    require(
        isinstance(payload, dict),
        "Expected a JSON object response.",
    )

    return payload


async def mock_handler(
    db,
    job: BackgroundJob,
) -> dict[str, Any]:
    return {
        "handled": True,
        "job_uid": job.job_uid,
        "job_type": job.job_type,
        "broker_execution_enabled": False,
    }


def main() -> int:
    print("=" * 72)
    print("BLUE TRADING AI - VERSION 45 BACKGROUND PROCESSING TEST")
    print("=" * 72)

    created_ids: list[int] = []
    db = None

    try:
        print_step(1, "API reports Version 45")

        response = requests.get(
            f"{BASE_URL}/",
            timeout=TIMEOUT,
        )

        require(
            response.status_code == 200,
            (
                "Main API failed: "
                f"{response.status_code} {response.text}"
            ),
        )

        payload = json_body(response)

        require(
            str(payload.get("version")) == "45.0.0",
            f"Expected version 45.0.0, got {payload}",
        )

        require(
            payload.get(
                "background_processing_enabled"
            )
            is True,
            "Background processing metadata is missing.",
        )

        print("PASSED")

        print_step(2, "Background API is available")

        response = requests.get(
            f"{BASE_URL}/background-jobs/",
            timeout=TIMEOUT,
        )

        require(
            response.status_code == 200,
            (
                "Background API failed: "
                f"{response.status_code} {response.text}"
            ),
        )

        background_home = json_body(response)

        require(
            background_home.get(
                "background_api_version"
            )
            == 45,
            "Background API version is incorrect.",
        )

        require(
            background_home.get(
                "broker_execution_enabled"
            )
            is False,
            "Broker execution must remain disabled.",
        )

        print("PASSED")

        db = SessionLocal()

        print_step(3, "Jobs are queued persistently")

        low_priority = enqueue_job(
            db,
            job_type=JOB_TYPE_MARKET_REFRESH,
            symbol="BTCUSD",
            timeframe="1h",
            payload={"test": True},
            priority=200,
            commit=True,
        )
        created_ids.append(int(low_priority.id))

        high_priority = enqueue_job(
            db,
            job_type=JOB_TYPE_LEARNING_REFRESH,
            priority=10,
            commit=True,
        )
        created_ids.append(int(high_priority.id))

        require(
            low_priority.status == JOB_STATUS_PENDING,
            "Low-priority job was not pending.",
        )
        require(
            high_priority.status == JOB_STATUS_PENDING,
            "High-priority job was not pending.",
        )

        print("PASSED")

        print_step(4, "Queue claims highest-priority due job")

        claimed = claim_next_job(
            db,
            worker_name="v45-test-worker",
            commit=True,
        )

        require(
            claimed is not None,
            "No queued job was claimed.",
        )
        require(
            int(claimed.id) == int(high_priority.id),
            "Queue did not claim the highest-priority job.",
        )
        require(
            claimed.status == JOB_STATUS_RUNNING,
            "Claimed job is not RUNNING.",
        )
        require(
            claimed.attempt_count == 1,
            "Claim attempt count is incorrect.",
        )

        print("PASSED")

        print_step(5, "Running job heartbeat is updated")

        previous_heartbeat = claimed.heartbeat_at

        heartbeat = heartbeat_job(
            db,
            job_id=int(claimed.id),
            worker_name="v45-test-worker",
            commit=True,
        )

        require(
            heartbeat.heartbeat_at is not None,
            "Heartbeat timestamp is missing.",
        )
        require(
            heartbeat.status == JOB_STATUS_RUNNING,
            "Heartbeat changed the job status.",
        )
        require(
            previous_heartbeat is None
            or heartbeat.heartbeat_at
            >= previous_heartbeat,
            "Heartbeat timestamp did not advance.",
        )

        print("PASSED")

        print_step(6, "Running job completes with result")

        completed = complete_job(
            db,
            job_id=int(claimed.id),
            result_payload={
                "test_completed": True,
            },
            commit=True,
        )

        require(
            completed.status == JOB_STATUS_COMPLETED,
            "Job did not complete.",
        )
        require(
            completed.result_payload.get(
                "test_completed"
            )
            is True,
            "Completion result was not saved.",
        )

        print("PASSED")

        print_step(7, "Failed job enters retry wait")

        retry_job = enqueue_job(
            db,
            job_type=JOB_TYPE_LEARNING_REFRESH,
            max_attempts=3,
            priority=20,
            commit=True,
        )
        created_ids.append(int(retry_job.id))

        claimed_retry = claim_next_job(
            db,
            worker_name="v45-retry-worker",
            allowed_job_types=[
                JOB_TYPE_LEARNING_REFRESH,
            ],
            commit=True,
        )

        require(
            claimed_retry is not None,
            "Retry test job was not claimed.",
        )

        failed = fail_job(
            db,
            job_id=int(claimed_retry.id),
            error_message="Expected test failure.",
            retry_delay_seconds=1,
            commit=True,
        )

        require(
            failed.status == JOB_STATUS_RETRY_WAIT,
            "Failed job did not enter RETRY_WAIT.",
        )
        require(
            failed.retry_at is not None,
            "Retry timestamp is missing.",
        )

        print("PASSED")

        print_step(8, "Cancellation and requeue work")

        cancel_target = enqueue_job(
            db,
            job_type=JOB_TYPE_MARKET_REFRESH,
            symbol="XAUUSD",
            timeframe="4h",
            priority=300,
            commit=True,
        )
        created_ids.append(int(cancel_target.id))

        cancelled = cancel_job(
            db,
            job_id=int(cancel_target.id),
            commit=True,
        )

        require(
            cancelled.status == JOB_STATUS_CANCELLED,
            "Job was not cancelled.",
        )

        requeued = requeue_job(
            db,
            job_id=int(cancel_target.id),
            reset_attempts=True,
            commit=True,
        )

        require(
            requeued.status == JOB_STATUS_PENDING,
            "Cancelled job was not requeued.",
        )
        require(
            requeued.attempt_count == 0,
            "Attempt count was not reset.",
        )

        print("PASSED")

        print_step(9, "Stalled worker recovery works")

        stalled = enqueue_job(
            db,
            job_type=JOB_TYPE_LEARNING_REFRESH,
            priority=5,
            commit=True,
        )
        created_ids.append(int(stalled.id))

        stalled_claim = claim_next_job(
            db,
            worker_name="v45-stalled-worker",
            allowed_job_types=[
                JOB_TYPE_LEARNING_REFRESH,
            ],
            commit=True,
        )

        require(
            stalled_claim is not None,
            "Stalled test job was not claimed.",
        )

        stalled_claim.heartbeat_at = (
            utc_now() - timedelta(minutes=10)
        )
        db.commit()

        recovered_count = recover_stalled_jobs(
            db,
            stalled_after_seconds=60,
            retry_delay_seconds=1,
            commit=True,
        )

        db.refresh(stalled_claim)

        require(
            recovered_count >= 1,
            "No stalled job was recovered.",
        )
        require(
            stalled_claim.status
            == JOB_STATUS_RETRY_WAIT,
            (
                "Recovered stalled job did not enter "
                "RETRY_WAIT."
            ),
        )

        print("PASSED")

        print_step(10, "Worker processes a claimed job safely")

        worker_job = enqueue_job(
            db,
            job_type=JOB_TYPE_LEARNING_REFRESH,
            priority=1,
            commit=True,
        )
        created_ids.append(int(worker_job.id))

        claimed_worker_job = claim_next_job(
            db,
            worker_name="v45-process-worker",
            allowed_job_types=[
                JOB_TYPE_LEARNING_REFRESH,
            ],
            commit=True,
        )

        require(
            claimed_worker_job is not None,
            "Worker test job was not claimed.",
        )

        processed = asyncio.run(
            process_claimed_job(
                job=claimed_worker_job,
                worker_name=(
                    "v45-process-worker"
                ),
                handlers={
                    JOB_TYPE_LEARNING_REFRESH: (
                        mock_handler
                    )
                },
                heartbeat_interval_seconds=1,
            )
        )

        require(
            processed.status
            == JOB_STATUS_COMPLETED,
            "Worker did not complete the job.",
        )
        require(
            processed.result_payload.get(
                "handled"
            )
            is True,
            "Worker result payload is incorrect.",
        )
        require(
            processed.result_payload.get(
                "broker_execution_enabled"
            )
            is False,
            "Worker must not enable broker execution.",
        )

        print("PASSED")

        print("\n" + "=" * 72)
        print(
            "VERSION 45 BACKGROUND PROCESSING TEST: "
            "10/10 PASSED"
        )
        print("=" * 72)

        return 0

    except requests.RequestException as exc:
        print(
            f"\nFAILED: API connection error: {exc}"
        )
        return 1
    except ValidationFailure as exc:
        print(f"\nFAILED: {exc}")
        return 1
    except Exception as exc:
        print(
            "\nFAILED: Unexpected error: "
            f"{type(exc).__name__}: {exc}"
        )
        return 1
    finally:
        if db is not None:
            try:
                for job_id in created_ids:
                    record = (
                        db.query(BackgroundJob)
                        .filter(
                            BackgroundJob.id
                            == int(job_id)
                        )
                        .first()
                    )

                    if record is not None:
                        db.delete(record)

                db.commit()
            except Exception:
                db.rollback()
            finally:
                db.close()


if __name__ == "__main__":
    sys.exit(main())

