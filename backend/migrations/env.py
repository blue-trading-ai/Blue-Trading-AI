from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.database.connection import (
    Base,
    DATABASE_URL,
)

# Import every SQLAlchemy model module before reading Base.metadata.
#
# Alembic autogenerate only sees tables that have been registered on
# Base.metadata. Missing imports here can make Alembic incorrectly propose
# destructive remove_table/remove_index operations for valid live tables.
from app.models.account_action_token import AccountActionToken  # noqa: F401
from app.models.application_event_log import ApplicationEventLog  # noqa: F401
from app.models.auth_session import AuthSession  # noqa: F401
from app.models.background_job import BackgroundJob  # noqa: F401
from app.models.refresh_token import RefreshToken  # noqa: F401
from app.models.role_permission import (  # noqa: F401
    Permission,
    Role,
    UserRole,
    role_permissions,
)
from app.models.security_audit_log import SecurityAuditLog  # noqa: F401
from app.models.trade_history import TradeHistory  # noqa: F401
from app.models.trading_signal import TradingSignal  # noqa: F401
from app.models.user import User  # noqa: F401


config = context.config

if config.config_file_name is not None:
    fileConfig(
        config.config_file_name
    )

# Always use the same database URL as the application.
config.set_main_option(
    "sqlalchemy.url",
    DATABASE_URL.replace(
        "%",
        "%%",
    ),
)

target_metadata = Base.metadata


EXPECTED_MODEL_TABLES = {
    "account_action_tokens",
    "application_event_logs",
    "auth_sessions",
    "background_jobs",
    "permissions",
    "refresh_tokens",
    "role_permissions",
    "roles",
    "security_audit_logs",
    "trade_history",
    "trading_signals",
    "user_roles",
    "users",
}


def _validate_model_metadata() -> None:
    """
    Fail fast when a model import is accidentally removed from this file.

    This protects Alembic autogenerate from interpreting a missing model
    registration as a request to drop an existing database table.
    """

    registered_tables = set(
        target_metadata.tables.keys()
    )

    missing_tables = (
        EXPECTED_MODEL_TABLES
        - registered_tables
    )

    if missing_tables:
        missing = ", ".join(
            sorted(
                missing_tables
            )
        )
        raise RuntimeError(
            "Alembic metadata is incomplete. "
            f"Missing model tables: {missing}"
        )


_validate_model_metadata()


def _configure_context(
    *,
    connection=None,
    url: str | None = None,
) -> None:
    """
    Apply one consistent Alembic comparison configuration.
    """

    options = {
        "target_metadata": target_metadata,
        "compare_type": True,
        "compare_server_default": True,
    }

    if connection is not None:
        options["connection"] = connection
        options["render_as_batch"] = (
            connection.dialect.name
            == "sqlite"
        )
    else:
        options["url"] = url
        options["literal_binds"] = True
        options["dialect_opts"] = {
            "paramstyle": "named",
        }
        options["render_as_batch"] = True

    context.configure(
        **options
    )


def run_migrations_offline() -> None:
    """
    Run migrations without creating a live database connection.
    """

    _configure_context(
        url=DATABASE_URL
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations using a live database connection.
    """

    configuration = config.get_section(
        config.config_ini_section,
        {},
    )

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        _configure_context(
            connection=connection
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()