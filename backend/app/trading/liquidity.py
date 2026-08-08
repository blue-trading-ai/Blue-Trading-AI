"""
Smart Money Concept Liquidity Sweep Detection.

Bullish Liquidity Sweep:
Price trades below a previous swing low but closes back above it.

Bearish Liquidity Sweep:
Price trades above a previous swing high but closes back below it.
"""

from __future__ import annotations

import math
from typing import Any, Final, Mapping


MINIMUM_CANDLES: Final[int] = 5
MAXIMUM_CANDLES: Final[int] = 100_000
MAXIMUM_LOOKBACK: Final[int] = 5_000
MAXIMUM_CONFIRMATION_BUFFER: Final[float] = 1_000_000.0


def _default_result(
    status: str = "NO_LIQUIDITY_SWEEP",
) -> dict:
    return {
        "detected": False,
        "direction": "NONE",
        "status": status,
        "level": None,
        "sweep_price": None,
        "close_price": None,
        "distance": None,
        "candle_index": None,
        "liquidity_candle_index": None,
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


def _normalise_lookback(
    value: Any,
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
        1
        <= resolved
        <= MAXIMUM_LOOKBACK
    ):
        return None

    return resolved


def _normalise_confirmation_buffer(
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

    if (
        resolved < 0.0
        or resolved
        > MAXIMUM_CONFIRMATION_BUFFER
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

    required = (
        "open",
        "high",
        "low",
        "close",
    )

    resolved: dict[
        str,
        float,
    ] = {}

    for field in required:
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


def _valid_candle(
    candle: object,
) -> bool:
    return (
        _normalise_candle(
            candle
        )
        is not None
    )


def _find_swing_high(
    candles: list,
    end_index: int,
    lookback: int,
) -> tuple[int, float] | None:
    resolved_lookback = _normalise_lookback(
        lookback
    )

    if resolved_lookback is None:
        return None

    if isinstance(
        end_index,
        bool,
    ):
        return None

    try:
        resolved_end = int(
            end_index
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None

    if not (
        1
        <= resolved_end
        <= len(
            candles
        )
    ):
        return None

    start_index = max(
        0,
        resolved_end
        - resolved_lookback,
    )

    selected = candles[
        start_index:
        resolved_end
    ]

    if not selected:
        return None

    try:
        relative_index = max(
            range(
                len(
                    selected
                )
            ),
            key=lambda index: float(
                selected[
                    index
                ][
                    "high"
                ]
            ),
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None

    candle_index = (
        start_index
        + relative_index
    )

    level = _finite_positive_float(
        candles[
            candle_index
        ].get(
            "high"
        )
        if isinstance(
            candles[
                candle_index
            ],
            Mapping,
        )
        else None
    )

    if level is None:
        return None

    return (
        candle_index,
        level,
    )


def _find_swing_low(
    candles: list,
    end_index: int,
    lookback: int,
) -> tuple[int, float] | None:
    resolved_lookback = _normalise_lookback(
        lookback
    )

    if resolved_lookback is None:
        return None

    if isinstance(
        end_index,
        bool,
    ):
        return None

    try:
        resolved_end = int(
            end_index
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None

    if not (
        1
        <= resolved_end
        <= len(
            candles
        )
    ):
        return None

    start_index = max(
        0,
        resolved_end
        - resolved_lookback,
    )

    selected = candles[
        start_index:
        resolved_end
    ]

    if not selected:
        return None

    try:
        relative_index = min(
            range(
                len(
                    selected
                )
            ),
            key=lambda index: float(
                selected[
                    index
                ][
                    "low"
                ]
            ),
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None

    candle_index = (
        start_index
        + relative_index
    )

    level = _finite_positive_float(
        candles[
            candle_index
        ].get(
            "low"
        )
        if isinstance(
            candles[
                candle_index
            ],
            Mapping,
        )
        else None
    )

    if level is None:
        return None

    return (
        candle_index,
        level,
    )


def detect_liquidity_sweep(
    candles: list,
    lookback: int = 20,
    confirmation_buffer: float = 0.0,
) -> dict:
    """
    Detect a liquidity sweep using the latest completed candle.

    Args:
        candles:
            OHLC candles ordered from oldest to newest.

        lookback:
            Number of previous candles used to find liquidity levels.

        confirmation_buffer:
            Minimum distance price must move beyond the liquidity level.

    Returns:
        Liquidity sweep details.
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

    resolved_lookback = (
        _normalise_lookback(
            lookback
        )
    )
    resolved_buffer = (
        _normalise_confirmation_buffer(
            confirmation_buffer
        )
    )

    if (
        resolved_lookback is None
        or resolved_buffer is None
    ):
        return _default_result(
            "INVALID_CONFIGURATION"
        )

    current_index = (
        len(
            resolved_candles
        )
        - 1
    )

    current_candle = (
        resolved_candles[
            current_index
        ]
    )

    swing_high = _find_swing_high(
        resolved_candles,
        current_index,
        resolved_lookback,
    )

    swing_low = _find_swing_low(
        resolved_candles,
        current_index,
        resolved_lookback,
    )

    current_close = float(
        current_candle[
            "close"
        ]
    )

    if (
        swing_high is None
        or swing_low is None
    ):
        result = _default_result(
            "NO_SWING_LEVEL"
        )
        result[
            "close_price"
        ] = current_close

        return result

    high_index, high_level = (
        swing_high
    )
    low_index, low_level = (
        swing_low
    )

    current_high = float(
        current_candle[
            "high"
        ]
    )
    current_low = float(
        current_candle[
            "low"
        ]
    )

    bearish_sweep_level = (
        high_level
        + resolved_buffer
    )
    bullish_sweep_level = (
        low_level
        - resolved_buffer
    )

    if (
        not math.isfinite(
            bearish_sweep_level
        )
        or not math.isfinite(
            bullish_sweep_level
        )
        or bullish_sweep_level <= 0.0
    ):
        result = _default_result(
            "INVALID_SWING_LEVEL"
        )
        result[
            "close_price"
        ] = current_close

        return result

    bearish_sweep = (
        current_high
        > bearish_sweep_level
        and current_close
        < high_level
    )

    bullish_sweep = (
        current_low
        < bullish_sweep_level
        and current_close
        > low_level
    )

    if bullish_sweep:
        distance = (
            low_level
            - current_low
        )

        return {
            "detected": True,
            "direction": (
                "BULLISH_LIQUIDITY_SWEEP"
            ),
            "status": "CONFIRMED",
            "level": low_level,
            "sweep_price": (
                current_low
            ),
            "close_price": (
                current_close
            ),
            "distance": round(
                max(
                    distance,
                    0.0,
                ),
                5,
            ),
            "candle_index": (
                current_index
            ),
            "liquidity_candle_index": (
                low_index
            ),
        }

    if bearish_sweep:
        distance = (
            current_high
            - high_level
        )

        return {
            "detected": True,
            "direction": (
                "BEARISH_LIQUIDITY_SWEEP"
            ),
            "status": "CONFIRMED",
            "level": high_level,
            "sweep_price": (
                current_high
            ),
            "close_price": (
                current_close
            ),
            "distance": round(
                max(
                    distance,
                    0.0,
                ),
                5,
            ),
            "candle_index": (
                current_index
            ),
            "liquidity_candle_index": (
                high_index
            ),
        }

    result = _default_result()
    result[
        "close_price"
    ] = current_close

    return result


__all__ = [
    "MAXIMUM_CANDLES",
    "MAXIMUM_CONFIRMATION_BUFFER",
    "MAXIMUM_LOOKBACK",
    "MINIMUM_CANDLES",
    "detect_liquidity_sweep",
]