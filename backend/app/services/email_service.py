from __future__ import annotations

import html
import logging
import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Final
from urllib.parse import quote

from dotenv import load_dotenv


load_dotenv()

LOGGER = logging.getLogger(__name__)

DEFAULT_SMTP_PORT: Final[int] = 587
DEFAULT_TIMEOUT_SECONDS: Final[int] = 20
DEFAULT_FRONTEND_URL: Final[str] = "http://127.0.0.1:3000"


class EmailConfigurationError(RuntimeError):
    """
    Raised when required email configuration is missing.
    """


class EmailDeliveryError(RuntimeError):
    """
    Raised when an email could not be delivered.
    """


@dataclass(frozen=True)
class EmailSettings:
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    sender_email: str
    sender_name: str
    use_tls: bool
    use_ssl: bool
    timeout_seconds: int
    frontend_url: str

    @property
    def configured(self) -> bool:
        return all(
            [
                self.smtp_host,
                self.smtp_username,
                self.smtp_password,
                self.sender_email,
            ]
        )


def _env_bool(
    name: str,
    default: bool,
) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _env_int(
    name: str,
    default: int,
) -> int:
    raw_value = os.getenv(name)

    if raw_value is None:
        return default

    try:
        return int(raw_value.strip())
    except ValueError as exc:
        raise EmailConfigurationError(
            f"{name} must be a valid integer."
        ) from exc


def load_email_settings() -> EmailSettings:
    """
    Load SMTP and frontend configuration from environment variables.
    """

    sender_email = os.getenv(
        "EMAIL_FROM_ADDRESS",
        os.getenv("SMTP_USERNAME", ""),
    ).strip()

    return EmailSettings(
        smtp_host=os.getenv(
            "SMTP_HOST",
            "",
        ).strip(),
        smtp_port=_env_int(
            "SMTP_PORT",
            DEFAULT_SMTP_PORT,
        ),
        smtp_username=os.getenv(
            "SMTP_USERNAME",
            "",
        ).strip(),
        smtp_password=os.getenv(
            "SMTP_PASSWORD",
            "",
        ),
        sender_email=sender_email,
        sender_name=os.getenv(
            "EMAIL_FROM_NAME",
            "Blue Trading AI",
        ).strip()
        or "Blue Trading AI",
        use_tls=_env_bool(
            "SMTP_USE_TLS",
            True,
        ),
        use_ssl=_env_bool(
            "SMTP_USE_SSL",
            False,
        ),
        timeout_seconds=_env_int(
            "SMTP_TIMEOUT_SECONDS",
            DEFAULT_TIMEOUT_SECONDS,
        ),
        frontend_url=os.getenv(
            "FRONTEND_URL",
            DEFAULT_FRONTEND_URL,
        ).strip().rstrip("/"),
    )


def validate_email_settings(
    settings: EmailSettings,
) -> None:
    """
    Validate email settings before attempting delivery.
    """

    missing: list[str] = []

    if not settings.smtp_host:
        missing.append("SMTP_HOST")

    if not settings.smtp_username:
        missing.append("SMTP_USERNAME")

    if not settings.smtp_password:
        missing.append("SMTP_PASSWORD")

    if not settings.sender_email:
        missing.append("EMAIL_FROM_ADDRESS")

    if missing:
        raise EmailConfigurationError(
            "Missing email configuration: "
            + ", ".join(missing)
        )

    if settings.use_tls and settings.use_ssl:
        raise EmailConfigurationError(
            "SMTP_USE_TLS and SMTP_USE_SSL cannot both be true."
        )

    if settings.smtp_port <= 0:
        raise EmailConfigurationError(
            "SMTP_PORT must be greater than zero."
        )

    if settings.timeout_seconds <= 0:
        raise EmailConfigurationError(
            "SMTP_TIMEOUT_SECONDS must be greater than zero."
        )

    _validate_email_address(
        settings.smtp_username,
        "SMTP_USERNAME",
    )
    _validate_email_address(
        settings.sender_email,
        "EMAIL_FROM_ADDRESS",
    )

    if "\r" in settings.sender_name or "\n" in settings.sender_name:
        raise EmailConfigurationError(
            "EMAIL_FROM_NAME contains invalid characters."
        )


def _validate_email_address(value: str, field_name: str) -> str:
    """
    Normalize and validate one mailbox address for SMTP/header use.
    """
    candidate = str(value or "").strip()

    if not candidate or "\r" in candidate or "\n" in candidate:
        raise EmailConfigurationError(
            f"{field_name} must be a valid email address."
        )

    display_name, address = parseaddr(candidate)

    if display_name or not address or "@" not in address:
        raise EmailConfigurationError(
            f"{field_name} must contain only one email address."
        )

    local_part, _, domain_part = address.rpartition("@")

    if (
        not local_part
        or not domain_part
        or "." not in domain_part
        or any(character.isspace() for character in address)
    ):
        raise EmailConfigurationError(
            f"{field_name} must be a valid email address."
        )

    return address.lower()


def _build_message(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str,
    settings: EmailSettings,
) -> EmailMessage:
    """
    Build a safe multipart email message.
    """

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = (
        f"{settings.sender_name} <{settings.sender_email}>"
    )
    message["To"] = to_email
    message.set_content(text_body)
    message.add_alternative(
        html_body,
        subtype="html",
    )

    return message


def send_email(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str,
    settings: EmailSettings | None = None,
) -> None:
    """
    Deliver one email through the configured SMTP provider.
    """

    resolved_settings = (
        settings
        if settings is not None
        else load_email_settings()
    )

    validate_email_settings(
        resolved_settings
    )

    try:
        recipient = _validate_email_address(
            to_email,
            "Recipient",
        )
    except EmailConfigurationError as exc:
        raise EmailDeliveryError(
            "Recipient email address is invalid."
        ) from exc

    message = _build_message(
        to_email=recipient,
        subject=str(subject or "").strip(),
        text_body=text_body,
        html_body=html_body,
        settings=resolved_settings,
    )

    context = ssl.create_default_context()

    try:
        if resolved_settings.use_ssl:
            with smtplib.SMTP_SSL(
                resolved_settings.smtp_host,
                resolved_settings.smtp_port,
                timeout=resolved_settings.timeout_seconds,
                context=context,
            ) as server:
                server.login(
                    resolved_settings.smtp_username,
                    resolved_settings.smtp_password,
                )
                server.send_message(message)
        else:
            with smtplib.SMTP(
                resolved_settings.smtp_host,
                resolved_settings.smtp_port,
                timeout=resolved_settings.timeout_seconds,
            ) as server:
                server.ehlo()

                if resolved_settings.use_tls:
                    server.starttls(
                        context=context
                    )
                    server.ehlo()

                server.login(
                    resolved_settings.smtp_username,
                    resolved_settings.smtp_password,
                )
                server.send_message(message)

    except (
        smtplib.SMTPException,
        OSError,
        ssl.SSLError,
    ) as exc:
        LOGGER.exception(
            "Email delivery failed."
        )
        raise EmailDeliveryError(
            "Email delivery failed."
        ) from exc


def build_verification_url(
    *,
    raw_token: str,
    settings: EmailSettings | None = None,
) -> str:
    """
    Build the frontend email-verification link.
    """

    resolved_settings = (
        settings
        if settings is not None
        else load_email_settings()
    )

    token = quote(
        str(raw_token or "").strip(),
        safe="",
    )

    return (
        f"{resolved_settings.frontend_url}"
        f"/verify-email?token={token}"
    )


def build_password_reset_url(
    *,
    raw_token: str,
    settings: EmailSettings | None = None,
) -> str:
    """
    Build the frontend password-reset link.
    """

    resolved_settings = (
        settings
        if settings is not None
        else load_email_settings()
    )

    token = quote(
        str(raw_token or "").strip(),
        safe="",
    )

    return (
        f"{resolved_settings.frontend_url}"
        f"/reset-password?token={token}"
    )


def send_verification_email(
    *,
    to_email: str,
    username: str,
    raw_token: str,
    settings: EmailSettings | None = None,
) -> None:
    """
    Send one email-verification message.
    """

    resolved_settings = (
        settings
        if settings is not None
        else load_email_settings()
    )

    verification_url = build_verification_url(
        raw_token=raw_token,
        settings=resolved_settings,
    )

    safe_username = html.escape(
        str(username or "Trader")
    )
    safe_url = html.escape(
        verification_url,
        quote=True,
    )

    subject = "Verify your Blue Trading AI email"

    text_body = (
        f"Hello {username or 'Trader'},\n\n"
        "Verify your Blue Trading AI email address using this link:\n"
        f"{verification_url}\n\n"
        "This verification link expires in 24 hours. "
        "If you did not create this account, ignore this email.\n"
    )

    html_body = f"""
    <html>
      <body style="font-family:Arial,sans-serif;line-height:1.6;">
        <h2>Verify your email</h2>
        <p>Hello {safe_username},</p>
        <p>
          Confirm your email address to complete your
          Blue Trading AI account setup.
        </p>
        <p>
          <a href="{safe_url}"
             style="display:inline-block;padding:12px 18px;
                    text-decoration:none;border-radius:6px;
                    background:#111827;color:#ffffff;">
            Verify Email
          </a>
        </p>
        <p>This link expires in 24 hours.</p>
        <p>
          If you did not create this account,
          you can safely ignore this email.
        </p>
      </body>
    </html>
    """

    send_email(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        settings=resolved_settings,
    )


def send_password_reset_email(
    *,
    to_email: str,
    username: str,
    raw_token: str,
    settings: EmailSettings | None = None,
) -> None:
    """
    Send one secure password-reset message.
    """

    resolved_settings = (
        settings
        if settings is not None
        else load_email_settings()
    )

    reset_url = build_password_reset_url(
        raw_token=raw_token,
        settings=resolved_settings,
    )

    safe_username = html.escape(
        str(username or "Trader")
    )
    safe_url = html.escape(
        reset_url,
        quote=True,
    )

    subject = "Reset your Blue Trading AI password"

    text_body = (
        f"Hello {username or 'Trader'},\n\n"
        "Reset your Blue Trading AI password using this link:\n"
        f"{reset_url}\n\n"
        "This reset link expires in 30 minutes and can be used once. "
        "If you did not request this reset, ignore this email.\n"
    )

    html_body = f"""
    <html>
      <body style="font-family:Arial,sans-serif;line-height:1.6;">
        <h2>Reset your password</h2>
        <p>Hello {safe_username},</p>
        <p>
          A password reset was requested for your
          Blue Trading AI account.
        </p>
        <p>
          <a href="{safe_url}"
             style="display:inline-block;padding:12px 18px;
                    text-decoration:none;border-radius:6px;
                    background:#111827;color:#ffffff;">
            Reset Password
          </a>
        </p>
        <p>
          This link expires in 30 minutes and can be used once.
        </p>
        <p>
          If you did not request this reset,
          you can safely ignore this email.
        </p>
      </body>
    </html>
    """

    send_email(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        settings=resolved_settings,
    )


def email_delivery_configured() -> bool:
    """
    Return whether the minimum SMTP configuration exists.
    """

    try:
        settings = load_email_settings()
        validate_email_settings(settings)
        return True
    except EmailConfigurationError:
        return False


__all__ = [
    "EmailConfigurationError",
    "EmailDeliveryError",
    "EmailSettings",
    "build_password_reset_url",
    "build_verification_url",
    "email_delivery_configured",
    "load_email_settings",
    "send_email",
    "send_password_reset_email",
    "send_verification_email",
    "validate_email_settings",
]