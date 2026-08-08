"""
Candlestick Pattern Detection Engine.

Candles must be ordered from oldest to newest and use this format:

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


MINIMUM_CANDLES: Final[int] = 2
MAXIMUM_CANDLES: Final[int] = 100_000
DOJI_TOLERANCE: Final[float] = 0.10


def _default_result(
    status: str = "NO_PATTERN",
) -> dict:
    return {
        "detected": False,
        "status": status,
        "direction": "NONE",
        "pattern": "NONE",
        "strength": 0,
        "candle_index": None,
        "confirmation_index": None,
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


def _body_size(
    candle: Mapping[str, float],
) -> float:
    value = abs(
        candle[
            "close"
        ]
        - candle[
            "open"
        ]
    )

    return (
        value
        if math.isfinite(
            value
        )
        else 0.0
    )


def _range_size(
    candle: Mapping[str, float],
) -> float:
    value = (
        candle[
            "high"
        ]
        - candle[
            "low"
        ]
    )

    return (
        value
        if math.isfinite(
            value
        )
        and value >= 0.0
        else 0.0
    )


def _upper_wick(
    candle: Mapping[str, float],
) -> float:
    value = (
        candle[
            "high"
        ]
        - max(
            candle[
                "open"
            ],
            candle[
                "close"
            ],
        )
    )

    return (
        max(
            value,
            0.0,
        )
        if math.isfinite(
            value
        )
        else 0.0
    )


def _lower_wick(
    candle: Mapping[str, float],
) -> float:
    value = (
        min(
            candle[
                "open"
            ],
            candle[
                "close"
            ],
        )
        - candle[
            "low"
        ]
    )

    return (
        max(
            value,
            0.0,
        )
        if math.isfinite(
            value
        )
        else 0.0
    )


def _is_bullish(
    candle: Mapping[str, float],
) -> bool:
    return (
        candle[
            "close"
        ]
        > candle[
            "open"
        ]
    )


def _is_bearish(
    candle: Mapping[str, float],
) -> bool:
    return (
        candle[
            "close"
        ]
        < candle[
            "open"
        ]
    )


def _is_doji(
    candle: Mapping[str, float],
    tolerance: float = DOJI_TOLERANCE,
) -> bool:
    try:
        resolved_tolerance = float(
            tolerance
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return False

    if (
        not math.isfinite(
            resolved_tolerance
        )
        or resolved_tolerance < 0.0
        or resolved_tolerance > 1.0
    ):
        return False

    candle_range = _range_size(
        candle
    )

    if candle_range <= 0.0:
        return False

    return (
        _body_size(
            candle
        )
        <= candle_range
        * resolved_tolerance
    )


def detect_candlestick_pattern(
    candles: list,
) -> dict:
    """
    Detect the strongest recent candlestick pattern.

    Patterns:
    - Bullish Engulfing
    - Bearish Engulfing
    - Hammer
    - Shooting Star
    - Bullish Pin Bar
    - Bearish Pin Bar
    - Morning Star
    - Evening Star
    - Three White Soldiers
    - Three Black Crows
    - Doji
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

    current = resolved_candles[
        -1
    ]
    previous = resolved_candles[
        -2
    ]
    current_index = (
        len(
            resolved_candles
        )
        - 1
    )
    current_price = float(
        current[
            "close"
        ]
    )

    candidates: list[
        dict[str, Any]
    ] = []

    def add_candidate(
        pattern: str,
        direction: str,
        strength: int,
        candle_index: int,
        confirmation_index: int | None = None,
    ) -> None:
        candidates.append(
            {
                "detected": True,
                "status": "CONFIRMED",
                "direction": direction,
                "pattern": pattern,
                "strength": strength,
                "candle_index": (
                    candle_index
                ),
                "confirmation_index": (
                    confirmation_index
                ),
                "current_price": (
                    current_price
                ),
            }
        )

    bullish_engulfing = (
        _is_bearish(
            previous
        )
        and _is_bullish(
            current
        )
        and current[
            "open"
        ]
        <= previous[
            "close"
        ]
        and current[
            "close"
        ]
        >= previous[
            "open"
        ]
        and _body_size(
            current
        )
        > _body_size(
            previous
        )
    )

    bearish_engulfing = (
        _is_bullish(
            previous
        )
        and _is_bearish(
            current
        )
        and current[
            "open"
        ]
        >= previous[
            "close"
        ]
        and current[
            "close"
        ]
        <= previous[
            "open"
        ]
        and _body_size(
            current
        )
        > _body_size(
            previous
        )
    )

    if bullish_engulfing:
        add_candidate(
            "BULLISH_ENGULFING",
            "BULLISH",
            85,
            current_index,
            current_index,
        )

    if bearish_engulfing:
        add_candidate(
            "BEARISH_ENGULFING",
            "BEARISH",
            85,
            current_index,
            current_index,
        )

    candle_range = _range_size(
        current
    )
    body = _body_size(
        current
    )
    upper_wick = _upper_wick(
        current
    )
    lower_wick = _lower_wick(
        current
    )

    if candle_range > 0.0:
        small_body = (
            body
            <= candle_range
            * 0.35
        )

        hammer = (
            small_body
            and lower_wick
            >= max(
                body
                * 2.0,
                candle_range
                * 0.45,
            )
            and upper_wick
            <= candle_range
            * 0.20
        )

        shooting_star = (
            small_body
            and upper_wick
            >= max(
                body
                * 2.0,
                candle_range
                * 0.45,
            )
            and lower_wick
            <= candle_range
            * 0.20
        )

        bullish_pin_bar = (
            lower_wick
            >= candle_range
            * 0.60
            and upper_wick
            <= candle_range
            * 0.15
            and current[
                "close"
            ]
            >= current[
                "open"
            ]
        )

        bearish_pin_bar = (
            upper_wick
            >= candle_range
            * 0.60
            and lower_wick
            <= candle_range
            * 0.15
            and current[
                "close"
            ]
            <= current[
                "open"
            ]
        )

        if hammer:
            add_candidate(
                "HAMMER",
                "BULLISH",
                70,
                current_index,
            )

        if shooting_star:
            add_candidate(
                "SHOOTING_STAR",
                "BEARISH",
                70,
                current_index,
            )

        if bullish_pin_bar:
            add_candidate(
                "BULLISH_PIN_BAR",
                "BULLISH",
                75,
                current_index,
            )

        if bearish_pin_bar:
            add_candidate(
                "BEARISH_PIN_BAR",
                "BEARISH",
                75,
                current_index,
            )

    if len(
        resolved_candles
    ) >= 3:
        first = resolved_candles[
            -3
        ]
        middle = resolved_candles[
            -2
        ]
        third = resolved_candles[
            -1
        ]

        first_index = (
            len(
                resolved_candles
            )
            - 3
        )
        third_index = (
            len(
                resolved_candles
            )
            - 1
        )

        first_body = _body_size(
            first
        )
        middle_body = _body_size(
            middle
        )

        morning_star = (
            _is_bearish(
                first
            )
            and middle_body
            <= first_body
            * 0.50
            and _is_bullish(
                third
            )
            and third[
                "close"
            ]
            >= (
                first[
                    "open"
                ]
                + first[
                    "close"
                ]
            )
            / 2.0
        )

        evening_star = (
            _is_bullish(
                first
            )
            and middle_body
            <= first_body
            * 0.50
            and _is_bearish(
                third
            )
            and third[
                "close"
            ]
            <= (
                first[
                    "open"
                ]
                + first[
                    "close"
                ]
            )
            / 2.0
        )

        three_white_soldiers = (
            all(
                _is_bullish(
                    candle
                )
                for candle in (
                    first,
                    middle,
                    third,
                )
            )
            and middle[
                "close"
            ]
            > first[
                "close"
            ]
            and third[
                "close"
            ]
            > middle[
                "close"
            ]
            and middle[
                "open"
            ]
            >= first[
                "open"
            ]
            and third[
                "open"
            ]
            >= middle[
                "open"
            ]
        )

        three_black_crows = (
            all(
                _is_bearish(
                    candle
                )
                for candle in (
                    first,
                    middle,
                    third,
                )
            )
            and middle[
                "close"
            ]
            < first[
                "close"
            ]
            and third[
                "close"
            ]
            < middle[
                "close"
            ]
            and middle[
                "open"
            ]
            <= first[
                "open"
            ]
            and third[
                "open"
            ]
            <= middle[
                "open"
            ]
        )

        if morning_star:
            add_candidate(
                "MORNING_STAR",
                "BULLISH",
                90,
                first_index,
                third_index,
            )

        if evening_star:
            add_candidate(
                "EVENING_STAR",
                "BEARISH",
                90,
                first_index,
                third_index,
            )

        if three_white_soldiers:
            add_candidate(
                "THREE_WHITE_SOLDIERS",
                "BULLISH",
                95,
                first_index,
                third_index,
            )

        if three_black_crows:
            add_candidate(
                "THREE_BLACK_CROWS",
                "BEARISH",
                95,
                first_index,
                third_index,
            )

    if _is_doji(
        current
    ):
        add_candidate(
            "DOJI",
            "NEUTRAL",
            40,
            current_index,
        )

    if not candidates:
        result = _default_result()
        result[
            "current_price"
        ] = current_price

        return result

    candidates.sort(
        key=lambda item: (
            int(
                item[
                    "strength"
                ]
            ),
            int(
                item[
                    "candle_index"
                ]
            ),
        ),
        reverse=True,
    )

    return dict(
        candidates[
            0
        ]
    )


__all__ = [
    "DOJI_TOLERANCE",
    "MAXIMUM_CANDLES",
    "MINIMUM_CANDLES",
    "detect_candlestick_pattern",
]