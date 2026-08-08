from __future__ import annotations

import os
import sys
from typing import Any

import requests

from app.database.connection import SessionLocal
from app.models.application_event_log import (
    ApplicationEventLog,
    EVENT_TYPE_HTTP_REQUEST,
    LOG_LEVEL_ERROR,
    LOG_LEVEL_INFO,
)
from app.services.application_logging_service import (
    create_application_event,
    get_monitoring_summary,
    get_slow_requests,
    hash_client_ip,
    sanitise_metadata,
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


def main() -> int:
    print("=" * 72)
    print("BLUE TRADING AI - VERSION 46 MONITORING TEST")
    print("=" * 72)

    created_ids: list[int] = []
    db = None

    try:
        print_step(1, "API reports Version 46")

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
            str(payload.get("version")) == "46.0.0",
            f"Expected version 46.0.0, got {payload}",
        )

        require(
            payload.get(
                "production_logging_enabled"
            )
            is True,
            "Production logging metadata is missing.",
        )

        print("PASSED")

        print_step(2, "Request ID and response time headers exist")

        response = requests.get(
            f"{BASE_URL}/health",
            timeout=TIMEOUT,
        )

        require(
            response.status_code == 200,
            (
                "Health request failed: "
                f"{response.status_code} {response.text}"
            ),
        )

        require(
            "X-Request-ID" in response.headers,
            "X-Request-ID header is missing.",
        )

        require(
            "X-Response-Time-Ms" in response.headers,
            "X-Response-Time-Ms header is missing.",
        )

        require(
            float(
                response.headers[
                    "X-Response-Time-Ms"
                ]
            )
            >= 0,
            "Response-time header is invalid.",
        )

        print("PASSED")

        print_step(3, "Monitoring API is available")

        response = requests.get(
            f"{BASE_URL}/monitoring/",
            timeout=TIMEOUT,
        )

        require(
            response.status_code == 200,
            (
                "Monitoring API failed: "
                f"{response.status_code} {response.text}"
            ),
        )

        monitoring_home = json_body(response)

        require(
            monitoring_home.get(
                "monitoring_api_version"
            )
            == 46,
            "Monitoring API version is incorrect.",
        )

        require(
            monitoring_home.get(
                "request_body_logging_enabled"
            )
            is False,
            "Request-body logging must remain disabled.",
        )

        print("PASSED")

        print_step(4, "Protected monitoring endpoint blocks anonymous access")

        response = requests.get(
            f"{BASE_URL}/monitoring/summary",
            timeout=TIMEOUT,
        )

        require(
            response.status_code in {401, 403},
            (
                "Anonymous monitoring access was not blocked: "
                f"{response.status_code} {response.text}"
            ),
        )

        print("PASSED")

        db = SessionLocal()

        print_step(5, "Sensitive metadata is redacted")

        sanitized = sanitise_metadata(
            {
                "username": "tester",
                "password": "super-secret",
                "access_token": "abc123",
                "nested": {
                    "authorization": (
                        "Bearer secret-token-value"
                    ),
                    "safe": "visible",
                },
            }
        )

        require(
            sanitized["password"] == "[REDACTED]",
            "Password was not redacted.",
        )

        require(
            sanitized["access_token"] == "[REDACTED]",
            "Access token was not redacted.",
        )

        require(
            sanitized["nested"]["authorization"]
            == "[REDACTED]",
            "Authorization value was not redacted.",
        )

        require(
            sanitized["nested"]["safe"] == "visible",
            "Safe metadata was changed unexpectedly.",
        )

        print("PASSED")

        print_step(6, "Client IP is hashed")

        ip_hash = hash_client_ip(
            "127.0.0.1"
        )

        require(
            ip_hash is not None,
            "Client IP hash was not created.",
        )

        require(
            ip_hash != "127.0.0.1",
            "Raw client IP was returned.",
        )

        require(
            len(ip_hash) == 64,
            "Expected SHA-256 client IP hash.",
        )

        print("PASSED")

        print_step(7, "Structured events are stored safely")

        normal_event = create_application_event(
            db,
            level=LOG_LEVEL_INFO,
            event_type=EVENT_TYPE_HTTP_REQUEST,
            event_name="v46_test_request",
            message="Test request completed.",
            source="v46_test",
            request_id="REQ-V46-TEST-1",
            method="GET",
            path="/v46/test?token=[REDACTED]",
            status_code=200,
            duration_ms=1500.0,
            client_ip="127.0.0.1",
            metadata={
                "password": "should-not-store",
                "safe": "stored",
            },
            commit=True,
        )
        created_ids.append(int(normal_event.id))

        error_event = create_application_event(
            db,
            level=LOG_LEVEL_ERROR,
            event_type=EVENT_TYPE_HTTP_REQUEST,
            event_name="v46_test_error",
            message="Test server error.",
            source="v46_test",
            request_id="REQ-V46-TEST-2",
            method="POST",
            path="/v46/error",
            status_code=500,
            duration_ms=2500.0,
            client_ip="127.0.0.1",
            exception_type="TestError",
            exception_message=(
                "Bearer secret-token-should-redact"
            ),
            metadata={
                "refresh_token": "should-not-store",
            },
            commit=True,
        )
        created_ids.append(int(error_event.id))

        require(
            normal_event.client_ip_hash is not None,
            "Stored event has no client IP hash.",
        )

        require(
            normal_event.metadata_json["password"]
            == "[REDACTED]",
            "Stored metadata contains a password.",
        )

        require(
            "[REDACTED]"
            in str(error_event.exception_message),
            "Exception token was not redacted.",
        )

        print("PASSED")

        print_step(8, "Monitoring summary is calculated")

        summary = get_monitoring_summary(
            db,
            hours=24,
            slow_request_ms=1000,
        )

        require(
            int(summary["total_events"]) >= 2,
            "Monitoring summary event count is incorrect.",
        )

        require(
            int(summary["request_count"]) >= 2,
            "Monitoring summary request count is incorrect.",
        )

        require(
            int(summary["server_error_requests"]) >= 1,
            "Server error count is incorrect.",
        )

        require(
            float(summary["maximum_request_ms"])
            >= 2500.0,
            "Maximum response time is incorrect.",
        )

        print("PASSED")

        print_step(9, "Slow requests are detected")

        slow_requests = get_slow_requests(
            db,
            threshold_ms=1000,
            hours=24,
            limit=10,
        )

        slow_ids = {
            int(event.id)
            for event in slow_requests
        }

        require(
            int(normal_event.id) in slow_ids,
            "Normal slow request was not detected.",
        )

        require(
            int(error_event.id) in slow_ids,
            "Error slow request was not detected.",
        )

        print("PASSED")

        print_step(10, "HTTP middleware stored request activity")

        request_id = response.headers.get(
            "X-Request-ID"
        )

        middleware_event = (
            db.query(ApplicationEventLog)
            .filter(
                ApplicationEventLog.request_id
                == request_id
            )
            .first()
        )

        require(
            middleware_event is not None,
            (
                "No middleware event was stored for "
                "the test request."
            ),
        )

        require(
            middleware_event.metadata_json.get(
                "request_body_logged"
            )
            is False,
            "Middleware claimed to log request bodies.",
        )

        print("PASSED")

        print("\n" + "=" * 72)
        print(
            "VERSION 46 LOGGING AND MONITORING TEST: "
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
                for event_id in created_ids:
                    record = (
                        db.query(ApplicationEventLog)
                        .filter(
                            ApplicationEventLog.id
                            == int(event_id)
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

