"""
Smart Money Concept Order Block Detection.

Bullish Order Block:
The last bearish candle before a strong bullish impulse.

Bearish Order Block:
The last bullish candle before a strong bearish impulse.

The detector requires OHLC candles:
{
    "open": float,
    "high": float,
    "low": float,
    "close": float
}
"""

from __future__ import annotations

import math
from typing import Any, Final, Mapping


MINIMUM_CANDLES: Final[int] = 5
MAXIMUM_CANDLES: Final[int] = 100_000
MAXIMUM_SEARCH_LOOKBACK: Final[int] = 5_000
MAXIMUM_AVERAGE_BODY_PERIOD: Final[int] = 1_000
MINIMUM_IMPULSE_MULTIPLIER: Final[float] = 0.1
MAXIMUM_IMPULSE_MULTIPLIER: Final[float] = 100.0


def _default_result(
    status: str = "NO_ORDER_BLOCK",
) -> dict:
    return {
        "detected": False,
        "direction": "NONE",
        "status": status,
        "zone_high": None,
        "zone_low": None,
        "candle_index": None,
        "impulse_strength": None,
        "mitigated": False,
        "current_price": None,
    }


def _finite_positive_float(
    value: Any,
) -> float | None:
    try:
        resolved = float(
            value
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None

    if (
        not math.isfinite(
            resolved
        )
        or resolved <= 0.0
    ):
        return None

    return resolved


def _normalise_positive_int(
    value: Any,
    *,
    minimum: int,
    maximum: int,
) -> int | None:
    if isinstance(
        value,
        bool,
    ):
        return None

    try:
        resolved = int(
            value
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None

    if not (
        minimum
        <= resolved
        <= maximum
    ):
        return None

    return resolved


def _normalise_impulse_multiplier(
    value: Any,
) -> float | None:
    try:
        resolved = float(
            value
        )
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

    if not (
        MINIMUM_IMPULSE_MULTIPLIER
        <= resolved
        <= MAXIMUM_IMPULSE_MULTIPLIER
    ):
        return None

    return resolved


def _normalise_candle(
    candle: Any,
) -> dict[str, float] | None:
    if not isinstance(
        candle,
        Mapping,
    ):
        return None

    required_fields = (
        "open",
        "high",
        "low",
        "close",
    )

    resolved: dict[
        str,
        float,
    ] = {}

    for field in required_fields:
        value = _finite_positive_float(
            candle.get(
                field
            )
        )

        if value is None:
            return None

        resolved[
            field
        ] = value

    candle_high = resolved[
        "high"
    ]
    candle_low = resolved[
        "low"
    ]
    candle_open = resolved[
        "open"
    ]
    candle_close = resolved[
        "close"
    ]

    if candle_high < candle_low:
        return None

    if not (
        candle_low
        <= candle_open
        <= candle_high
    ):
        return None

    if not (
        candle_low
        <= candle_close
        <= candle_high
    ):
        return None

    return resolved


def _normalise_candles(
    candles: Any,
) -> list[dict[str, float]]:
    if not isinstance(
        candles,
        (list, tuple),
    ):
        return []

    if len(
        candles
    ) > MAXIMUM_CANDLES:
        return []

    output: list[
        dict[str, float]
    ] = []

    for candle in candles:
        resolved = _normalise_candle(
            candle
        )

        if resolved is None:
            return []

        output.append(
            resolved
        )

    return output


def _is_valid_candle(
    candle: Any,
) -> bool:
    return (
        _normalise_candle(
            candle
        )
        is not None
    )


def _is_bullish(
    candle: Mapping[str, float],
) -> bool:
    return (
        candle["close"]
        > candle["open"]
    )


def _is_bearish(
    candle: Mapping[str, float],
) -> bool:
    return (
        candle["close"]
        < candle["open"]
    )


def _body_size(
    candle: Mapping[str, float],
) -> float:
    body = abs(
        candle["close"]
        - candle["open"]
    )

    if not math.isfinite(
        body
    ):
        return 0.0

    return body


def _average_body_size(
    candles: list,
    end_index: int,
    period: int = 10,
) -> float:
    resolved_period = (
        _normalise_positive_int(
            period,
            minimum=1,
            maximum=MAXIMUM_AVERAGE_BODY_PERIOD,
        )
    )

    if resolved_period is None:
        return 0.0

    if isinstance(
        end_index,
        bool,
    ):
        return 0.0

    try:
        resolved_end_index = int(
            end_index
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return 0.0

    if (
        resolved_end_index <= 0
        or resolved_end_index
        > len(
            candles
        )
    ):
        return 0.0

    start_index = max(
        0,
        resolved_end_index
        - resolved_period,
    )

    selected_candles = candles[
        start_index:
        resolved_end_index
    ]

    if not selected_candles:
        return 0.0

    body_sizes = [
        _body_size(
            candle
        )
        for candle in selected_candles
    ]

    average = (
        sum(
            body_sizes
        )
        / len(
            body_sizes
        )
    )

    return (
        average
        if math.isfinite(
            average
        )
        and average >= 0.0
        else 0.0
    )


def _zone_is_mitigated(
    candles: list,
    start_index: int,
    zone_low: float,
    zone_high: float,
) -> bool:
    """
    A zone is considered mitigated when a later candle returns
    inside the order-block price range.
    """

    resolved_low = _finite_positive_float(
        zone_low
    )
    resolved_high = _finite_positive_float(
        zone_high
    )

    if (
        resolved_low is None
        or resolved_high is None
    ):
        return False

    if resolved_low > resolved_high:
        resolved_low, resolved_high = (
            resolved_high,
            resolved_low,
        )

    if isinstance(
        start_index,
        bool,
    ):
        return False

    try:
        resolved_start = max(
            0,
            int(
                start_index
            ),
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return False

    for candle in candles[
        resolved_start:
    ]:
        if not isinstance(
            candle,
            Mapping,
        ):
            continue

        candle_low = _finite_positive_float(
            candle.get(
                "low"
            )
        )
        candle_high = _finite_positive_float(
            candle.get(
                "high"
            )
        )

        if (
            candle_low is None
            or candle_high is None
        ):
            continue

        touched_zone = (
            candle_low
            <= resolved_high
            and candle_high
            >= resolved_low
        )

        if touched_zone:
            return True

    return False


def detect_order_block(
    candles: list,
    impulse_multiplier: float = 1.5,
    search_lookback: int = 30,
) -> dict:
    """
    Detect the most recent bullish or bearish order block.

    Args:
        candles:
            OHLC candles ordered from oldest to newest.

        impulse_multiplier:
            Required impulse body size compared with the average
            candle body size.

        search_lookback:
            Maximum number of recent candles to search.

    Returns:
        Order-block detection information.
    """

    if not isinstance(
        candles,
        (list, tuple),
    ):
        return _default_result(
            "INSUFFICIENT_OHLC_DATA"
        )

    if len(
        candles
    ) < MINIMUM_CANDLES:
        return _default_result(
            "INSUFFICIENT_DATA"
        )

    resolved_candles = (
        _normalise_candles(
            candles
        )
    )

    if not resolved_candles:
        return _default_result(
            "INSUFFICIENT_OHLC_DATA"
        )

    resolved_multiplier = (
        _normalise_impulse_multiplier(
            impulse_multiplier
        )
    )
    resolved_lookback = (
        _normalise_positive_int(
            search_lookback,
            minimum=1,
            maximum=MAXIMUM_SEARCH_LOOKBACK,
        )
    )

    if (
        resolved_multiplier is None
        or resolved_lookback is None
    ):
        return _default_result(
            "INVALID_CONFIGURATION"
        )

    current_price = float(
        resolved_candles[
            -1
        ][
            "close"
        ]
    )

    start_index = max(
        1,
        len(
            resolved_candles
        )
        - resolved_lookback,
    )

    detected_blocks: list[
        dict[str, Any]
    ] = []

    for index in range(
        start_index,
        len(
            resolved_candles
        )
        - 1,
    ):
        order_candle = (
            resolved_candles[
                index
            ]
        )
        impulse_candle = (
            resolved_candles[
                index + 1
            ]
        )

        average_body = (
            _average_body_size(
                resolved_candles,
                index,
                period=10,
            )
        )

        impulse_body = _body_size(
            impulse_candle
        )

        if (
            average_body <= 0.0
            or impulse_body <= 0.0
        ):
            continue

        impulse_strength = (
            impulse_body
            / average_body
        )

        if not math.isfinite(
            impulse_strength
        ):
            continue

        strong_impulse = (
            impulse_strength
            >= resolved_multiplier
        )

        if not strong_impulse:
            continue

        bullish_order_block = (
            _is_bearish(
                order_candle
            )
            and _is_bullish(
                impulse_candle
            )
            and impulse_candle[
                "close"
            ]
            > order_candle[
                "high"
            ]
        )

        if bullish_order_block:
            zone_high = float(
                order_candle[
                    "high"
                ]
            )
            zone_low = float(
                order_candle[
                    "low"
                ]
            )

            mitigated = (
                _zone_is_mitigated(
                    resolved_candles,
                    index + 2,
                    zone_low,
                    zone_high,
                )
            )

            detected_blocks.append(
                {
                    "detected": True,
                    "direction": (
                        "BULLISH_ORDER_BLOCK"
                    ),
                    "status": (
                        "MITIGATED"
                        if mitigated
                        else "ACTIVE"
                    ),
                    "zone_high": (
                        zone_high
                    ),
                    "zone_low": (
                        zone_low
                    ),
                    "candle_index": (
                        index
                    ),
                    "impulse_strength": round(
                        impulse_strength,
                        2,
                    ),
                    "mitigated": (
                        mitigated
                    ),
                    "current_price": (
                        current_price
                    ),
                }
            )

        bearish_order_block = (
            _is_bullish(
                order_candle
            )
            and _is_bearish(
                impulse_candle
            )
            and impulse_candle[
                "close"
            ]
            < order_candle[
                "low"
            ]
        )

        if bearish_order_block:
            zone_high = float(
                order_candle[
                    "high"
                ]
            )
            zone_low = float(
                order_candle[
                    "low"
                ]
            )

            mitigated = (
                _zone_is_mitigated(
                    resolved_candles,
                    index + 2,
                    zone_low,
                    zone_high,
                )
            )

            detected_blocks.append(
                {
                    "detected": True,
                    "direction": (
                        "BEARISH_ORDER_BLOCK"
                    ),
                    "status": (
                        "MITIGATED"
                        if mitigated
                        else "ACTIVE"
                    ),
                    "zone_high": (
                        zone_high
                    ),
                    "zone_low": (
                        zone_low
                    ),
                    "candle_index": (
                        index
                    ),
                    "impulse_strength": round(
                        impulse_strength,
                        2,
                    ),
                    "mitigated": (
                        mitigated
                    ),
                    "current_price": (
                        current_price
                    ),
                }
            )

    if not detected_blocks:
        result = _default_result()
        result[
            "current_price"
        ] = current_price

        return result

    return detected_blocks[
        -1
    ]


__all__ = [
    "MAXIMUM_CANDLES",
    "MAXIMUM_SEARCH_LOOKBACK",
    "MINIMUM_CANDLES",
    "detect_order_block",
]