from __future__ import annotations

import os
import sys
from typing import Any

import requests

from app.services.deployment_validation_service import (
    MINIMUM_SECRET_LENGTH,
    RECOMMENDED_SECRET_LENGTH,
    run_deployment_validation,
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
    validation: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    checks = validation.get("checks")

    require(
        isinstance(checks, list),
        "Deployment checks must be a list.",
    )

    result: dict[str, dict[str, Any]] = {}

    for check in checks:
        require(
            isinstance(check, dict),
            "Each deployment check must be an object.",
        )

        name = str(
            check.get("name") or ""
        ).strip()

        require(
            bool(name),
            "Deployment check name is missing.",
        )

        result[name] = check

    return result


def main() -> int:
    print("=" * 74)
    print(
        "BLUE TRADING AI - VERSION 48 "
        "DEPLOYMENT VALIDATION TEST"
    )
    print("=" * 74)

    try:
        print_step(1, "API reports Version 48")

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
            str(payload.get("version")) == "48.0.0",
            f"Expected version 48.0.0, got {payload}",
        )

        require(
            payload.get(
                "deployment_preparation_enabled"
            )
            is True,
            "Deployment metadata is missing.",
        )

        print("PASSED")

        print_step(2, "Deployment API is available")

        response = requests.get(
            f"{BASE_URL}/deployment/",
            timeout=TIMEOUT,
        )

        require(
            response.status_code == 200,
            (
                "Deployment API failed: "
                f"{response.status_code} {response.text}"
            ),
        )

        deployment_home = json_body(response)

        require(
            deployment_home.get(
                "deployment_api_version"
            )
            == 48,
            "Deployment API version is incorrect.",
        )

        require(
            deployment_home.get(
                "validation_is_read_only"
            )
            is True,
            "Deployment validation must remain read-only.",
        )

        require(
            deployment_home.get(
                "broker_execution_enabled"
            )
            is False,
            "Broker execution must remain disabled.",
        )

        print("PASSED")

        print_step(3, "Protected deployment endpoints block anonymous access")

        for method, endpoint in (
            ("GET", "/deployment/status"),
            ("POST", "/deployment/validate"),
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

        print_step(4, "Secret-key requirements are correct")

        require(
            MINIMUM_SECRET_LENGTH == 32,
            "Minimum secret length must remain 32.",
        )

        require(
            RECOMMENDED_SECRET_LENGTH == 64,
            "Recommended secret length must remain 64.",
        )

        require(
            deployment_home.get(
                "minimum_secret_length"
            )
            == 32,
            "Deployment API minimum secret length is wrong.",
        )

        require(
            deployment_home.get(
                "recommended_secret_length"
            )
            == 64,
            "Deployment API recommended secret length is wrong.",
        )

        print("PASSED")

        print_step(5, "Deployment validation runs safely")

        validation = run_deployment_validation()

        require(
            validation.get(
                "deployment_validation_version"
            )
            == 48,
            "Deployment validation version is incorrect.",
        )

        require(
            int(validation.get("total_checks", 0))
            == 10,
            "Expected ten deployment checks.",
        )

        require(
            isinstance(
                validation.get("critical_failures"),
                list,
            ),
            "Critical failures must be a list.",
        )

        checks = check_map(validation)

        print("PASSED")

        print_step(6, "All required deployment checks exist")

        required_checks = {
            "application_environment",
            "secret_key",
            "owner_email",
            "development_token_exposure",
            "database_url",
            "cors",
            "public_urls",
            "smtp",
            "signal_safety",
            "logging_privacy",
        }

        missing = sorted(
            required_checks - set(checks)
        )

        require(
            not missing,
            f"Missing deployment checks: {missing}",
        )

        print("PASSED")

        print_step(7, "Signal safety rules remain enforced")

        signal_safety = checks[
            "signal_safety"
        ]

        details = signal_safety.get(
            "details",
            {},
        )

        require(
            details.get(
                "broker_execution_enabled"
            )
            is False,
            "Broker execution is enabled.",
        )

        require(
            float(
                details.get(
                    "minimum_confidence",
                    0,
                )
            )
            >= 80,
            "Minimum confidence is below 80.",
        )

        require(
            int(
                details.get(
                    "minimum_confirmations",
                    0,
                )
            )
            >= 3,
            "Minimum confirmations are below 3.",
        )

        require(
            float(
                details.get(
                    "minimum_risk_reward",
                    0,
                )
            )
            >= 1.5,
            "Minimum R:R is below 1.5.",
        )

        print("PASSED")

        print_step(8, "Logging privacy rules remain enforced")

        logging_privacy = checks[
            "logging_privacy"
        ]

        privacy_details = logging_privacy.get(
            "details",
            {},
        )

        require(
            privacy_details.get(
                "request_body_logging_enabled"
            )
            is False,
            "Request-body logging is enabled.",
        )

        require(
            privacy_details.get(
                "authorization_header_logging_enabled"
            )
            is False,
            "Authorization-header logging is enabled.",
        )

        require(
            privacy_details.get(
                "cookie_header_logging_enabled"
            )
            is False,
            "Cookie-header logging is enabled.",
        )

        print("PASSED")

        print_step(9, "Development environment failures are explicit")

        require(
            isinstance(
                validation.get(
                    "deployment_ready"
                ),
                bool,
            ),
            "Deployment-ready result must be boolean.",
        )

        require(
            int(
                validation.get(
                    "passed_checks",
                    -1,
                )
            )
            + int(
                validation.get(
                    "failed_checks",
                    -1,
                )
            )
            == 10,
            "Passed and failed totals are inconsistent.",
        )

        if validation.get(
            "deployment_ready"
        ) is True:
            print(
                "PASSED - production environment is valid"
            )
        else:
            print(
                "PASSED - development configuration "
                "was rejected correctly"
            )

            for failure in validation.get(
                "critical_failures",
                [],
            ):
                print(
                    f"  DEVELOPMENT BLOCKER: {failure}"
                )

        print_step(10, "Production template rules are present")

        required_rules = set(
            deployment_home.get(
                "required_production_rules",
                [],
            )
        )

        expected_rules = {
            "APP_ENV=production",
            "DEBUG=false",
            "EXPOSE_DEVELOPMENT_TOKENS=false",
            "BROKER_EXECUTION_ENABLED=false",
            "HTTPS frontend and backend URLs",
            "No wildcard CORS",
            "Production database required",
            "Sensitive request logging disabled",
        }

        require(
            expected_rules.issubset(
                required_rules
            ),
            "Deployment API is missing production rules.",
        )

        print("PASSED")

        print("\n" + "=" * 74)
        print(
            "VERSION 48 DEPLOYMENT VALIDATION TEST: "
            "10/10 PASSED"
        )
        print("=" * 74)

        if validation.get(
            "deployment_ready"
        ) is True:
            print(
                "DEPLOYMENT VALIDATION: PASSED"
            )
        else:
            print(
                "DEPLOYMENT VALIDATION: "
                "LOCAL DEVELOPMENT SETTINGS DETECTED"
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


if __name__ == "__main__":
    sys.exit(main())

