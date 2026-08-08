from __future__ import annotations

import os
import sys
from decimal import Decimal
from typing import Any

import requests

from app.database.connection import SessionLocal
from app.services.production_readiness_audit_service import (
    EXPECTED_ALEMBIC_HEAD,
    MAX_ACCEPTABLE_DATABASE_PING_MS,
    MAX_ACCEPTABLE_MONITORING_QUERY_MS,
    MINIMUM_SIGNAL_CONFIDENCE,
    MINIMUM_SIGNAL_CONFIRMATIONS,
    MINIMUM_SIGNAL_RISK_REWARD,
    run_production_readiness_audit,
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


def check_map(
    audit: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    checks = audit.get("checks")

    require(
        isinstance(checks, list),
        "Audit checks must be a list.",
    )

    result: dict[str, dict[str, Any]] = {}

    for check in checks:
        require(
            isinstance(check, dict),
            "Each audit check must be an object.",
        )

        name = str(
            check.get("name") or ""
        ).strip()

        require(
            bool(name),
            "Audit check name is missing.",
        )

        result[name] = check

    return result


def main() -> int:
    print("=" * 74)
    print(
        "BLUE TRADING AI - VERSION 47 "
        "SECURITY AND PERFORMANCE TEST"
    )
    print("=" * 74)

    db = None

    try:
        print_step(1, "API reports Version 47")

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
            str(payload.get("version")) == "47.0.0",
            f"Expected version 47.0.0, got {payload}",
        )

        require(
            payload.get(
                "production_readiness_audit_enabled"
            )
            is True,
            "Readiness metadata is missing.",
        )

        print("PASSED")

        print_step(2, "Readiness API is available")

        response = requests.get(
            f"{BASE_URL}/readiness/",
            timeout=TIMEOUT,
        )

        require(
            response.status_code == 200,
            (
                "Readiness API failed: "
                f"{response.status_code} {response.text}"
            ),
        )

        readiness_home = json_body(response)

        require(
            readiness_home.get(
                "readiness_api_version"
            )
            == 47,
            "Readiness API version is incorrect.",
        )

        require(
            readiness_home.get(
                "audit_is_read_only"
            )
            is True,
            "Readiness audit must remain read-only.",
        )

        require(
            readiness_home.get(
                "broker_execution_enabled"
            )
            is False,
            "Broker execution must remain disabled.",
        )

        print("PASSED")

        print_step(3, "Protected readiness endpoints block anonymous access")

        for method, endpoint in (
            ("GET", "/readiness/status"),
            ("POST", "/readiness/audit"),
        ):
            response = requests.request(
                method,
                f"{BASE_URL}{endpoint}",
                timeout=TIMEOUT,
            )

            require(
                response.status_code in {401, 403},
                (
                    f"Anonymous {method} {endpoint} "
                    f"was not blocked: "
                    f"{response.status_code} {response.text}"
                ),
            )

        print("PASSED")

        print_step(4, "Security thresholds remain correct")

        require(
            MINIMUM_SIGNAL_CONFIDENCE
            == Decimal("80"),
            "Minimum confidence must be 80.",
        )

        require(
            MINIMUM_SIGNAL_CONFIRMATIONS == 3,
            "Minimum confirmations must be 3.",
        )

        require(
            MINIMUM_SIGNAL_RISK_REWARD
            == Decimal("1.5"),
            "Minimum R:R must be 1.5.",
        )

        require(
            MAX_ACCEPTABLE_DATABASE_PING_MS
            == 500.0,
            "Database timing threshold changed.",
        )

        require(
            MAX_ACCEPTABLE_MONITORING_QUERY_MS
            == 1500.0,
            "Monitoring timing threshold changed.",
        )

        print("PASSED")

        db = SessionLocal()

        print_step(5, "Production-readiness audit runs")

        audit = run_production_readiness_audit(
            db
        )

        require(
            audit.get("audit_version") == 47,
            "Audit version is incorrect.",
        )

        require(
            int(audit.get("total_checks", 0))
            == 8,
            "Expected eight readiness checks.",
        )

        require(
            audit.get("expected_alembic_head")
            == EXPECTED_ALEMBIC_HEAD,
            "Expected Alembic head is incorrect.",
        )

        checks = check_map(audit)

        print("PASSED")

        print_step(6, "Database and required tables pass")

        database_health = checks.get(
            "database_health"
        )
        required_tables = checks.get(
            "required_tables"
        )
        model_registration = checks.get(
            "model_registration"
        )

        require(
            database_health is not None
            and database_health.get("passed")
            is True,
            (
                "Database health failed: "
                f"{database_health}"
            ),
        )

        require(
            required_tables is not None
            and required_tables.get("passed")
            is True,
            (
                "Required tables failed: "
                f"{required_tables}"
            ),
        )

        require(
            model_registration is not None
            and model_registration.get("passed")
            is True,
            (
                "Model registration failed: "
                f"{model_registration}"
            ),
        )

        print("PASSED")

        print_step(7, "Signal guardrails pass")

        guardrails = checks.get(
            "signal_guardrails"
        )

        require(
            guardrails is not None
            and guardrails.get("passed") is True,
            (
                "Signal guardrails failed: "
                f"{guardrails}"
            ),
        )

        details = guardrails.get(
            "details",
            {},
        )

        require(
            details.get("minimum_confidence")
            == "80",
            "Audit confidence threshold is wrong.",
        )

        require(
            details.get("minimum_confirmations")
            == 3,
            "Audit confirmation threshold is wrong.",
        )

        require(
            details.get("minimum_risk_reward")
            == "1.5",
            "Audit R:R threshold is wrong.",
        )

        require(
            details.get(
                "learning_minimum_completed_trades"
            )
            == 20,
            "Learning threshold is wrong.",
        )

        require(
            details.get(
                "broker_execution_enabled"
            )
            is False,
            "Audit enabled broker execution.",
        )

        print("PASSED")

        print_step(8, "Monitoring performance and indexes pass")

        monitoring = checks.get(
            "monitoring_performance"
        )
        indexes = checks.get(
            "storage_indexes"
        )

        require(
            monitoring is not None
            and monitoring.get("passed") is True,
            (
                "Monitoring performance failed: "
                f"{monitoring}"
            ),
        )

        require(
            indexes is not None
            and indexes.get("passed") is True,
            (
                "Storage index verification failed: "
                f"{indexes}"
            ),
        )

        print("PASSED")

        print_step(9, "Database count check is read-only and valid")

        counts = checks.get(
            "database_counts"
        )

        require(
            counts is not None
            and counts.get("passed") is True,
            f"Database count check failed: {counts}",
        )

        count_details = counts.get(
            "details",
            {},
        )

        for key in (
            "trading_signals",
            "background_jobs",
            "application_event_logs",
        ):
            require(
                int(count_details.get(key, -1)) >= 0,
                f"Invalid database count for {key}.",
            )

        print("PASSED")

        print_step(10, "Environment security result is explicit")

        environment = checks.get(
            "environment_security"
        )

        require(
            environment is not None,
            "Environment-security check is missing.",
        )

        environment_details = environment.get(
            "details",
            {},
        )

        require(
            "development_tokens_exposed"
            in environment_details,
            (
                "Development-token exposure result "
                "is missing."
            ),
        )

        require(
            isinstance(
                environment_details.get(
                    "issues"
                ),
                list,
            ),
            "Environment issues must be a list.",
        )

        if environment.get("passed") is True:
            print(
                "PASSED - environment is production-ready"
            )
        else:
            print(
                "PASSED - development environment warning "
                "was reported correctly"
            )

            for issue in environment_details.get(
                "issues",
                [],
            ):
                print(f"  WARNING: {issue}")

        print("\n" + "=" * 74)
        print(
            "VERSION 47 SECURITY AND PERFORMANCE TEST: "
            "10/10 PASSED"
        )
        print("=" * 74)

        if audit.get("production_ready") is True:
            print(
                "PRODUCTION READINESS AUDIT: PASSED"
            )
        else:
            print(
                "PRODUCTION READINESS AUDIT: "
                "DEVELOPMENT WARNINGS REMAIN"
            )

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
            db.close()


if __name__ == "__main__":
    sys.exit(main())

