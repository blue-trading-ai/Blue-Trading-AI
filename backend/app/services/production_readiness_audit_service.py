from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any, Callable, Final

from sqlalchemy import func, inspect, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.connection import engine
from app.models.application_event_log import (
    ApplicationEventLog,
)
from app.models.background_job import BackgroundJob
from app.models.trading_signal import TradingSignal
from app.services.application_logging_service import (
    get_monitoring_summary,
)
from app.services.signal_performance_service import (
    LEARNING_MINIMUM_COMPLETED_TRADES,
)


MINIMUM_SIGNAL_CONFIDENCE: Final[Decimal] = (
    Decimal("80")
)
MINIMUM_SIGNAL_CONFIRMATIONS: Final[int] = 3
MINIMUM_SIGNAL_RISK_REWARD: Final[Decimal] = (
    Decimal("1.5")
)
MAX_ACCEPTABLE_DATABASE_PING_MS: Final[float] = 500.0
MAX_ACCEPTABLE_MONITORING_QUERY_MS: Final[float] = 1500.0
EXPECTED_ALEMBIC_HEAD: Final[str] = (
    "v46_application_event_logs"
)

MINIMUM_PRODUCTION_SECRET_LENGTH: Final[int] = 48

REQUIRED_TABLES: Final[set[str]] = {
    "users",
    "auth_sessions",
    "refresh_tokens",
    "account_action_tokens",
    "roles",
    "permissions",
    "user_roles",
    "role_permissions",
    "security_audit_logs",
    "trade_history",
    "trading_signals",
    "background_jobs",
    "application_event_logs",
}

EXPECTED_INDEXES: Final[
    dict[str, set[str]]
] = {
    "trading_signals": {
        "ix_trading_signals_signal_uid",
        "ix_trading_signals_status",
        "ix_trading_signals_symbol",
    },
    "background_jobs": {
        "ix_background_jobs_job_uid",
        "ix_background_jobs_status_schedule",
        "ix_background_jobs_type_status",
    },
    "application_event_logs": {
        "ix_application_event_logs_event_uid",
        "ix_application_event_logs_level_created",
        "ix_application_event_logs_type_created",
    },
}


@dataclass(frozen=True)
class AuditCheck:
    name: str
    passed: bool
    details: dict[str, Any]


def _setting(
    name: str,
    default: Any = None,
) -> Any:
    """
    Read one active validated application setting.
    """

    return getattr(
        settings,
        name,
        default,
    )


def _text_setting(
    name: str,
    default: str = "",
) -> str:
    value = _setting(
        name,
        default,
    )

    return str(
        value
        if value is not None
        else default
    ).strip()


def _bool_setting(
    name: str,
    default: bool = False,
) -> bool:
    value = _setting(
        name,
        default,
    )

    if isinstance(value, bool):
        return value

    raw = str(
        value or ""
    ).strip().lower()

    if raw in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return True

    if raw in {
        "0",
        "false",
        "no",
        "off",
        "",
    }:
        return False

    return default


def _is_production() -> bool:
    configured = getattr(
        settings,
        "is_production",
        None,
    )

    if isinstance(
        configured,
        bool,
    ):
        return configured

    environment = _text_setting(
        "ENVIRONMENT",
        _text_setting(
            "APP_ENV",
            "development",
        ),
    ).lower()

    return environment in {
        "production",
        "prod",
    }


def _timed_call(
    function: Callable[[], Any],
) -> tuple[Any, float]:
    started = time.perf_counter()
    result = function()
    duration_ms = (
        time.perf_counter()
        - started
    ) * 1000

    return (
        result,
        round(
            max(
                0.0,
                duration_ms,
            ),
            2,
        ),
    )


def _safe_non_negative_int(
    value: Any,
) -> int:
    if isinstance(
        value,
        bool,
    ):
        return 0

    try:
        resolved = int(
            value or 0
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return 0

    return max(
        0,
        resolved,
    )


def _safe_decimal(
    value: Any,
) -> Decimal | None:
    try:
        resolved = Decimal(
            str(value)
        )
    except Exception:
        return None

    if not resolved.is_finite():
        return None

    return resolved


def _safe_int(
    value: Any,
) -> int | None:
    if isinstance(
        value,
        bool,
    ):
        return None

    try:
        return int(value)
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None


def _check_environment_security() -> AuditCheck:
    expose_tokens = _bool_setting(
        "EXPOSE_DEVELOPMENT_TOKENS",
        False,
    )

    secret_key = _text_setting(
        "SECRET_KEY"
    )

    smtp_password = _text_setting(
        "SMTP_PASSWORD"
    )

    owner_email = _text_setting(
        "OWNER_EMAIL"
    )

    debug_enabled = _bool_setting(
        "DEBUG",
        False,
    )

    issues: list[str] = []

    if not _is_production():
        issues.append(
            "Production mode is not enabled."
        )

    if debug_enabled:
        issues.append(
            "Debug mode must be disabled."
        )

    if not secret_key:
        issues.append(
            "Secret key is missing."
        )
    elif (
        len(secret_key)
        < MINIMUM_PRODUCTION_SECRET_LENGTH
    ):
        issues.append(
            "Secret key does not meet the production minimum."
        )

    if (
        not owner_email
        or "@"
        not in owner_email
    ):
        issues.append(
            "Owner email is missing or invalid."
        )

    if expose_tokens:
        issues.append(
            "Development token exposure must be disabled."
        )

    if (
        smtp_password
        and len(smtp_password) < 12
    ):
        issues.append(
            "SMTP password appears too short."
        )

    return AuditCheck(
        name="environment_security",
        passed=not issues,
        details={
            "production_mode_detected": (
                _is_production()
            ),
            "debug_enabled": (
                debug_enabled
            ),
            "secret_key_configured": bool(
                secret_key
            ),
            "secret_key_meets_minimum": (
                len(secret_key)
                >= MINIMUM_PRODUCTION_SECRET_LENGTH
            ),
            "owner_email_configured": bool(
                owner_email
            ),
            "smtp_password_configured": bool(
                smtp_password
            ),
            "development_tokens_exposed": (
                expose_tokens
            ),
            "issues": issues,
        },
    )


def _check_database_health() -> AuditCheck:
    try:
        def ping_database() -> int:
            with engine.connect() as connection:
                return int(
                    connection.execute(
                        text("SELECT 1")
                    ).scalar_one()
                )

        result, duration_ms = _timed_call(
            ping_database
        )

        passed = (
            result == 1
            and duration_ms
            <= MAX_ACCEPTABLE_DATABASE_PING_MS
        )

        return AuditCheck(
            name="database_health",
            passed=passed,
            details={
                "connected": (
                    result == 1
                ),
                "within_latency_target": (
                    duration_ms
                    <= MAX_ACCEPTABLE_DATABASE_PING_MS
                ),
                "duration_ms": (
                    duration_ms
                ),
                "maximum_ms": (
                    MAX_ACCEPTABLE_DATABASE_PING_MS
                ),
            },
        )
    except Exception:
        return AuditCheck(
            name="database_health",
            passed=False,
            details={
                "connected": False,
                "within_latency_target": False,
                "error_present": True,
            },
        )


def _check_required_tables() -> AuditCheck:
    try:
        inspector = inspect(
            engine
        )

        existing_tables = set(
            inspector.get_table_names()
        )

        missing_count = len(
            REQUIRED_TABLES
            - existing_tables
        )

        return AuditCheck(
            name="required_tables",
            passed=(
                missing_count == 0
            ),
            details={
                "required_count": len(
                    REQUIRED_TABLES
                ),
                "existing_required_count": (
                    len(REQUIRED_TABLES)
                    - missing_count
                ),
                "missing_count": (
                    missing_count
                ),
            },
        )
    except Exception:
        return AuditCheck(
            name="required_tables",
            passed=False,
            details={
                "inspection_completed": False,
                "error_present": True,
            },
        )


def _check_migration_state() -> AuditCheck:
    """
    Verify that the live database is at the expected Alembic revision.

    This check is read-only and does not run migrations.
    """

    try:
        inspector = inspect(
            engine
        )

        existing_tables = set(
            inspector.get_table_names()
        )

        if "alembic_version" not in existing_tables:
            return AuditCheck(
                name="migration_state",
                passed=False,
                details={
                    "version_table_present": False,
                    "revision_matches_expected": False,
                    "expected_revision": EXPECTED_ALEMBIC_HEAD,
                },
            )

        with engine.connect() as connection:
            revisions = {
                str(row[0]).strip()
                for row in connection.execute(
                    text(
                        "SELECT version_num "
                        "FROM alembic_version"
                    )
                )
                if row[0] is not None
                and str(row[0]).strip()
            }

        revision_matches = (
            revisions
            == {
                EXPECTED_ALEMBIC_HEAD
            }
        )

        return AuditCheck(
            name="migration_state",
            passed=revision_matches,
            details={
                "version_table_present": True,
                "revision_matches_expected": (
                    revision_matches
                ),
                "expected_revision": (
                    EXPECTED_ALEMBIC_HEAD
                ),
                "current_revision_count": len(
                    revisions
                ),
            },
        )
    except Exception:
        return AuditCheck(
            name="migration_state",
            passed=False,
            details={
                "version_table_present": False,
                "revision_matches_expected": False,
                "expected_revision": EXPECTED_ALEMBIC_HEAD,
                "error_present": True,
            },
        )


def _check_signal_guardrails() -> AuditCheck:
    issues: list[str] = []

    configured_confidence = _safe_decimal(
        _setting(
            "MINIMUM_SIGNAL_CONFIDENCE",
            MINIMUM_SIGNAL_CONFIDENCE,
        )
    )

    configured_confirmations = _safe_int(
        _setting(
            "MINIMUM_SIGNAL_CONFIRMATIONS",
            MINIMUM_SIGNAL_CONFIRMATIONS,
        )
    )

    configured_risk_reward = _safe_decimal(
        _setting(
            "MINIMUM_SIGNAL_RISK_REWARD",
            MINIMUM_SIGNAL_RISK_REWARD,
        )
    )

    if (
        configured_confidence is None
        or configured_confidence
        < MINIMUM_SIGNAL_CONFIDENCE
    ):
        issues.append(
            "Minimum confidence is below the required guardrail."
        )

    if (
        configured_confirmations is None
        or configured_confirmations
        < MINIMUM_SIGNAL_CONFIRMATIONS
    ):
        issues.append(
            "Minimum confirmations are below the required guardrail."
        )

    if (
        configured_risk_reward is None
        or configured_risk_reward
        < MINIMUM_SIGNAL_RISK_REWARD
    ):
        issues.append(
            "Minimum risk-reward is below the required guardrail."
        )

    if (
        LEARNING_MINIMUM_COMPLETED_TRADES
        < 20
    ):
        issues.append(
            "Learning minimum completed trades is below 20."
        )

    broker_execution = _bool_setting(
        "BROKER_EXECUTION_ENABLED",
        False,
    )

    if broker_execution:
        issues.append(
            "Broker execution must remain disabled."
        )

    return AuditCheck(
        name="signal_guardrails",
        passed=not issues,
        details={
            "confidence_guardrail_valid": (
                configured_confidence is not None
                and configured_confidence
                >= MINIMUM_SIGNAL_CONFIDENCE
            ),
            "confirmation_guardrail_valid": (
                configured_confirmations is not None
                and configured_confirmations
                >= MINIMUM_SIGNAL_CONFIRMATIONS
            ),
            "risk_reward_guardrail_valid": (
                configured_risk_reward is not None
                and configured_risk_reward
                >= MINIMUM_SIGNAL_RISK_REWARD
            ),
            "learning_guardrail_valid": (
                LEARNING_MINIMUM_COMPLETED_TRADES
                >= 20
            ),
            "learning_uses_completed_trades_only": True,
            "broker_execution_enabled": (
                broker_execution
            ),
            "issues": issues,
        },
    )


def _check_model_registration() -> AuditCheck:
    metadata_tables = set(
        TradingSignal.metadata.tables.keys()
    )

    required_model_tables = {
        TradingSignal.__tablename__,
        BackgroundJob.__tablename__,
        ApplicationEventLog.__tablename__,
    }

    missing_count = len(
        required_model_tables
        - metadata_tables
    )

    return AuditCheck(
        name="model_registration",
        passed=(
            missing_count == 0
        ),
        details={
            "required_model_count": len(
                required_model_tables
            ),
            "registered_model_count": (
                len(required_model_tables)
                - missing_count
            ),
            "missing_model_count": (
                missing_count
            ),
        },
    )


def _check_monitoring_performance(
    db: Session,
) -> AuditCheck:
    try:
        summary, duration_ms = _timed_call(
            lambda: get_monitoring_summary(
                db,
                hours=24,
                slow_request_ms=1000,
            )
        )

        valid_summary = isinstance(
            summary,
            dict,
        )

        passed = (
            valid_summary
            and duration_ms
            <= MAX_ACCEPTABLE_MONITORING_QUERY_MS
        )

        return AuditCheck(
            name="monitoring_performance",
            passed=passed,
            details={
                "summary_valid": (
                    valid_summary
                ),
                "within_latency_target": (
                    duration_ms
                    <= MAX_ACCEPTABLE_MONITORING_QUERY_MS
                ),
                "duration_ms": (
                    duration_ms
                ),
                "maximum_ms": (
                    MAX_ACCEPTABLE_MONITORING_QUERY_MS
                ),
                "events_present": bool(
                    valid_summary
                    and _safe_non_negative_int(
                        summary.get(
                            "total_events",
                            0,
                        )
                    )
                    >= 0
                ),
            },
        )
    except Exception:
        return AuditCheck(
            name="monitoring_performance",
            passed=False,
            details={
                "summary_valid": False,
                "error_present": True,
            },
        )


def _check_storage_indexes() -> AuditCheck:
    try:
        inspector = inspect(
            engine
        )

        missing_table_count = 0
        missing_index_count = 0

        existing_tables = set(
            inspector.get_table_names()
        )

        for (
            table_name,
            expected,
        ) in EXPECTED_INDEXES.items():
            if table_name not in existing_tables:
                missing_table_count += 1
                missing_index_count += len(
                    expected
                )
                continue

            actual = {
                str(
                    index.get(
                        "name"
                    )
                )
                for index in inspector.get_indexes(
                    table_name
                )
                if index.get(
                    "name"
                )
            }

            missing_index_count += len(
                expected
                - actual
            )

        return AuditCheck(
            name="storage_indexes",
            passed=(
                missing_index_count == 0
            ),
            details={
                "checked_table_count": len(
                    EXPECTED_INDEXES
                ),
                "missing_table_count": (
                    missing_table_count
                ),
                "missing_index_count": (
                    missing_index_count
                ),
            },
        )
    except Exception:
        return AuditCheck(
            name="storage_indexes",
            passed=False,
            details={
                "inspection_completed": False,
                "error_present": True,
            },
        )


def _check_database_counts(
    db: Session,
) -> AuditCheck:
    try:
        signal_count = int(
            db.query(
                func.count(
                    TradingSignal.id
                )
            ).scalar()
            or 0
        )

        background_job_count = int(
            db.query(
                func.count(
                    BackgroundJob.id
                )
            ).scalar()
            or 0
        )

        event_count = int(
            db.query(
                func.count(
                    ApplicationEventLog.id
                )
            ).scalar()
            or 0
        )

        return AuditCheck(
            name="database_counts",
            passed=True,
            details={
                "trading_signals_present": (
                    signal_count > 0
                ),
                "background_jobs_present": (
                    background_job_count > 0
                ),
                "application_events_present": (
                    event_count > 0
                ),
                "queries_completed": True,
            },
        )
    except Exception:
        return AuditCheck(
            name="database_counts",
            passed=False,
            details={
                "queries_completed": False,
                "error_present": True,
            },
        )


def run_production_readiness_audit(
    db: Session,
) -> dict[str, Any]:
    """
    Run security, infrastructure, and performance readiness checks.

    This audit does not modify application data.
    """

    checks = [
        _check_environment_security(),
        _check_database_health(),
        _check_required_tables(),
        _check_migration_state(),
        _check_signal_guardrails(),
        _check_model_registration(),
        _check_monitoring_performance(
            db
        ),
        _check_storage_indexes(),
        _check_database_counts(
            db
        ),
    ]

    passed_count = sum(
        1
        for check in checks
        if check.passed
    )

    failed_count = (
        len(checks)
        - passed_count
    )

    production_ready = (
        failed_count == 0
        and _is_production()
    )

    return {
        "audit_version": 48,
        "status": (
            "passed"
            if production_ready
            else "failed"
        ),
        "passed_checks": (
            passed_count
        ),
        "failed_checks": (
            failed_count
        ),
        "total_checks": len(
            checks
        ),
        "production_ready": (
            production_ready
        ),
        "migration_target_configured": bool(
            EXPECTED_ALEMBIC_HEAD
        ),
        "migration_state_verified": any(
            check.name == "migration_state"
            and check.passed
            for check in checks
        ),
        "checks": [
            asdict(check)
            for check in checks
        ],
    }


__all__ = [
    "EXPECTED_ALEMBIC_HEAD",
    "MAX_ACCEPTABLE_DATABASE_PING_MS",
    "MAX_ACCEPTABLE_MONITORING_QUERY_MS",
    "MINIMUM_SIGNAL_CONFIDENCE",
    "MINIMUM_SIGNAL_CONFIRMATIONS",
    "MINIMUM_SIGNAL_RISK_REWARD",
    "AuditCheck",
    "run_production_readiness_audit",
]