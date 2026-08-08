"""Database engine and SQLAlchemy session configuration for Blue-Trading-AI."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any, Final
from urllib.parse import unquote

from sqlalchemy import (
    create_engine,
    event,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    sessionmaker,
)

from app.core.config import settings


PROJECT_ROOT: Final[Path] = Path(
    __file__
).resolve().parents[2]

DEFAULT_SQLITE_PATH: Final[Path] = (
    PROJECT_ROOT
    / "blue_trading_ai.db"
)

DEFAULT_SQLITE_URL: Final[str] = (
    f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"
)

DATABASE_URL: Final[str] = str(
    settings.DATABASE_URL
    or DEFAULT_SQLITE_URL
).strip()

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL cannot be empty."
    )

IS_SQLITE: Final[bool] = (
    DATABASE_URL.lower().startswith(
        "sqlite"
    )
)


def _sqlite_database_path(
    database_url: str,
) -> Path | None:
    """
    Resolve one local SQLite database path.

    Returns None for in-memory databases or unrecognized SQLite URLs.
    """

    normalized = str(
        database_url or ""
    ).strip()

    if not normalized.lower().startswith(
        "sqlite"
    ):
        return None

    lowered = normalized.lower()

    if (
        ":memory:" in lowered
        or "mode=memory" in lowered
    ):
        return None

    prefixes = (
        "sqlite+pysqlite:///",
        "sqlite:///",
    )

    raw_path: str | None = None

    for prefix in prefixes:
        if lowered.startswith(
            prefix
        ):
            raw_path = normalized[
                len(prefix):
            ]
            break

    if raw_path is None:
        return None

    # Ignore SQLite URL query parameters when resolving a local path.
    raw_path = raw_path.split(
        "?",
        1,
    )[0]

    raw_path = unquote(
        raw_path
    ).strip()

    if not raw_path:
        return None

    path = Path(
        raw_path
    )

    if not path.is_absolute():
        path = (
            PROJECT_ROOT
            / path
        )

    return path.resolve()


DATABASE_PATH: Final[Path | None] = (
    _sqlite_database_path(
        DATABASE_URL
    )
)


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.
    """


engine_options: dict[str, Any] = {
    "pool_pre_ping": True,
}

if IS_SQLITE:
    engine_options[
        "connect_args"
    ] = {
        "check_same_thread": False,
        "timeout": 30,
    }


engine: Engine = create_engine(
    DATABASE_URL,
    **engine_options,
)


if IS_SQLITE:

    @event.listens_for(
        engine,
        "connect",
    )
    def configure_sqlite_connection(
        dbapi_connection: Any,
        connection_record: Any,
    ) -> None:
        """
        Apply safe SQLite settings to each SQLite connection.
        """

        del connection_record

        cursor = dbapi_connection.cursor()

        try:
            cursor.execute(
                "PRAGMA foreign_keys=ON"
            )
            cursor.execute(
                "PRAGMA journal_mode=WAL"
            )
            cursor.fetchone()
            cursor.execute(
                "PRAGMA synchronous=NORMAL"
            )
            cursor.execute(
                "PRAGMA busy_timeout=30000"
            )
        finally:
            cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Generator[
    Session,
    None,
    None,
]:
    """
    Provide one SQLAlchemy session per FastAPI request.
    """

    db = SessionLocal()

    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _sqlite_runtime_settings(
    connection: Any,
) -> dict[str, object]:
    """
    Read actual SQLite runtime PRAGMA values from one live connection.
    """

    foreign_keys_value = connection.execute(
        text(
            "PRAGMA foreign_keys"
        )
    ).scalar()

    journal_mode_value = connection.execute(
        text(
            "PRAGMA journal_mode"
        )
    ).scalar()

    busy_timeout_value = connection.execute(
        text(
            "PRAGMA busy_timeout"
        )
    ).scalar()

    synchronous_value = connection.execute(
        text(
            "PRAGMA synchronous"
        )
    ).scalar()

    journal_mode = str(
        journal_mode_value
        or ""
    ).strip().lower()

    return {
        "foreign_keys_enabled": (
            int(
                foreign_keys_value
                or 0
            )
            == 1
        ),
        "journal_mode": (
            journal_mode
            or None
        ),
        "wal_mode_enabled": (
            journal_mode == "wal"
        ),
        "busy_timeout_milliseconds": int(
            busy_timeout_value
            or 0
        ),
        "synchronous_mode": (
            int(
                synchronous_value
                or 0
            )
        ),
    }


def database_health() -> dict[str, object]:
    """
    Return safe database configuration and connectivity details.

    SQLite PRAGMA values are read from the live connection instead of
    being reported from configuration assumptions.
    """

    database_type = (
        engine.url.get_backend_name()
    )

    connected = False
    connection_error: str | None = None
    sqlite_runtime: dict[
        str,
        object,
    ] = {}

    try:
        with engine.connect() as connection:
            connection.execute(
                text(
                    "SELECT 1"
                )
            )

            if IS_SQLITE:
                sqlite_runtime = (
                    _sqlite_runtime_settings(
                        connection
                    )
                )

        connected = True
    except Exception as exc:
        connection_error = (
            exc.__class__.__name__
        )

    payload: dict[str, object] = {
        "database_type": database_type,
        "database_connected": connected,
        "pool_pre_ping_enabled": True,
    }

    if connection_error is not None:
        payload[
            "connection_error_type"
        ] = connection_error

    if IS_SQLITE:
        payload.update(
            {
                "database_path": (
                    str(
                        DATABASE_PATH
                    )
                    if DATABASE_PATH
                    else None
                ),
                "database_exists": (
                    DATABASE_PATH.exists()
                    if DATABASE_PATH
                    else True
                ),
                "foreign_keys_enabled": (
                    sqlite_runtime.get(
                        "foreign_keys_enabled",
                        False,
                    )
                ),
                "journal_mode": (
                    sqlite_runtime.get(
                        "journal_mode"
                    )
                ),
                "wal_mode_enabled": (
                    sqlite_runtime.get(
                        "wal_mode_enabled",
                        False,
                    )
                ),
                "busy_timeout_milliseconds": (
                    sqlite_runtime.get(
                        "busy_timeout_milliseconds",
                        0,
                    )
                ),
                "synchronous_mode": (
                    sqlite_runtime.get(
                        "synchronous_mode"
                    )
                ),
            }
        )

    return payload


__all__ = [
    "Base",
    "DATABASE_PATH",
    "DATABASE_URL",
    "DEFAULT_SQLITE_PATH",
    "DEFAULT_SQLITE_URL",
    "IS_SQLITE",
    "SessionLocal",
    "database_health",
    "engine",
    "get_db",
]