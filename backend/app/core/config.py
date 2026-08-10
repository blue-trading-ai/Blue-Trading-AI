from __future__ import annotations

from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import (
    EmailStr,
    Field,
    field_validator,
    model_validator,
)
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    """
    Blue-Trading-AI application settings.

    Access model:
    - No plans
    - No subscriptions
    - No payments
    - Owner approval is required for platform access
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        validate_default=True,
    )

    # ==========================
    # APPLICATION
    # ==========================

    APP_NAME: str = "Blue-Trading-AI"

    ENVIRONMENT: Literal[
        "development",
        "testing",
        "production",
    ] = "development"

    DEBUG: bool = False

    EXPOSE_DEVELOPMENT_TOKENS: bool = False

    # ==========================
    # OWNER ACCESS CONTROL
    # ==========================

    OWNER_EMAIL: EmailStr

    OWNER_APPROVAL_REQUIRED: bool = True

    PLANS_ENABLED: bool = False
    SUBSCRIPTIONS_ENABLED: bool = False
    PAYMENTS_ENABLED: bool = False

    # ==========================
    # AUTHENTICATION
    # ==========================

    SECRET_KEY: str = Field(
        ...,
        min_length=32,
        max_length=4096,
    )

    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        ge=1,
        le=1440,
    )

    # ==========================
    # DATABASE
    # ==========================

    DATABASE_URL: str = (
        "sqlite:///./blue_trading_ai.db"
    )

    # ==========================
    # MARKET DATA
    # ==========================

    TWELVE_DATA_API_KEY: str = ""

    # ==========================
    # ECONOMIC NEWS
    # ==========================

    ECONOMIC_NEWS_PROVIDER: Literal[
        "forex_factory",
    ] = "forex_factory"

    ECONOMIC_NEWS_WEEKLY_URL: str = (
        "https://nfs.faireconomy.media/"
        "ff_calendar_thisweek.json"
    )

    ECONOMIC_NEWS_REQUEST_TIMEOUT_SECONDS: int = Field(
        default=10,
        ge=3,
        le=30,
    )

    ECONOMIC_NEWS_USER_AGENT: str = (
        "Blue-Trading-AI/49 EconomicNews"
    )

    ECONOMIC_NEWS_CACHE_MINUTES: int = Field(
        default=15,
        ge=1,
        le=120,
    )

    # ==========================
    # CORS
    # ==========================

    CORS_ORIGINS: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000"
    )

    @field_validator("APP_NAME")
    @classmethod
    def validate_app_name(
        cls,
        value: str,
    ) -> str:
        cleaned = str(value or "").strip()

        if not cleaned:
            raise ValueError(
                "APP_NAME must not be empty."
            )

        return cleaned

    @field_validator("OWNER_EMAIL")
    @classmethod
    def normalise_owner_email(
        cls,
        value: EmailStr,
    ) -> str:
        return str(value).strip().lower()

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(
        cls,
        value: str,
    ) -> str:
        cleaned = str(value or "").strip()

        weak_values = {
            "secret",
            "secret_key",
            "changeme",
            "change_me",
            "your_secret_key",
            "replace_me",
            "development",
            "password",
            "default",
        }

        if cleaned.lower() in weak_values:
            raise ValueError(
                "SECRET_KEY must not use a placeholder value."
            )

        if len(cleaned) < 32:
            raise ValueError(
                "SECRET_KEY must contain at least 32 characters."
            )

        if len(set(cleaned)) < 12:
            raise ValueError(
                "SECRET_KEY must contain sufficient character diversity."
            )

        return cleaned

    @field_validator("ALGORITHM")
    @classmethod
    def validate_algorithm(
        cls,
        value: str,
    ) -> str:
        cleaned = str(value or "").strip().upper()

        allowed_algorithms = {
            "HS256",
            "HS384",
            "HS512",
        }

        if cleaned not in allowed_algorithms:
            raise ValueError(
                "ALGORITHM must be HS256, HS384, or HS512."
            )

        return cleaned

    @field_validator("DATABASE_URL")
    @classmethod
    def clean_database_url(
        cls,
        value: str,
    ) -> str:
        cleaned = str(value or "").strip()

        if not cleaned:
            raise ValueError(
                "DATABASE_URL must not be empty."
            )

        return cleaned

    @field_validator("TWELVE_DATA_API_KEY")
    @classmethod
    def clean_market_api_key(
        cls,
        value: str,
    ) -> str:
        return str(value or "").strip()

    @field_validator("ECONOMIC_NEWS_WEEKLY_URL")
    @classmethod
    def validate_economic_news_url(
        cls,
        value: str,
    ) -> str:
        cleaned = str(value or "").strip()
        parsed = urlparse(cleaned)

        if (
            parsed.scheme != "https"
            or not parsed.netloc
        ):
            raise ValueError(
                "ECONOMIC_NEWS_WEEKLY_URL must be a valid HTTPS URL."
            )

        return cleaned

    @field_validator("ECONOMIC_NEWS_USER_AGENT")
    @classmethod
    def validate_economic_news_user_agent(
        cls,
        value: str,
    ) -> str:
        cleaned = str(value or "").strip()

        if not cleaned:
            raise ValueError(
                "ECONOMIC_NEWS_USER_AGENT must not be empty."
            )

        if len(cleaned) > 200:
            raise ValueError(
                "ECONOMIC_NEWS_USER_AGENT is too long."
            )

        return cleaned

    @field_validator("CORS_ORIGINS")
    @classmethod
    def validate_cors_origins(
        cls,
        value: str,
    ) -> str:
        origins = [
            origin.strip().rstrip("/")
            for origin in str(value or "").split(",")
            if origin.strip()
        ]

        if not origins:
            raise ValueError(
                "CORS_ORIGINS must contain at least one origin."
            )

        unique_origins: list[str] = []

        for origin in origins:
            if origin == "*":
                if origin not in unique_origins:
                    unique_origins.append(origin)

                continue

            parsed = urlparse(origin)

            if (
                parsed.scheme not in {
                    "http",
                    "https",
                }
                or not parsed.netloc
                or parsed.path not in {
                    "",
                    "/",
                }
                or parsed.params
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    "Each CORS origin must be a valid HTTP or HTTPS "
                    f"origin without a path: {origin!r}."
                )

            normalized_origin = (
                f"{parsed.scheme}://{parsed.netloc}"
            )

            if normalized_origin not in unique_origins:
                unique_origins.append(
                    normalized_origin
                )

        return ",".join(unique_origins)

    @model_validator(mode="after")
    def validate_access_model(
        self,
    ) -> "Settings":
        if (
            self.PLANS_ENABLED
            or self.SUBSCRIPTIONS_ENABLED
            or self.PAYMENTS_ENABLED
        ):
            raise ValueError(
                "Blue-Trading-AI does not support plans, "
                "subscriptions, or payments."
            )

        if not self.OWNER_APPROVAL_REQUIRED:
            raise ValueError(
                "OWNER_APPROVAL_REQUIRED must remain enabled."
            )

        if self.ENVIRONMENT == "production":
            self._validate_production_settings()

        return self

    def _validate_production_settings(
        self,
    ) -> None:
        if self.DEBUG:
            raise ValueError(
                "DEBUG must be disabled in production."
            )

        if self.EXPOSE_DEVELOPMENT_TOKENS:
            raise ValueError(
                "EXPOSE_DEVELOPMENT_TOKENS must be disabled "
                "in production."
            )

        if not self.TWELVE_DATA_API_KEY:
            raise ValueError(
                "TWELVE_DATA_API_KEY is required in production."
            )

        if len(self.SECRET_KEY) < 48:
            raise ValueError(
                "Production SECRET_KEY must contain at least "
                "48 characters."
            )

        database_url = self.DATABASE_URL.lower()

        if database_url.startswith("sqlite"):
            raise ValueError(
                "SQLite must not be used as the production database."
            )

        production_origins = self.cors_origin_list

        for origin in production_origins:
            lowered = origin.lower()

            if origin == "*":
                raise ValueError(
                    "Wildcard CORS origins are not allowed "
                    "in production."
                )

            parsed = urlparse(origin)

            if parsed.scheme != "https":
                raise ValueError(
                    "Production CORS origins must use HTTPS."
                )

            hostname = (
                parsed.hostname or ""
            ).lower()

            if hostname in {
                "localhost",
                "127.0.0.1",
                "::1",
            }:
                raise ValueError(
                    "Localhost CORS origins are not allowed "
                    "in production."
                )

            if "localhost" in lowered:
                raise ValueError(
                    "Localhost CORS origins are not allowed "
                    "in production."
                )

    @property
    def owner_email_normalised(self) -> str:
        return str(
            self.OWNER_EMAIL
        ).strip().lower()

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def is_development(self) -> bool:
        return (
            self.ENVIRONMENT == "development"
        )

    @property
    def is_testing(self) -> bool:
        return (
            self.ENVIRONMENT == "testing"
        )

    @property
    def is_production(self) -> bool:
        return (
            self.ENVIRONMENT == "production"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


__all__ = [
    "Settings",
    "get_settings",
    "settings",
]