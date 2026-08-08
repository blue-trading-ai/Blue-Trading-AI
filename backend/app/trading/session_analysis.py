"""Trading session and ICT kill-zone analysis for Blue-Trading-AI."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Final, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


MAXIMUM_CANDLES: Final[int] = 100_000
MAXIMUM_TIMESTAMP_TEXT_LENGTH: Final[int] = 128

NEW_YORK_TIMEZONE: Final[str] = "America/New_York"

_TIMESTAMP_FIELDS: Final[tuple[str, ...]] = (
    "timestamp",
    "time",
    "datetime",
    "date",
    "open_time",
)


def _parse_timestamp(
    value: Any,
) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, datetime):
        parsed = value

    elif isinstance(value, (int, float)):
        try:
            seconds = float(value)
        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            return None

        if not math.isfinite(seconds):
            return None

        # Support Unix timestamps in seconds or milliseconds.
        if abs(seconds) > 10_000_000_000:
            seconds /= 1000.0

        if not math.isfinite(seconds):
            return None

        try:
            parsed = datetime.fromtimestamp(
                seconds,
                tz=timezone.utc,
            )
        except (
            OverflowError,
            OSError,
            ValueError,
        ):
            return None

    elif isinstance(value, str):
        text = value.strip()

        if (
            not text
            or len(text)
            > MAXIMUM_TIMESTAMP_TEXT_LENGTH
        ):
            return None

        if text.endswith(("Z", "z")):
            text = (
                text[:-1]
                + "+00:00"
            )

        try:
            parsed = datetime.fromisoformat(
                text
            )
        except (
            TypeError,
            ValueError,
        ):
            return None

    else:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    try:
        return parsed.astimezone(
            timezone.utc
        )
    except (
        OverflowError,
        ValueError,
    ):
        return None


def _latest_market_time(
    candles: list[dict] | None,
) -> tuple[datetime, str]:
    if isinstance(
        candles,
        (list, tuple),
    ) and candles:
        if len(candles) <= MAXIMUM_CANDLES:
            latest = candles[-1]

            if isinstance(
                latest,
                Mapping,
            ):
                for key in _TIMESTAMP_FIELDS:
                    parsed = _parse_timestamp(
                        latest.get(key)
                    )

                    if parsed is not None:
                        return (
                            parsed,
                            "CANDLE_TIMESTAMP",
                        )

    return (
        datetime.now(
            timezone.utc
        ),
        "SERVER_TIME",
    )


def _between_minutes(
    current: int,
    start: int,
    end: int,
) -> bool:
    if not all(
        isinstance(value, int)
        and not isinstance(value, bool)
        for value in (
            current,
            start,
            end,
        )
    ):
        return False

    if not (
        0 <= current < 24 * 60
        and 0 <= start <= 24 * 60
        and 0 <= end <= 24 * 60
    ):
        return False

    if start == end:
        return False

    if start <= end:
        return (
            start
            <= current
            < end
        )

    return (
        current >= start
        or current < end
    )


def _new_york_time(
    utc_time: datetime,
) -> datetime:
    try:
        new_york_zone = ZoneInfo(
            NEW_YORK_TIMEZONE
        )
    except ZoneInfoNotFoundError:
        # Fail safely without crashing the full signal pipeline.
        return utc_time

    try:
        return utc_time.astimezone(
            new_york_zone
        )
    except (
        OverflowError,
        ValueError,
    ):
        return utc_time


def analyze_trading_session(
    candles: list[dict] | None = None,
) -> dict:
    """Identify active forex sessions, overlaps, and common ICT kill zones."""

    utc_time, time_source = (
        _latest_market_time(
            candles
        )
    )

    utc_minutes = (
        utc_time.hour * 60
        + utc_time.minute
    )

    sessions: list[str] = []

    if _between_minutes(
        utc_minutes,
        0,
        9 * 60,
    ):
        sessions.append(
            "ASIAN"
        )

    if _between_minutes(
        utc_minutes,
        7 * 60,
        16 * 60,
    ):
        sessions.append(
            "LONDON"
        )

    if _between_minutes(
        utc_minutes,
        12 * 60,
        21 * 60,
    ):
        sessions.append(
            "NEW_YORK"
        )

    overlaps: list[str] = []

    if (
        "ASIAN" in sessions
        and "LONDON" in sessions
    ):
        overlaps.append(
            "ASIAN_LONDON"
        )

    if (
        "LONDON" in sessions
        and "NEW_YORK" in sessions
    ):
        overlaps.append(
            "LONDON_NEW_YORK"
        )

    ny_time = _new_york_time(
        utc_time
    )

    ny_minutes = (
        ny_time.hour * 60
        + ny_time.minute
    )

    kill_zones: list[str] = []

    if _between_minutes(
        ny_minutes,
        20 * 60,
        24 * 60,
    ):
        kill_zones.append(
            "ASIAN_KILL_ZONE"
        )

    if _between_minutes(
        ny_minutes,
        2 * 60,
        5 * 60,
    ):
        kill_zones.append(
            "LONDON_KILL_ZONE"
        )

    if _between_minutes(
        ny_minutes,
        7 * 60,
        10 * 60,
    ):
        kill_zones.append(
            "NEW_YORK_AM_KILL_ZONE"
        )

    if _between_minutes(
        ny_minutes,
        13 * 60 + 30,
        16 * 60,
    ):
        kill_zones.append(
            "NEW_YORK_PM_KILL_ZONE"
        )

    if kill_zones:
        liquidity = "HIGH"
        trade_environment = (
            "FAVORABLE"
        )
        strength = 90
        actionable = True

    elif overlaps:
        liquidity = "HIGH"
        trade_environment = (
            "FAVORABLE"
        )
        strength = 80
        actionable = True

    elif sessions:
        liquidity = "NORMAL"
        trade_environment = (
            "ACTIVE"
        )
        strength = 65
        actionable = True

    else:
        liquidity = "LOW"
        trade_environment = (
            "QUIET"
        )
        strength = 30
        actionable = False

    primary_session = (
        sessions[-1]
        if sessions
        else "OFF_SESSION"
    )

    return {
        "detected": True,
        "status": (
            "ACTIVE"
            if sessions
            else "OFF_SESSION"
        ),
        "time_source": time_source,
        "market_time_utc": (
            utc_time.isoformat()
        ),
        "market_time_new_york": (
            ny_time.isoformat()
        ),
        "primary_session": (
            primary_session
        ),
        "active_sessions": list(
            sessions
        ),
        "session_overlaps": list(
            overlaps
        ),
        "kill_zones": list(
            kill_zones
        ),
        "in_kill_zone": bool(
            kill_zones
        ),
        "in_session_overlap": bool(
            overlaps
        ),
        "liquidity": liquidity,
        "trade_environment": (
            trade_environment
        ),
        "strength": strength,
        "actionable": actionable,
    }


__all__ = [
    "MAXIMUM_CANDLES",
    "NEW_YORK_TIMEZONE",
    "analyze_trading_session",
]