"""Breaker Block Detection Engine for Blue-Trading-AI.

A breaker block is treated as a failed order block that price breaks through
and later retests from the opposite side.
"""

from __future__ import annotations

import math
from typing import Any, Final, Mapping


MINIMUM_CANDLES: Final[int] = 6
MAXIMUM_CANDLES: Final[int] = 100_000
MAXIMUM_LOOKBACK: Final[int] = 5_000
MAXIMUM_BREAKER_AGE: Final[int] = 1_000
MAXIMUM_ATR_PERIOD: Final[int] = 1_000

MINIMUM_IMPULSE_MULTIPLIER: Final[float] = 0.1
MAXIMUM_IMPULSE_MULTIPLIER: Final[float] = 100.0
MINIMUM_NEAR_ATR_MULTIPLIER: Final[float] = 0.0
MAXIMUM_NEAR_ATR_MULTIPLIER: Final[float] = 10.0


def _default_result(
    status: str = "NO_BREAKER_BLOCK",
) -> dict:
    return {
        "detected": False,
        "status": status,
        "direction": "NONE",
        "zone_high": None,
        "zone_low": None,
        "source_index": None,
        "break_index": None,
        "retest_index": None,
        "current_price": None,
        "price_inside_zone": False,
        "price_near_zone": False,
        "near_tolerance": None,
        "retest": False,
        "mitigated": False,
        "bos_confirmed": False,
        "choch_confirmed": False,
        "distance_to_zone": None,
        "distance_percent": None,
        "strength": 0,
        "actionable": False,
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
        minimum <= resolved <= maximum
    ):
        return None

    return resolved


def _normalise_float(
    value: Any,
    *,
    minimum: float,
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
        minimum <= resolved <= maximum
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

    candle_open = resolved["open"]
    candle_high = resolved["high"]
    candle_low = resolved["low"]
    candle_close = resolved["close"]

    if candle_high < candle_low:
        return None

    if not (
        candle_low <= candle_open <= candle_high
    ):
        return None

    if not (
        candle_low <= candle_close <= candle_high
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
        resolved = _normalise_candle(candle)

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


def _bullish(
    candle: Mapping[str, float],
) -> bool:
    return candle["close"] > candle["open"]


def _bearish(
    candle: Mapping[str, float],
) -> bool:
    return candle["close"] < candle["open"]


def _body(
    candle: Mapping[str, float],
) -> float:
    value = abs(
        candle["close"] - candle["open"]
    )

    return (
        value
        if math.isfinite(value)
        else 0.0
    )


def _average_true_range(
    candles,
    period=14,
):
    resolved_period = _normalise_positive_int(
        period,
        minimum=1,
        maximum=MAXIMUM_ATR_PERIOD,
    )

    if (
        resolved_period is None
        or not candles
    ):
        return 0.0

    values: list[float] = []

    start = max(
        0,
        len(candles) - resolved_period,
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
            candle["high"] - candle["low"],
            abs(
                candle["high"] - previous_close
            ),
            abs(
                candle["low"] - previous_close
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

    average = sum(values) / len(values)

    return (
        average
        if math.isfinite(average)
        and average >= 0.0
        else 0.0
    )


def _zone_distance(
    current_price,
    zone_low,
    zone_high,
):
    if (
        not all(
            math.isfinite(value)
            for value in (
                current_price,
                zone_low,
                zone_high,
            )
        )
        or current_price <= 0.0
        or zone_low <= 0.0
        or zone_high <= 0.0
        or zone_low > zone_high
    ):
        return 0.0

    if zone_low <= current_price <= zone_high:
        return 0.0

    if current_price > zone_high:
        return current_price - zone_high

    return current_price - zone_low


def _normalise_direction(
    payload: Any,
) -> str:
    if not isinstance(payload, Mapping):
        return "NONE"

    direction = str(
        payload.get("direction", "NONE")
        or "NONE"
    ).strip().upper()

    allowed = {
        "NONE",
        "BULLISH",
        "BEARISH",
        "BULLISH_BOS",
        "BEARISH_BOS",
        "BULLISH_CHOCH",
        "BEARISH_CHOCH",
    }

    return (
        direction
        if direction in allowed
        else "NONE"
    )


def detect_breaker_block(
    candles,
    bos=None,
    choch=None,
    lookback=50,
    impulse_multiplier=1.5,
    near_atr_multiplier=0.35,
    max_age=30,
):
    """
    Detect the most relevant bullish or bearish breaker block.

    Bullish breaker:
    - A bearish source candle fails
    - Price closes above its zone
    - Price later retests it as support

    Bearish breaker:
    - A bullish source candle fails
    - Price closes below its zone
    - Price later retests it as resistance
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

    resolved_candles = _normalise_candles(
        candles
    )

    if not resolved_candles:
        return _default_result(
            "INSUFFICIENT_OHLC_DATA"
        )

    resolved_lookback = _normalise_positive_int(
        lookback,
        minimum=1,
        maximum=MAXIMUM_LOOKBACK,
    )
    resolved_impulse_multiplier = _normalise_float(
        impulse_multiplier,
        minimum=MINIMUM_IMPULSE_MULTIPLIER,
        maximum=MAXIMUM_IMPULSE_MULTIPLIER,
    )
    resolved_near_atr_multiplier = _normalise_float(
        near_atr_multiplier,
        minimum=MINIMUM_NEAR_ATR_MULTIPLIER,
        maximum=MAXIMUM_NEAR_ATR_MULTIPLIER,
    )
    resolved_max_age = _normalise_positive_int(
        max_age,
        minimum=1,
        maximum=MAXIMUM_BREAKER_AGE,
    )

    current_price = float(
        resolved_candles[-1]["close"]
    )

    if (
        resolved_lookback is None
        or resolved_impulse_multiplier is None
        or resolved_near_atr_multiplier is None
        or resolved_max_age is None
    ):
        result = _default_result(
            "INVALID_CONFIGURATION"
        )
        result["current_price"] = current_price
        return result

    selected = (
        resolved_candles[-resolved_lookback:]
        if resolved_lookback
        < len(resolved_candles)
        else resolved_candles
    )

    if len(selected) < 4:
        result = _default_result(
            "INSUFFICIENT_LOOKBACK_DATA"
        )
        result["current_price"] = current_price
        return result

    offset = (
        len(resolved_candles)
        - len(selected)
    )

    atr = _average_true_range(
        resolved_candles,
        period=14,
    )

    near_tolerance = max(
        atr * resolved_near_atr_multiplier,
        current_price * 0.0005,
    )

    if (
        not math.isfinite(near_tolerance)
        or near_tolerance < 0.0
    ):
        result = _default_result(
            "INVALID_CONFIGURATION"
        )
        result["current_price"] = current_price
        return result

    average_body = (
        sum(
            _body(candle)
            for candle in selected
        )
        / len(selected)
    )

    if (
        not math.isfinite(average_body)
        or average_body <= 0.0
    ):
        result = _default_result()
        result["current_price"] = current_price
        result["near_tolerance"] = float(
            near_tolerance
        )
        return result

    required_impulse_body = (
        average_body
        * resolved_impulse_multiplier
    )

    if (
        not math.isfinite(required_impulse_body)
        or required_impulse_body <= 0.0
    ):
        result = _default_result(
            "INVALID_CONFIGURATION"
        )
        result["current_price"] = current_price
        return result

    bos_direction = _normalise_direction(
        bos
    )
    choch_direction = _normalise_direction(
        choch
    )

    candidates: list[dict[str, Any]] = []

    for index in range(
        len(selected) - 3
    ):
        source = selected[index]
        source_index = index + offset

        age = (
            len(resolved_candles)
            - 1
            - source_index
        )

        if (
            age < 0
            or age > resolved_max_age
        ):
            continue

        zone_high = float(
            source["high"]
        )
        zone_low = float(
            source["low"]
        )

        if (
            not math.isfinite(zone_high)
            or not math.isfinite(zone_low)
            or zone_low <= 0.0
            or zone_high <= 0.0
            or zone_low > zone_high
        ):
            continue

        if _bearish(source):
            break_index = None

            for future_index in range(
                index + 1,
                len(selected),
            ):
                future = selected[
                    future_index
                ]

                if (
                    future["close"] > zone_high
                    and _body(future)
                    >= required_impulse_body
                ):
                    break_index = (
                        future_index
                        + offset
                    )
                    break

            if break_index is not None:
                retest_index = None

                for global_index in range(
                    break_index + 1,
                    len(resolved_candles),
                ):
                    candle = resolved_candles[
                        global_index
                    ]

                    if (
                        candle["low"]
                        <= zone_high
                        + near_tolerance
                        and candle["high"]
                        >= zone_low
                        - near_tolerance
                    ):
                        retest_index = (
                            global_index
                        )

                price_inside = (
                    zone_low
                    <= current_price
                    <= zone_high
                )

                distance = _zone_distance(
                    current_price,
                    zone_low,
                    zone_high,
                )

                price_near = (
                    not price_inside
                    and abs(distance)
                    <= near_tolerance
                )

                retest = (
                    retest_index is not None
                    and (
                        price_inside
                        or price_near
                    )
                )

                mitigated = any(
                    candle["close"]
                    < zone_low
                    for candle in resolved_candles[
                        break_index + 1:
                    ]
                )

                bos_confirmed = (
                    bos_direction
                    in {
                        "BULLISH",
                        "BULLISH_BOS",
                    }
                )

                choch_confirmed = (
                    choch_direction
                    in {
                        "BULLISH",
                        "BULLISH_CHOCH",
                    }
                )

                strength = 35
                strength += (
                    20
                    if retest
                    else 0
                )
                strength += (
                    15
                    if price_inside
                    else 10
                    if price_near
                    else 0
                )
                strength += (
                    15
                    if bos_confirmed
                    else 0
                )
                strength += (
                    15
                    if choch_confirmed
                    else 0
                )
                strength = min(
                    100,
                    strength,
                )

                actionable = (
                    not mitigated
                    and (
                        price_inside
                        or price_near
                    )
                    and retest
                    and (
                        bos_confirmed
                        or choch_confirmed
                    )
                )

                distance_percent = (
                    abs(distance)
                    / current_price
                    * 100.0
                )

                if not math.isfinite(
                    distance_percent
                ):
                    continue

                candidates.append(
                    {
                        "detected": True,
                        "status": (
                            "MITIGATED"
                            if mitigated
                            else "ACTIVE"
                            if actionable
                            else "DETECTED"
                        ),
                        "direction": "BULLISH",
                        "zone_high": zone_high,
                        "zone_low": zone_low,
                        "source_index": source_index,
                        "break_index": break_index,
                        "retest_index": retest_index,
                        "current_price": current_price,
                        "price_inside_zone": price_inside,
                        "price_near_zone": price_near,
                        "near_tolerance": float(
                            near_tolerance
                        ),
                        "retest": retest,
                        "mitigated": mitigated,
                        "bos_confirmed": (
                            bos_confirmed
                        ),
                        "choch_confirmed": (
                            choch_confirmed
                        ),
                        "distance_to_zone": float(
                            distance
                        ),
                        "distance_percent": round(
                            distance_percent,
                            4,
                        ),
                        "strength": int(
                            strength
                        ),
                        "actionable": actionable,
                    }
                )

        if _bullish(source):
            break_index = None

            for future_index in range(
                index + 1,
                len(selected),
            ):
                future = selected[
                    future_index
                ]

                if (
                    future["close"] < zone_low
                    and _body(future)
                    >= required_impulse_body
                ):
                    break_index = (
                        future_index
                        + offset
                    )
                    break

            if break_index is not None:
                retest_index = None

                for global_index in range(
                    break_index + 1,
                    len(resolved_candles),
                ):
                    candle = resolved_candles[
                        global_index
                    ]

                    if (
                        candle["high"]
                        >= zone_low
                        - near_tolerance
                        and candle["low"]
                        <= zone_high
                        + near_tolerance
                    ):
                        retest_index = (
                            global_index
                        )

                price_inside = (
                    zone_low
                    <= current_price
                    <= zone_high
                )

                distance = _zone_distance(
                    current_price,
                    zone_low,
                    zone_high,
                )

                price_near = (
                    not price_inside
                    and abs(distance)
                    <= near_tolerance
                )

                retest = (
                    retest_index is not None
                    and (
                        price_inside
                        or price_near
                    )
                )

                mitigated = any(
                    candle["close"]
                    > zone_high
                    for candle in resolved_candles[
                        break_index + 1:
                    ]
                )

                bos_confirmed = (
                    bos_direction
                    in {
                        "BEARISH",
                        "BEARISH_BOS",
                    }
                )

                choch_confirmed = (
                    choch_direction
                    in {
                        "BEARISH",
                        "BEARISH_CHOCH",
                    }
                )

                strength = 35
                strength += (
                    20
                    if retest
                    else 0
                )
                strength += (
                    15
                    if price_inside
                    else 10
                    if price_near
                    else 0
                )
                strength += (
                    15
                    if bos_confirmed
                    else 0
                )
                strength += (
                    15
                    if choch_confirmed
                    else 0
                )
                strength = min(
                    100,
                    strength,
                )

                actionable = (
                    not mitigated
                    and (
                        price_inside
                        or price_near
                    )
                    and retest
                    and (
                        bos_confirmed
                        or choch_confirmed
                    )
                )

                distance_percent = (
                    abs(distance)
                    / current_price
                    * 100.0
                )

                if not math.isfinite(
                    distance_percent
                ):
                    continue

                candidates.append(
                    {
                        "detected": True,
                        "status": (
                            "MITIGATED"
                            if mitigated
                            else "ACTIVE"
                            if actionable
                            else "DETECTED"
                        ),
                        "direction": "BEARISH",
                        "zone_high": zone_high,
                        "zone_low": zone_low,
                        "source_index": source_index,
                        "break_index": break_index,
                        "retest_index": retest_index,
                        "current_price": current_price,
                        "price_inside_zone": price_inside,
                        "price_near_zone": price_near,
                        "near_tolerance": float(
                            near_tolerance
                        ),
                        "retest": retest,
                        "mitigated": mitigated,
                        "bos_confirmed": (
                            bos_confirmed
                        ),
                        "choch_confirmed": (
                            choch_confirmed
                        ),
                        "distance_to_zone": float(
                            distance
                        ),
                        "distance_percent": round(
                            distance_percent,
                            4,
                        ),
                        "strength": int(
                            strength
                        ),
                        "actionable": actionable,
                    }
                )

    if not candidates:
        result = _default_result()
        result["current_price"] = (
            current_price
        )
        result["near_tolerance"] = float(
            near_tolerance
        )
        return result

    status_rank = {
        "ACTIVE": 4,
        "DETECTED": 3,
        "MITIGATED": 1,
    }

    candidates.sort(
        key=lambda item: (
            status_rank.get(
                str(item["status"]),
                0,
            ),
            int(item["strength"]),
            int(item["source_index"]),
        ),
        reverse=True,
    )

    return dict(candidates[0])


__all__ = [
    "MAXIMUM_BREAKER_AGE",
    "MAXIMUM_CANDLES",
    "MAXIMUM_LOOKBACK",
    "MINIMUM_CANDLES",
    "detect_breaker_block",
]