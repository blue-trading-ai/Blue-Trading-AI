"""Equal Highs and Equal Lows Detection for Blue-Trading-AI.

This module identifies clustered swing highs and lows that can act as
liquidity pools before a sweep, breakout, or reversal.
"""

from __future__ import annotations

import math
from typing import Any, Final, Mapping


MINIMUM_CANDLES: Final[int] = 8
MAXIMUM_CANDLES: Final[int] = 100_000
MAXIMUM_LOOKBACK: Final[int] = 5_000
MAXIMUM_SWING_LENGTH: Final[int] = 100
MAXIMUM_MINIMUM_SEPARATION: Final[int] = 5_000
MAXIMUM_PAIR_AGE: Final[int] = 5_000
MAXIMUM_ATR_PERIOD: Final[int] = 1_000
MAXIMUM_TOLERANCE_ATR_MULTIPLIER: Final[float] = 10.0
MAXIMUM_NEAR_ATR_MULTIPLIER: Final[float] = 10.0


def _default_result(
    status: str = "NO_LIQUIDITY_POOL",
) -> dict:
    return {
        "detected": False,
        "status": status,
        "type": "NONE",
        "direction": "NONE",
        "level": None,
        "first_index": None,
        "second_index": None,
        "touches": 0,
        "tolerance": None,
        "distance_to_level": None,
        "distance_percent": None,
        "current_price": None,
        "price_near_level": False,
        "swept": False,
        "breakout": False,
        "strength": 0,
    }


def _finite_positive_float(
    value: Any,
) -> float | None:
    try:
        resolved = float(value)
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None

    if (
        not math.isfinite(resolved)
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
    if isinstance(value, bool):
        return None

    try:
        resolved = int(value)
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


def _normalise_non_negative_float(
    value: Any,
    *,
    maximum: float,
) -> float | None:
    try:
        resolved = float(value)
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None

    if not math.isfinite(resolved):
        return None

    if not (
        0.0
        <= resolved
        <= maximum
    ):
        return None

    return resolved


def _normalise_candle(
    candle: Any,
) -> dict[str, float] | None:
    if not isinstance(candle, Mapping):
        return None

    resolved: dict[str, float] = {}

    for field in (
        "open",
        "high",
        "low",
        "close",
    ):
        value = _finite_positive_float(
            candle.get(field)
        )

        if value is None:
            return None

        resolved[field] = value

    candle_high = resolved["high"]
    candle_low = resolved["low"]
    candle_open = resolved["open"]
    candle_close = resolved["close"]

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

    if len(candles) > MAXIMUM_CANDLES:
        return []

    output: list[dict[str, float]] = []

    for candle in candles:
        resolved = _normalise_candle(
            candle
        )

        if resolved is None:
            return []

        output.append(resolved)

    return output


def _valid_candle(
    candle: object,
) -> bool:
    return (
        _normalise_candle(candle)
        is not None
    )


def _average_true_range(
    candles,
    period=14,
):
    resolved_period = (
        _normalise_positive_int(
            period,
            minimum=1,
            maximum=MAXIMUM_ATR_PERIOD,
        )
    )

    if (
        resolved_period is None
        or not candles
    ):
        return 0.0

    values: list[float] = []

    start = max(
        0,
        len(candles)
        - resolved_period,
    )

    for index in range(
        start,
        len(candles),
    ):
        candle = candles[index]

        previous_close = (
            candles[index - 1]["close"]
            if index > 0
            else candle["close"]
        )

        true_range = max(
            candle["high"]
            - candle["low"],
            abs(
                candle["high"]
                - previous_close
            ),
            abs(
                candle["low"]
                - previous_close
            ),
        )

        if (
            not math.isfinite(true_range)
            or true_range < 0.0
        ):
            return 0.0

        values.append(true_range)

    if not values:
        return 0.0

    average = (
        sum(values)
        / len(values)
    )

    return (
        average
        if math.isfinite(average)
        and average >= 0.0
        else 0.0
    )


def _swing_highs(
    candles,
    swing_length=2,
):
    resolved_swing_length = (
        _normalise_positive_int(
            swing_length,
            minimum=1,
            maximum=MAXIMUM_SWING_LENGTH,
        )
    )

    if resolved_swing_length is None:
        return []

    if len(candles) < (
        resolved_swing_length * 2
        + 1
    ):
        return []

    points: list[
        tuple[int, float]
    ] = []

    for index in range(
        resolved_swing_length,
        len(candles)
        - resolved_swing_length,
    ):
        value = candles[index]["high"]

        if all(
            value
            >= candles[
                index - offset
            ]["high"]
            and value
            >= candles[
                index + offset
            ]["high"]
            for offset in range(
                1,
                resolved_swing_length + 1,
            )
        ):
            points.append(
                (
                    index,
                    float(value),
                )
            )

    return points


def _swing_lows(
    candles,
    swing_length=2,
):
    resolved_swing_length = (
        _normalise_positive_int(
            swing_length,
            minimum=1,
            maximum=MAXIMUM_SWING_LENGTH,
        )
    )

    if resolved_swing_length is None:
        return []

    if len(candles) < (
        resolved_swing_length * 2
        + 1
    ):
        return []

    points: list[
        tuple[int, float]
    ] = []

    for index in range(
        resolved_swing_length,
        len(candles)
        - resolved_swing_length,
    ):
        value = candles[index]["low"]

        if all(
            value
            <= candles[
                index - offset
            ]["low"]
            and value
            <= candles[
                index + offset
            ]["low"]
            for offset in range(
                1,
                resolved_swing_length + 1,
            )
        ):
            points.append(
                (
                    index,
                    float(value),
                )
            )

    return points


def _build_candidate(
    *,
    pool_type,
    first,
    second,
    candles,
    tolerance,
    near_tolerance,
):
    if pool_type not in {
        "EQUAL_HIGHS",
        "EQUAL_LOWS",
    }:
        return None

    if not (
        isinstance(first, tuple)
        and len(first) == 2
        and isinstance(second, tuple)
        and len(second) == 2
    ):
        return None

    first_index, first_price = first
    second_index, second_price = second

    if not (
        isinstance(first_index, int)
        and isinstance(second_index, int)
        and 0 <= first_index < second_index
        and second_index < len(candles)
    ):
        return None

    resolved_first_price = (
        _finite_positive_float(
            first_price
        )
    )
    resolved_second_price = (
        _finite_positive_float(
            second_price
        )
    )

    if (
        resolved_first_price is None
        or resolved_second_price is None
    ):
        return None

    try:
        resolved_tolerance = float(
            tolerance
        )
        resolved_near_tolerance = float(
            near_tolerance
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None

    if (
        not math.isfinite(
            resolved_tolerance
        )
        or not math.isfinite(
            resolved_near_tolerance
        )
        or resolved_tolerance < 0.0
        or resolved_near_tolerance < 0.0
    ):
        return None

    level = (
        resolved_first_price
        + resolved_second_price
    ) / 2.0

    if (
        not math.isfinite(level)
        or level <= 0.0
    ):
        return None

    current_price = float(
        candles[-1]["close"]
    )
    latest = candles[-1]

    touches = 2

    for index in range(
        second_index + 1,
        len(candles),
    ):
        test_price = (
            candles[index]["high"]
            if pool_type
            == "EQUAL_HIGHS"
            else candles[index]["low"]
        )

        if (
            abs(
                test_price
                - level
            )
            <= resolved_tolerance
        ):
            touches += 1

    if pool_type == "EQUAL_HIGHS":
        swept = (
            latest["high"]
            > level
            + resolved_tolerance
            and latest["close"]
            < level
        )
        breakout = (
            latest["close"]
            > level
            + resolved_tolerance
        )
        direction = (
            "BEARISH_LIQUIDITY"
        )
        distance = (
            level
            - current_price
        )

    else:
        swept = (
            latest["low"]
            < level
            - resolved_tolerance
            and latest["close"]
            > level
        )
        breakout = (
            latest["close"]
            < level
            - resolved_tolerance
        )
        direction = (
            "BULLISH_LIQUIDITY"
        )
        distance = (
            current_price
            - level
        )

    near = (
        abs(
            current_price
            - level
        )
        <= resolved_near_tolerance
    )

    age = (
        len(candles)
        - 1
        - second_index
    )
    recency_score = max(
        0,
        30 - age,
    )
    touch_score = min(
        30,
        touches * 10,
    )
    reaction_score = (
        25
        if swept
        else 15
        if breakout
        else 0
    )
    proximity_score = (
        15
        if near
        else 0
    )

    strength = min(
        100,
        recency_score
        + touch_score
        + reaction_score
        + proximity_score,
    )

    distance_percent = (
        abs(
            current_price
            - level
        )
        / current_price
        * 100.0
    )

    if (
        not math.isfinite(distance)
        or not math.isfinite(
            distance_percent
        )
    ):
        return None

    if swept:
        status = "SWEPT"
    elif breakout:
        status = "BROKEN"
    elif near:
        status = "ACTIVE_NEAR"
    else:
        status = "ACTIVE"

    return {
        "detected": True,
        "status": status,
        "type": pool_type,
        "direction": direction,
        "level": float(level),
        "first_index": first_index,
        "second_index": second_index,
        "touches": touches,
        "tolerance": float(
            resolved_tolerance
        ),
        "distance_to_level": float(
            distance
        ),
        "distance_percent": round(
            distance_percent,
            4,
        ),
        "current_price": current_price,
        "price_near_level": near,
        "swept": swept,
        "breakout": breakout,
        "strength": int(strength),
    }


def detect_equal_highs_lows(
    candles,
    lookback=50,
    swing_length=2,
    tolerance_atr_multiplier=0.12,
    near_atr_multiplier=0.35,
    minimum_separation=3,
    max_pair_age=30,
):
    """
    Detect the strongest recent Equal Highs or Equal Lows liquidity pool.

    Equal Highs:
    - Potential buy-side liquidity above the level
    - A sweep can support a bearish reversal

    Equal Lows:
    - Potential sell-side liquidity below the level
    - A sweep can support a bullish reversal
    """

    if not isinstance(
        candles,
        (list, tuple),
    ):
        return _default_result(
            "INSUFFICIENT_OHLC_DATA"
        )

    if len(candles) < MINIMUM_CANDLES:
        return _default_result(
            "INSUFFICIENT_DATA"
        )

    resolved_candles = (
        _normalise_candles(candles)
    )

    if not resolved_candles:
        return _default_result(
            "INSUFFICIENT_OHLC_DATA"
        )

    resolved_lookback = (
        _normalise_positive_int(
            lookback,
            minimum=1,
            maximum=MAXIMUM_LOOKBACK,
        )
    )
    resolved_swing_length = (
        _normalise_positive_int(
            swing_length,
            minimum=1,
            maximum=MAXIMUM_SWING_LENGTH,
        )
    )
    resolved_tolerance_multiplier = (
        _normalise_non_negative_float(
            tolerance_atr_multiplier,
            maximum=MAXIMUM_TOLERANCE_ATR_MULTIPLIER,
        )
    )
    resolved_near_multiplier = (
        _normalise_non_negative_float(
            near_atr_multiplier,
            maximum=MAXIMUM_NEAR_ATR_MULTIPLIER,
        )
    )
    resolved_minimum_separation = (
        _normalise_positive_int(
            minimum_separation,
            minimum=1,
            maximum=MAXIMUM_MINIMUM_SEPARATION,
        )
    )
    resolved_max_pair_age = (
        _normalise_positive_int(
            max_pair_age,
            minimum=1,
            maximum=MAXIMUM_PAIR_AGE,
        )
    )

    current_price = float(
        resolved_candles[-1]["close"]
    )

    if any(
        value is None
        for value in (
            resolved_lookback,
            resolved_swing_length,
            resolved_tolerance_multiplier,
            resolved_near_multiplier,
            resolved_minimum_separation,
            resolved_max_pair_age,
        )
    ):
        result = _default_result(
            "INVALID_CONFIGURATION"
        )
        result["current_price"] = (
            current_price
        )
        return result

    minimum_for_swings = (
        resolved_swing_length * 2
        + 1
    )

    if (
        resolved_lookback
        < minimum_for_swings
    ):
        result = _default_result(
            "INSUFFICIENT_SWING_WINDOW"
        )
        result["current_price"] = (
            current_price
        )
        return result

    selected = (
        resolved_candles[
            -resolved_lookback:
        ]
        if resolved_lookback
        < len(resolved_candles)
        else resolved_candles
    )

    offset = (
        len(resolved_candles)
        - len(selected)
    )

    atr = _average_true_range(
        resolved_candles,
        period=14,
    )

    tolerance = max(
        atr
        * resolved_tolerance_multiplier,
        current_price
        * 0.0002,
    )

    near_tolerance = max(
        atr
        * resolved_near_multiplier,
        current_price
        * 0.0005,
    )

    if (
        not math.isfinite(tolerance)
        or not math.isfinite(
            near_tolerance
        )
        or tolerance < 0.0
        or near_tolerance < 0.0
    ):
        result = _default_result(
            "INVALID_CONFIGURATION"
        )
        result["current_price"] = (
            current_price
        )
        return result

    highs = [
        (
            index + offset,
            price,
        )
        for index, price in _swing_highs(
            selected,
            resolved_swing_length,
        )
    ]

    lows = [
        (
            index + offset,
            price,
        )
        for index, price in _swing_lows(
            selected,
            resolved_swing_length,
        )
    ]

    candidates: list[dict[str, Any]] = []

    for points, pool_type in (
        (
            highs,
            "EQUAL_HIGHS",
        ),
        (
            lows,
            "EQUAL_LOWS",
        ),
    ):
        for first_position in range(
            len(points) - 1
        ):
            first = points[
                first_position
            ]

            for second_position in range(
                first_position + 1,
                len(points),
            ):
                second = points[
                    second_position
                ]

                if (
                    second[0]
                    - first[0]
                    < resolved_minimum_separation
                ):
                    continue

                if (
                    len(resolved_candles)
                    - 1
                    - second[0]
                    > resolved_max_pair_age
                ):
                    continue

                if (
                    abs(
                        first[1]
                        - second[1]
                    )
                    > tolerance
                ):
                    continue

                candidate = _build_candidate(
                    pool_type=pool_type,
                    first=first,
                    second=second,
                    candles=resolved_candles,
                    tolerance=tolerance,
                    near_tolerance=near_tolerance,
                )

                if candidate is not None:
                    candidates.append(
                        candidate
                    )

    if not candidates:
        result = _default_result()
        result["current_price"] = (
            current_price
        )
        result["tolerance"] = float(
            tolerance
        )
        return result

    status_rank = {
        "SWEPT": 5,
        "ACTIVE_NEAR": 4,
        "BROKEN": 3,
        "ACTIVE": 2,
    }

    candidates.sort(
        key=lambda item: (
            status_rank.get(
                str(item["status"]),
                0,
            ),
            int(item["strength"]),
            int(item["second_index"]),
        ),
        reverse=True,
    )

    return dict(candidates[0])


__all__ = [
    "MAXIMUM_CANDLES",
    "MAXIMUM_LOOKBACK",
    "MAXIMUM_PAIR_AGE",
    "MAXIMUM_SWING_LENGTH",
    "MINIMUM_CANDLES",
    "detect_equal_highs_lows",
]