from __future__ import annotations

import os
import sys
from typing import Any

from app.services.email_service import (
    EmailConfigurationError,
    EmailDeliveryError,
    email_delivery_configured,
    load_email_settings,
    send_email,
    validate_email_settings,
)


OWNER_EMAIL = os.getenv(
    "OWNER_EMAIL",
    "bluetradingai06@gmail.com",
).strip().lower()


class ValidationFailure(Exception):
    pass


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise ValidationFailure(message)


def masked_email(
    email: str,
) -> str:
    if "@" not in email:
        return "***"

    local, domain = email.split("@", 1)

    if len(local) <= 2:
        safe_local = local[:1] + "***"
    else:
        safe_local = (
            local[:2]
            + "***"
            + local[-1:]
        )

    return f"{safe_local}@{domain}"


def main() -> int:
    print("=" * 64)
    print("BLUE TRADING AI - VERSION 40 SMTP TEST")
    print("=" * 64)

    try:
        print("\n[1/5] Loading SMTP configuration")

        settings = load_email_settings()

        require(
            settings.smtp_password
            not in {"", "YOUR_GMAIL_APP_PASSWORD"},
            (
                "SMTP_PASSWORD is missing or still uses "
                "the placeholder value."
            ),
        )

        print("PASSED")

        print("\n[2/5] Validating SMTP configuration")

        validate_email_settings(settings)

        require(
            email_delivery_configured() is True,
            "Email delivery is not detected as configured.",
        )

        print("PASSED")

        print("\n[3/5] Checking safe Gmail SMTP settings")

        require(
            settings.smtp_host == "smtp.gmail.com",
            (
                "Expected SMTP_HOST=smtp.gmail.com, got "
                f"{settings.smtp_host!r}"
            ),
        )

        require(
            settings.smtp_port in {465, 587},
            (
                "Gmail SMTP port should be 465 or 587, got "
                f"{settings.smtp_port}"
            ),
        )

        if settings.smtp_port == 587:
            require(
                settings.use_tls is True,
                "Port 587 requires SMTP_USE_TLS=true.",
            )
            require(
                settings.use_ssl is False,
                "Port 587 requires SMTP_USE_SSL=false.",
            )

        if settings.smtp_port == 465:
            require(
                settings.use_ssl is True,
                "Port 465 requires SMTP_USE_SSL=true.",
            )
            require(
                settings.use_tls is False,
                "Port 465 requires SMTP_USE_TLS=false.",
            )

        print("PASSED")

        print("\n[4/5] Preparing owner test email")

        require(
            OWNER_EMAIL
            == settings.smtp_username.strip().lower(),
            (
                "OWNER_EMAIL and SMTP_USERNAME do not match. "
                "This is allowed in production, but for the "
                "Version 40 owner test they should match."
            ),
        )

        recipient = OWNER_EMAIL

        print(
            "Recipient:",
            masked_email(recipient),
        )
        print("PASSED")

        print("\n[5/5] Sending SMTP test email")

        send_email(
            to_email=recipient,
            subject=(
                "Blue Trading AI Version 40 SMTP Test"
            ),
            text_body=(
                "Blue Trading AI SMTP delivery is working.\n\n"
                "Version 40 real email delivery test passed."
            ),
            html_body="""
            <html>
              <body style="font-family:Arial,sans-serif;line-height:1.6;">
                <h2>Blue Trading AI SMTP Test</h2>
                <p>
                  Your Version 40 real email delivery
                  configuration is working successfully.
                </p>
                <p>
                  Verification and password-reset emails
                  can now be delivered through SMTP.
                </p>
              </body>
            </html>
            """,
            settings=settings,
        )

        print("PASSED")

        print("\n" + "=" * 64)
        print("VERSION 40 SMTP TEST: 5/5 PASSED")
        print("=" * 64)
        print(
            "Check the inbox and spam folder for:",
            masked_email(OWNER_EMAIL),
        )

        return 0

    except EmailConfigurationError as exc:
        print(f"\nFAILED: Configuration error: {exc}")
        return 1
    except EmailDeliveryError as exc:
        print(
            "\nFAILED: Email could not be delivered. "
            "Check the App Password, SMTP settings, "
            "internet connection, and Gmail security."
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

