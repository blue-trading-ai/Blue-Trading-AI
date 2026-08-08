from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Final
from urllib.parse import urlparse

from app.core.config import settings


PRODUCTION_ENV_NAMES: Final[set[str]] = {
    "production",
    "prod",
}

MINIMUM_SECRET_LENGTH: Final[int] = 48
RECOMMENDED_SECRET_LENGTH: Final[int] = 64

PLACEHOLDER_MARKERS: Final[tuple[str, ...]] = (
    "change_me",
    "changeme",
    "replace_me",
    "example.com",
    "your_",
    "<",
    ">",
)

SUPPORTED_DATABASE_SCHEMES: Final[set[str]] = {
    "postgres",
    "postgresql",
    "postgresql+asyncpg",
    "postgresql+psycopg",
    "postgresql+psycopg2",
    "mysql",
    "mysql+pymysql",
    "mysql+mysqlconnector",
}


@dataclass(frozen=True)
class DeploymentCheck:
    name: str
    passed: bool
    severity: str
    message: str
    details: dict[str, Any]


def _setting(
    name: str,
    default: Any = None,
) -> Any:
    """
    Read one validated application setting.

    Deployment validation must inspect the same settings object used
    by the running application instead of reloading environment files.
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


def _contains_placeholder(
    value: str,
) -> bool:
    lowered = str(
        value or ""
    ).strip().lower()

    return any(
        marker in lowered
        for marker in PLACEHOLDER_MARKERS
    )


def _environment_name() -> str:
    return _text_setting(
        "ENVIRONMENT",
        _text_setting(
            "APP_ENV",
            "development",
        ),
    ).lower()


def _is_production() -> bool:
    production_flag = getattr(
        settings,
        "is_production",
        None,
    )

    if isinstance(
        production_flag,
        bool,
    ):
        return production_flag

    return (
        _environment_name()
        in PRODUCTION_ENV_NAMES
    )


def _safe_url_scheme(
    value: str,
) -> str:
    try:
        return urlparse(
            value
        ).scheme.lower()
    except ValueError:
        return ""


def _is_https_url(
    value: str,
) -> bool:
    try:
        parsed = urlparse(
            value
        )
    except ValueError:
        return False

    return bool(
        parsed.scheme.lower() == "https"
        and parsed.netloc
        and not parsed.username
        and not parsed.password
    )


def _as_finite_float(
    value: Any,
) -> float | None:
    if isinstance(
        value,
        bool,
    ):
        return None

    try:
        resolved = float(value)
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None

    if not math.isfinite(
        resolved
    ):
        return None

    return resolved


def _as_int(
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


def _check_application_environment() -> DeploymentCheck:
    environment = (
        _environment_name()
    )

    debug = _bool_setting(
        "DEBUG",
        False,
    )

    passed = (
        environment
        in PRODUCTION_ENV_NAMES
        and debug is False
    )

    return DeploymentCheck(
        name="application_environment",
        passed=passed,
        severity="critical",
        message=(
            "Production mode and debug settings are valid."
            if passed
            else (
                "Production environment is not fully enabled "
                "or debug mode remains active."
            )
        ),
        details={
            "production_mode_detected": (
                environment
                in PRODUCTION_ENV_NAMES
            ),
            "debug_enabled": debug,
        },
    )


def _check_secret_key() -> DeploymentCheck:
    secret_key = _text_setting(
        "SECRET_KEY"
    )

    issues: list[str] = []

    if not secret_key:
        issues.append(
            "Secret key is missing."
        )
    elif (
        len(secret_key)
        < MINIMUM_SECRET_LENGTH
    ):
        issues.append(
            "Secret key is shorter than the production minimum."
        )

    if (
        secret_key
        and _contains_placeholder(
            secret_key
        )
    ):
        issues.append(
            "Secret key contains a placeholder marker."
        )

    diversity = len(
        {
            "lower"
            if character.islower()
            else "upper"
            if character.isupper()
            else "digit"
            if character.isdigit()
            else "symbol"
            for character in secret_key
        }
    )

    if secret_key and diversity < 3:
        issues.append(
            "Secret key character diversity is insufficient."
        )

    passed = not issues

    return DeploymentCheck(
        name="secret_key",
        passed=passed,
        severity="critical",
        message=(
            "Secret key configuration is secure."
            if passed
            else "Secret key configuration is unsafe."
        ),
        details={
            "configured": bool(
                secret_key
            ),
            "meets_minimum_length": (
                len(secret_key)
                >= MINIMUM_SECRET_LENGTH
            ),
            "meets_recommended_length": (
                len(secret_key)
                >= RECOMMENDED_SECRET_LENGTH
            ),
            "issues": issues,
        },
    )


def _check_owner_email() -> DeploymentCheck:
    owner_email = _text_setting(
        "OWNER_EMAIL"
    ).lower()

    local, separator, domain = (
        owner_email.partition("@")
    )

    passed = bool(
        local
        and separator
        and domain
        and "." in domain
        and not _contains_placeholder(
            owner_email
        )
    )

    return DeploymentCheck(
        name="owner_email",
        passed=passed,
        severity="critical",
        message=(
            "Owner email is configured."
            if passed
            else "Owner email is missing or invalid."
        ),
        details={
            "configured": bool(
                owner_email
            ),
            "valid_format": passed,
        },
    )


def _check_development_token_exposure() -> DeploymentCheck:
    exposed = _bool_setting(
        "EXPOSE_DEVELOPMENT_TOKENS",
        False,
    )

    passed = exposed is False

    return DeploymentCheck(
        name="development_token_exposure",
        passed=passed,
        severity="critical",
        message=(
            "Development tokens are hidden."
            if passed
            else (
                "Development token exposure must be disabled."
            )
        ),
        details={
            "development_tokens_exposed": exposed,
        },
    )


def _check_database_url() -> DeploymentCheck:
    database_url = _text_setting(
        "DATABASE_URL"
    )

    issues: list[str] = []

    scheme = _safe_url_scheme(
        database_url
    )

    if not database_url:
        issues.append(
            "Database URL is missing."
        )
    elif _contains_placeholder(
        database_url
    ):
        issues.append(
            "Database URL contains a placeholder marker."
        )

    if scheme.startswith(
        "sqlite"
    ):
        issues.append(
            "SQLite is not accepted for production deployment."
        )
    elif (
        database_url
        and scheme
        not in SUPPORTED_DATABASE_SCHEMES
    ):
        issues.append(
            "Database URL uses an unsupported production scheme."
        )

    passed = not issues

    return DeploymentCheck(
        name="database_url",
        passed=passed,
        severity="critical",
        message=(
            "Production database configuration is valid."
            if passed
            else "Production database configuration is unsafe."
        ),
        details={
            "configured": bool(
                database_url
            ),
            "supported_scheme": (
                scheme
                in SUPPORTED_DATABASE_SCHEMES
            ),
            "uses_sqlite": (
                scheme.startswith(
                    "sqlite"
                )
            ),
            "issues": issues,
        },
    )


def _cors_origins() -> list[str]:
    configured = getattr(
        settings,
        "cors_origin_list",
        None,
    )

    if configured is None:
        configured = _setting(
            "CORS_ORIGINS",
            [],
        )

    if isinstance(
        configured,
        str,
    ):
        origins = configured.split(",")
    elif isinstance(
        configured,
        (
            list,
            tuple,
            set,
        ),
    ):
        origins = list(
            configured
        )
    else:
        origins = []

    return list(
        dict.fromkeys(
            str(origin).strip()
            for origin in origins
            if str(origin).strip()
        )
    )


def _check_cors() -> DeploymentCheck:
    origins = _cors_origins()

    issues: list[str] = []

    if not origins:
        issues.append(
            "CORS origins are missing."
        )

    wildcard_present = (
        "*" in origins
    )

    if wildcard_present:
        issues.append(
            "Wildcard CORS origin is not allowed."
        )

    insecure_origin_count = sum(
        1
        for origin in origins
        if not _is_https_url(
            origin
        )
    )

    if insecure_origin_count:
        issues.append(
            "One or more CORS origins do not use a valid HTTPS URL."
        )

    placeholder_present = any(
        _contains_placeholder(
            origin
        )
        for origin in origins
    )

    if placeholder_present:
        issues.append(
            "One or more CORS origins contain placeholder markers."
        )

    passed = not issues

    return DeploymentCheck(
        name="cors",
        passed=passed,
        severity="critical",
        message=(
            "CORS configuration is production-safe."
            if passed
            else "CORS configuration is unsafe."
        ),
        details={
            "origin_count": len(
                origins
            ),
            "wildcard_present": (
                wildcard_present
            ),
            "insecure_origin_count": (
                insecure_origin_count
            ),
            "placeholder_present": (
                placeholder_present
            ),
            "issues": issues,
        },
    )


def _check_public_urls() -> DeploymentCheck:
    backend_url = _text_setting(
        "BACKEND_URL"
    )

    frontend_url = _text_setting(
        "FRONTEND_URL"
    )

    values = (
        backend_url,
        frontend_url,
    )

    missing_count = sum(
        1
        for value in values
        if not value
    )

    invalid_https_count = sum(
        1
        for value in values
        if value
        and not _is_https_url(
            value
        )
    )

    placeholder_count = sum(
        1
        for value in values
        if value
        and _contains_placeholder(
            value
        )
    )

    issues: list[str] = []

    if missing_count:
        issues.append(
            "One or more public URLs are missing."
        )

    if invalid_https_count:
        issues.append(
            "One or more public URLs are not valid HTTPS URLs."
        )

    if placeholder_count:
        issues.append(
            "One or more public URLs contain placeholder markers."
        )

    passed = not issues

    return DeploymentCheck(
        name="public_urls",
        passed=passed,
        severity="critical",
        message=(
            "Public deployment URLs are valid."
            if passed
            else "Public deployment URLs are invalid."
        ),
        details={
            "backend_url_configured": bool(
                backend_url
            ),
            "frontend_url_configured": bool(
                frontend_url
            ),
            "invalid_https_count": (
                invalid_https_count
            ),
            "placeholder_count": (
                placeholder_count
            ),
            "issues": issues,
        },
    )


def _check_smtp() -> DeploymentCheck:
    smtp_host = _text_setting(
        "SMTP_HOST"
    )

    smtp_username = _text_setting(
        "SMTP_USERNAME"
    )

    smtp_password = _text_setting(
        "SMTP_PASSWORD"
    )

    email_from = _text_setting(
        "EMAIL_FROM_ADDRESS"
    )

    values = {
        "host": smtp_host,
        "username": smtp_username,
        "password": smtp_password,
        "from_address": email_from,
    }

    missing_count = sum(
        1
        for value in values.values()
        if not value
    )

    placeholder_count = sum(
        1
        for value in values.values()
        if value
        and _contains_placeholder(
            value
        )
    )

    issues: list[str] = []

    if missing_count:
        issues.append(
            "SMTP configuration is incomplete."
        )

    if placeholder_count:
        issues.append(
            "SMTP configuration contains placeholder markers."
        )

    if (
        smtp_password
        and len(smtp_password) < 12
    ):
        issues.append(
            "SMTP password appears too short."
        )

    owner_from_valid = bool(
        email_from
        and "@"
        in email_from
    )

    if (
        email_from
        and not owner_from_valid
    ):
        issues.append(
            "Email sender address is invalid."
        )

    passed = not issues

    return DeploymentCheck(
        name="smtp",
        passed=passed,
        severity="high",
        message=(
            "SMTP configuration is valid."
            if passed
            else "SMTP configuration is incomplete or unsafe."
        ),
        details={
            "host_configured": bool(
                smtp_host
            ),
            "username_configured": bool(
                smtp_username
            ),
            "password_configured": bool(
                smtp_password
            ),
            "from_address_configured": bool(
                email_from
            ),
            "issues": issues,
        },
    )


def _check_signal_safety() -> DeploymentCheck:
    broker_execution = _bool_setting(
        "BROKER_EXECUTION_ENABLED",
        False,
    )

    confidence = _as_finite_float(
        _setting(
            "MINIMUM_SIGNAL_CONFIDENCE",
            80,
        )
    )

    confirmations = _as_int(
        _setting(
            "MINIMUM_SIGNAL_CONFIRMATIONS",
            3,
        )
    )

    risk_reward = _as_finite_float(
        _setting(
            "MINIMUM_SIGNAL_RISK_REWARD",
            1.5,
        )
    )

    issues: list[str] = []

    if broker_execution:
        issues.append(
            "Broker execution must remain disabled."
        )

    if (
        confidence is None
        or confidence < 80
        or confidence > 100
    ):
        issues.append(
            "Minimum signal confidence is invalid."
        )

    if (
        confirmations is None
        or confirmations < 3
        or confirmations > 100
    ):
        issues.append(
            "Minimum signal confirmations are invalid."
        )

    if (
        risk_reward is None
        or risk_reward < 1.5
        or risk_reward > 100
    ):
        issues.append(
            "Minimum signal risk-reward is invalid."
        )

    passed = not issues

    return DeploymentCheck(
        name="signal_safety",
        passed=passed,
        severity="critical",
        message=(
            "Signal safety rules are valid."
            if passed
            else "Signal safety rules are unsafe."
        ),
        details={
            "broker_execution_enabled": (
                broker_execution
            ),
            "confidence_rule_valid": (
                confidence is not None
                and 80
                <= confidence
                <= 100
            ),
            "confirmation_rule_valid": (
                confirmations is not None
                and 3
                <= confirmations
                <= 100
            ),
            "risk_reward_rule_valid": (
                risk_reward is not None
                and 1.5
                <= risk_reward
                <= 100
            ),
            "issues": issues,
        },
    )


def _check_logging_privacy() -> DeploymentCheck:
    request_body_logging = _bool_setting(
        "REQUEST_BODY_LOGGING_ENABLED",
        False,
    )

    authorization_logging = _bool_setting(
        "AUTHORIZATION_HEADER_LOGGING_ENABLED",
        False,
    )

    cookie_logging = _bool_setting(
        "COOKIE_HEADER_LOGGING_ENABLED",
        False,
    )

    issues: list[str] = []

    if request_body_logging:
        issues.append(
            "Request-body logging must remain disabled."
        )

    if authorization_logging:
        issues.append(
            "Authorization-header logging must remain disabled."
        )

    if cookie_logging:
        issues.append(
            "Cookie-header logging must remain disabled."
        )

    passed = not issues

    return DeploymentCheck(
        name="logging_privacy",
        passed=passed,
        severity="critical",
        message=(
            "Logging privacy settings are safe."
            if passed
            else "Logging privacy settings are unsafe."
        ),
        details={
            "request_body_logging_enabled": (
                request_body_logging
            ),
            "authorization_header_logging_enabled": (
                authorization_logging
            ),
            "cookie_header_logging_enabled": (
                cookie_logging
            ),
            "issues": issues,
        },
    )


def run_deployment_validation() -> dict[str, Any]:
    """
    Validate the active application settings without modifying them.
    """

    checks = [
        _check_application_environment(),
        _check_secret_key(),
        _check_owner_email(),
        _check_development_token_exposure(),
        _check_database_url(),
        _check_cors(),
        _check_public_urls(),
        _check_smtp(),
        _check_signal_safety(),
        _check_logging_privacy(),
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

    critical_failures = [
        check.name
        for check in checks
        if (
            not check.passed
            and check.severity
            == "critical"
        )
    ]

    deployment_ready = (
        failed_count == 0
        and _is_production()
    )

    return {
        "deployment_validation_version": 49,
        "production_mode_detected": (
            _is_production()
        ),
        "status": (
            "passed"
            if deployment_ready
            else "failed"
        ),
        "deployment_ready": (
            deployment_ready
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
        "critical_failures": (
            critical_failures
        ),
        "checks": [
            asdict(check)
            for check in checks
        ],
    }


__all__ = [
    "DeploymentCheck",
    "MINIMUM_SECRET_LENGTH",
    "RECOMMENDED_SECRET_LENGTH",
    "run_deployment_validation",
]