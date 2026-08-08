from __future__ import annotations

import math
from typing import Any, Final, Iterable


MAXIMUM_PRICE_POINTS: Final[int] = 100_000
MAXIMUM_PERIOD: Final[int] = 10_000


def _normalise_period(
    period: Any,
    *,
    minimum: int = 1,
) -> int:
    if isinstance(
        period,
        bool,
    ):
        raise ValueError(
            "period must be an integer."
        )

    try:
        resolved = int(
            period
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ) as exc:
        raise ValueError(
            "period must be an integer."
        ) from exc

    if resolved < minimum:
        raise ValueError(
            f"period must be at least {minimum}."
        )

    if resolved > MAXIMUM_PERIOD:
        raise ValueError(
            "period exceeds the supported safety limit."
        )

    return resolved


def _normalise_prices(
    prices: Any,
) -> list[float]:
    if not isinstance(
        prices,
        (list, tuple),
    ):
        raise ValueError(
            "prices must be a list or tuple."
        )

    if len(
        prices
    ) > MAXIMUM_PRICE_POINTS:
        raise ValueError(
            "Price history exceeds the supported safety limit."
        )

    output: list[
        float
    ] = []

    for value in prices:
        try:
            resolved = float(
                value
            )
        except (
            TypeError,
            ValueError,
            OverflowError,
        ) as exc:
            raise ValueError(
                "Price data contains an invalid value."
            ) from exc

        if (
            not math.isfinite(
                resolved
            )
            or resolved <= 0.0
        ):
            raise ValueError(
                "Price data contains an invalid value."
            )

        output.append(
            resolved
        )

    return output


def calculate_moving_average(
    prices,
    period=20,
):
    resolved_period = _normalise_period(
        period
    )
    resolved_prices = _normalise_prices(
        prices
    )

    if len(
        resolved_prices
    ) < resolved_period:
        return None

    average = sum(
        resolved_prices[
            -resolved_period:
        ]
    ) / resolved_period

    return round(
        average,
        5,
    )


def calculate_ema(
    prices,
    period=20,
):
    resolved_period = _normalise_period(
        period
    )
    resolved_prices = _normalise_prices(
        prices
    )

    if len(
        resolved_prices
    ) < resolved_period:
        return None

    multiplier = (
        2.0
        / (
            resolved_period
            + 1
        )
    )

    ema = sum(
        resolved_prices[
            :resolved_period
        ]
    ) / resolved_period

    for price in resolved_prices[
        resolved_period:
    ]:
        ema = (
            (
                price
                - ema
            )
            * multiplier
        ) + ema

    if not math.isfinite(
        ema
    ):
        return None

    return round(
        ema,
        5,
    )


def calculate_rsi(
    prices,
    period=14,
):
    resolved_period = _normalise_period(
        period
    )
    resolved_prices = _normalise_prices(
        prices
    )

    if len(
        resolved_prices
    ) < (
        resolved_period
        + 1
    ):
        return None

    gains: list[
        float
    ] = []
    losses: list[
        float
    ] = []

    for index in range(
        1,
        len(
            resolved_prices
        ),
    ):
        change = (
            resolved_prices[
                index
            ]
            - resolved_prices[
                index - 1
            ]
        )

        if change > 0.0:
            gains.append(
                change
            )
            losses.append(
                0.0
            )
        elif change < 0.0:
            gains.append(
                0.0
            )
            losses.append(
                abs(
                    change
                )
            )
        else:
            gains.append(
                0.0
            )
            losses.append(
                0.0
            )

    average_gain = sum(
        gains[
            -resolved_period:
        ]
    ) / resolved_period

    average_loss = sum(
        losses[
            -resolved_period:
        ]
    ) / resolved_period

    if (
        average_gain == 0.0
        and average_loss == 0.0
    ):
        return 50.0

    if average_loss == 0.0:
        return 100.0

    if average_gain == 0.0:
        return 0.0

    rs = (
        average_gain
        / average_loss
    )

    rsi = (
        100.0
        - (
            100.0
            / (
                1.0
                + rs
            )
        )
    )

    if not math.isfinite(
        rsi
    ):
        return None

    return round(
        max(
            0.0,
            min(
                100.0,
                rsi,
            ),
        ),
        2,
    )


def detect_trend(
    prices,
):
    resolved_prices = _normalise_prices(
        prices
    )

    if len(
        resolved_prices
    ) < 2:
        return "Not enough data"

    if (
        resolved_prices[
            -1
        ]
        > resolved_prices[
            0
        ]
    ):
        return "UPTREND"

    if (
        resolved_prices[
            -1
        ]
        < resolved_prices[
            0
        ]
    ):
        return "DOWNTREND"

    return "SIDEWAYS"


def find_support(
    prices,
):
    resolved_prices = _normalise_prices(
        prices
    )

    if not resolved_prices:
        return None

    return min(
        resolved_prices
    )


def find_resistance(
    prices,
):
    resolved_prices = _normalise_prices(
        prices
    )

    if not resolved_prices:
        return None

    return max(
        resolved_prices
    )


def find_support_resistance(
    prices,
):
    resolved_prices = _normalise_prices(
        prices
    )

    if not resolved_prices:
        return (
            None,
            None,
        )

    support = min(
        resolved_prices
    )
    resistance = max(
        resolved_prices
    )

    return (
        support,
        resistance,
    )


__all__ = [
    "MAXIMUM_PERIOD",
    "MAXIMUM_PRICE_POINTS",
    "calculate_ema",
    "calculate_moving_average",
    "calculate_rsi",
    "detect_trend",
    "find_resistance",
    "find_support",
    "find_support_resistance",
]