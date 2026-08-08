"""Supply and Demand Zone Detection Engine for Blue-Trading-AI."""

from __future__ import annotations

import math
from typing import Any, Final, Mapping


MINIMUM_CANDLES: Final[int] = 4
MAXIMUM_CANDLES: Final[int] = 100_000
MAXIMUM_LOOKBACK: Final[int] = 5_000
MAXIMUM_ZONE_AGE: Final[int] = 5_000
MAXIMUM_ATR_PERIOD: Final[int] = 1_000
MINIMUM_IMPULSE_MULTIPLIER: Final[float] = 0.1
MAXIMUM_IMPULSE_MULTIPLIER: Final[float] = 100.0
MINIMUM_NEAR_ATR_MULTIPLIER: Final[float] = 0.0
MAXIMUM_NEAR_ATR_MULTIPLIER: Final[float] = 10.0


def _default(
    status: str = "NO_ZONE",
) -> dict:
    return {
        "detected": False,
        "status": status,
        "direction": "NONE",
        "zone_type": "NONE",
        "zone_high": None,
        "zone_low": None,
        "candle_index": None,
        "impulse_index": None,
        "impulse_strength": 0,
        "current_price": None,
        "price_inside_zone": False,
        "price_near_zone": False,
        "near_tolerance": None,
        "mitigated": False,
        "distance_to_zone": None,
        "distance_percent": None,
        "relevance": "NONE",
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


def _normalise_float(
    value: Any,
    *,
    minimum: float,
    maximum: float,
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
        minimum
        <= resolved
        <= maximum
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

    resolved: dict[
        str,
        float,
    ] = {}

    for field in (
        "open",
        "high",
        "low",
        "close",
    ):
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


def _valid(
    candle: object,
) -> bool:
    return (
        _normalise_candle(
            candle
        )
        is not None
    )


def _body(
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


def _bullish(
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


def _bearish(
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

    ranges: list[
        float
    ] = []

    start = max(
        0,
        len(
            candles
        )
        - resolved_period,
    )

    for index in range(
        start,
        len(
            candles
        ),
    ):
        candle = candles[
            index
        ]

        previous_close = (
            candles[
                index - 1
            ][
                "close"
            ]
            if index > 0
            else candle[
                "close"
            ]
        )

        true_range = max(
            candle[
                "high"
            ]
            - candle[
                "low"
            ],
            abs(
                candle[
                    "high"
                ]
                - previous_close
            ),
            abs(
                candle[
                    "low"
                ]
                - previous_close
            ),
        )

        if (
            not math.isfinite(
                true_range
            )
            or true_range < 0.0
        ):
            return 0.0

        ranges.append(
            true_range
        )

    if not ranges:
        return 0.0

    average = (
        sum(
            ranges
        )
        / len(
            ranges
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


def _distance_to_zone(
    current_price: float,
    zone_low: float,
    zone_high: float,
) -> float:
    if (
        zone_low
        <= current_price
        <= zone_high
    ):
        return 0.0

    if current_price > zone_high:
        return (
            current_price
            - zone_high
        )

    return (
        current_price
        - zone_low
    )


def detect_supply_demand(
    candles,
    lookback=50,
    impulse_multiplier=1.5,
    near_atr_multiplier=0.35,
    max_zone_age=30,
):
    """
    Detect the most relevant recent active supply or demand zone.

    A zone is relevant only when price is:
    - inside the zone, or
    - near the zone within an ATR-based tolerance.

    Old, mitigated, and distant zones remain visible in the output but are
    classified as non-actionable.
    """

    if not isinstance(
        candles,
        (list, tuple),
    ):
        return _default(
            "INSUFFICIENT_OHLC_DATA"
        )

    if len(
        candles
    ) < MINIMUM_CANDLES:
        return _default(
            "INSUFFICIENT_DATA"
        )

    resolved_candles = (
        _normalise_candles(
            candles
        )
    )

    if not resolved_candles:
        return _default(
            "INSUFFICIENT_OHLC_DATA"
        )

    resolved_lookback = (
        _normalise_positive_int(
            lookback,
            minimum=1,
            maximum=MAXIMUM_LOOKBACK,
        )
    )
    resolved_impulse_multiplier = (
        _normalise_float(
            impulse_multiplier,
            minimum=MINIMUM_IMPULSE_MULTIPLIER,
            maximum=MAXIMUM_IMPULSE_MULTIPLIER,
        )
    )
    resolved_near_atr_multiplier = (
        _normalise_float(
            near_atr_multiplier,
            minimum=MINIMUM_NEAR_ATR_MULTIPLIER,
            maximum=MAXIMUM_NEAR_ATR_MULTIPLIER,
        )
    )
    resolved_max_zone_age = (
        _normalise_positive_int(
            max_zone_age,
            minimum=1,
            maximum=MAXIMUM_ZONE_AGE,
        )
    )

    current_price = float(
        resolved_candles[
            -1
        ][
            "close"
        ]
    )

    if (
        resolved_lookback is None
        or resolved_impulse_multiplier is None
        or resolved_near_atr_multiplier is None
        or resolved_max_zone_age is None
    ):
        result = _default(
            "INVALID_CONFIGURATION"
        )
        result[
            "current_price"
        ] = current_price

        return result

    selected = (
        resolved_candles[
            -resolved_lookback:
        ]
        if resolved_lookback
        < len(
            resolved_candles
        )
        else resolved_candles
    )

    offset = (
        len(
            resolved_candles
        )
        - len(
            selected
        )
    )

    average_body = (
        sum(
            _body(
                candle
            )
            for candle in selected
        )
        / len(
            selected
        )
    )

    if (
        not math.isfinite(
            average_body
        )
        or average_body <= 0.0
    ):
        result = _default()
        result[
            "current_price"
        ] = current_price

        return result

    atr = _average_true_range(
        resolved_candles,
        period=14,
    )

    near_tolerance = max(
        atr
        * resolved_near_atr_multiplier,
        current_price
        * 0.0005,
    )

    if (
        not math.isfinite(
            near_tolerance
        )
        or near_tolerance < 0.0
    ):
        result = _default(
            "INVALID_CONFIGURATION"
        )
        result[
            "current_price"
        ] = current_price

        return result

    candidates: list[
        dict[str, Any]
    ] = []

    for index in range(
        len(
            selected
        )
        - 1
    ):
        base = selected[
            index
        ]
        impulse = selected[
            index + 1
        ]
        impulse_body = _body(
            impulse
        )

        required_body = (
            average_body
            * resolved_impulse_multiplier
        )

        if (
            not math.isfinite(
                required_body
            )
            or impulse_body
            < required_body
        ):
            continue

        base_index = (
            index
            + offset
        )
        impulse_index = (
            index
            + 1
            + offset
        )

        zone_age = (
            len(
                resolved_candles
            )
            - 1
            - base_index
        )

        if (
            zone_age < 0
            or zone_age
            > resolved_max_zone_age
        ):
            continue

        strength = (
            impulse_body
            / average_body
        )

        if not math.isfinite(
            strength
        ):
            continue

        rounded_strength = round(
            strength,
            2,
        )

        if (
            (
                _bearish(
                    base
                )
                or _body(
                    base
                )
                <= average_body
                * 0.75
            )
            and _bullish(
                impulse
            )
        ):
            zone_high = float(
                max(
                    base[
                        "open"
                    ],
                    base[
                        "close"
                    ],
                )
            )
            zone_low = float(
                base[
                    "low"
                ]
            )

            if (
                zone_low <= 0.0
                or zone_high <= 0.0
                or zone_low > zone_high
            ):
                continue

            later = (
                resolved_candles[
                    impulse_index + 1:
                ]
            )

            mitigated = any(
                candle[
                    "low"
                ]
                <= zone_high
                for candle in later
            )

            inside = (
                zone_low
                <= current_price
                <= zone_high
            )

            distance = (
                _distance_to_zone(
                    current_price,
                    zone_low,
                    zone_high,
                )
            )

            near = (
                not inside
                and abs(
                    distance
                )
                <= near_tolerance
            )

            if mitigated:
                relevance = (
                    "MITIGATED"
                )
            elif inside:
                relevance = (
                    "INSIDE"
                )
            elif near:
                relevance = (
                    "NEAR"
                )
            else:
                relevance = (
                    "FAR"
                )

            distance_percent = (
                abs(
                    distance
                )
                / current_price
                * 100.0
            )

            candidates.append(
                {
                    "detected": True,
                    "status": (
                        "MITIGATED"
                        if mitigated
                        else "ACTIVE"
                    ),
                    "direction": (
                        "BULLISH"
                    ),
                    "zone_type": (
                        "DEMAND"
                    ),
                    "zone_high": (
                        zone_high
                    ),
                    "zone_low": (
                        zone_low
                    ),
                    "candle_index": (
                        base_index
                    ),
                    "impulse_index": (
                        impulse_index
                    ),
                    "impulse_strength": (
                        rounded_strength
                    ),
                    "current_price": (
                        current_price
                    ),
                    "price_inside_zone": (
                        inside
                    ),
                    "price_near_zone": (
                        near
                    ),
                    "near_tolerance": float(
                        near_tolerance
                    ),
                    "mitigated": (
                        mitigated
                    ),
                    "distance_to_zone": float(
                        distance
                    ),
                    "distance_percent": round(
                        distance_percent,
                        4,
                    ),
                    "relevance": (
                        relevance
                    ),
                }
            )

        if (
            (
                _bullish(
                    base
                )
                or _body(
                    base
                )
                <= average_body
                * 0.75
            )
            and _bearish(
                impulse
            )
        ):
            zone_high = float(
                base[
                    "high"
                ]
            )
            zone_low = float(
                min(
                    base[
                        "open"
                    ],
                    base[
                        "close"
                    ],
                )
            )

            if (
                zone_low <= 0.0
                or zone_high <= 0.0
                or zone_low > zone_high
            ):
                continue

            later = (
                resolved_candles[
                    impulse_index + 1:
                ]
            )

            mitigated = any(
                candle[
                    "high"
                ]
                >= zone_low
                for candle in later
            )

            inside = (
                zone_low
                <= current_price
                <= zone_high
            )

            distance = (
                _distance_to_zone(
                    current_price,
                    zone_low,
                    zone_high,
                )
            )

            near = (
                not inside
                and abs(
                    distance
                )
                <= near_tolerance
            )

            if mitigated:
                relevance = (
                    "MITIGATED"
                )
            elif inside:
                relevance = (
                    "INSIDE"
                )
            elif near:
                relevance = (
                    "NEAR"
                )
            else:
                relevance = (
                    "FAR"
                )

            distance_percent = (
                abs(
                    distance
                )
                / current_price
                * 100.0
            )

            candidates.append(
                {
                    "detected": True,
                    "status": (
                        "MITIGATED"
                        if mitigated
                        else "ACTIVE"
                    ),
                    "direction": (
                        "BEARISH"
                    ),
                    "zone_type": (
                        "SUPPLY"
                    ),
                    "zone_high": (
                        zone_high
                    ),
                    "zone_low": (
                        zone_low
                    ),
                    "candle_index": (
                        base_index
                    ),
                    "impulse_index": (
                        impulse_index
                    ),
                    "impulse_strength": (
                        rounded_strength
                    ),
                    "current_price": (
                        current_price
                    ),
                    "price_inside_zone": (
                        inside
                    ),
                    "price_near_zone": (
                        near
                    ),
                    "near_tolerance": float(
                        near_tolerance
                    ),
                    "mitigated": (
                        mitigated
                    ),
                    "distance_to_zone": float(
                        distance
                    ),
                    "distance_percent": round(
                        distance_percent,
                        4,
                    ),
                    "relevance": (
                        relevance
                    ),
                }
            )

    if not candidates:
        result = _default()
        result[
            "current_price"
        ] = current_price
        result[
            "near_tolerance"
        ] = float(
            near_tolerance
        )

        return result

    relevance_rank = {
        "INSIDE": 4,
        "NEAR": 3,
        "FAR": 2,
        "MITIGATED": 1,
        "NONE": 0,
    }

    candidates.sort(
        key=lambda item: (
            relevance_rank.get(
                str(
                    item[
                        "relevance"
                    ]
                ),
                0,
            ),
            float(
                item[
                    "impulse_strength"
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
    "MAXIMUM_CANDLES",
    "MAXIMUM_LOOKBACK",
    "MAXIMUM_ZONE_AGE",
    "MINIMUM_CANDLES",
    "detect_supply_demand",
]