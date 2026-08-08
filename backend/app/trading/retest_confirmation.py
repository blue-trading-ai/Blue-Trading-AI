"""Retest and rejection confirmation engine for Blue-Trading-AI.

Candles must be ordered from oldest to newest and contain open, high, low, close.
This module confirms entry timing only. It must never bypass market-structure,
confidence, alignment, or risk-management safety rules.
"""

from __future__ import annotations

import math
from typing import Any, Final, Mapping


MINIMUM_CANDLES: Final[int] = 2
MAXIMUM_CANDLES: Final[int] = 100_000
MAXIMUM_LOOKBACK: Final[int] = 500
MAXIMUM_CONFIRMATION_AGE: Final[int] = 100
MAXIMUM_DISTANCE_ATR: Final[float] = 10.0
MAXIMUM_ZONES: Final[int] = 32
MAXIMUM_REASON_ITEMS: Final[int] = 10
MAXIMUM_TEXT_LENGTH: Final[int] = 128


def _default(
    status: str = "NO_RETEST",
) -> dict:
    return {
        "detected": False,
        "confirmed": False,
        "status": status,
        "direction": "NONE",
        "zone_type": "NONE",
        "zone_low": None,
        "zone_high": None,
        "zone_mid": None,
        "touch_index": None,
        "confirmation_index": None,
        "current_price": None,
        "rejection_type": "NONE",
        "rejection_strength": 0,
        "freshness_score": 0,
        "candles_since_confirmation": None,
        "max_confirmation_age": 2,
        "max_action_distance": None,
        "distance_to_zone": None,
        "distance_percent": None,
        "reason": [],
        "candidates_checked": 0,
        "rules": {
            "requires_zone_touch": True,
            "requires_directional_rejection": True,
            "requires_fresh_confirmation": True,
            "requires_actionable_distance": True,
            "can_bypass_structure_gate": False,
            "can_bypass_minimum_confidence": False,
            "can_bypass_market_alignment": False,
        },
    }


def _safe_bool(
    value: Any,
    *,
    default: bool = False,
) -> bool:
    if isinstance(value, bool):
        return value

    if value is None:
        return default

    if isinstance(value, (int, float)):
        try:
            number = float(value)
        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            return default

        if not math.isfinite(number):
            return default

        if number == 1.0:
            return True

        if number == 0.0:
            return False

        return default

    if isinstance(value, str):
        text = value.strip().lower()

        if text in {
            "true",
            "1",
            "yes",
            "y",
            "on",
        }:
            return True

        if text in {
            "false",
            "0",
            "no",
            "n",
            "off",
            "",
            "none",
            "null",
        }:
            return False

    return default


def _number(
    value: Any,
    *,
    positive: bool = False,
) -> float | None:
    if isinstance(value, bool):
        return None

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

    if positive and resolved <= 0.0:
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


def _normalise_non_negative_int(
    value: Any,
    *,
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
        0 <= resolved <= maximum
    ):
        return None

    return resolved


def _normalise_non_negative_float(
    value: Any,
    *,
    maximum: float,
) -> float | None:
    resolved = _number(value)

    if resolved is None:
        return None

    if not (
        0.0 <= resolved <= maximum
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
        value = _number(
            candle.get(field),
            positive=True,
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

    if (
        len(candles) < MINIMUM_CANDLES
        or len(candles) > MAXIMUM_CANDLES
    ):
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


def _normalise_zone(
    low: Any,
    high: Any,
) -> tuple[float, float] | None:
    low_value = _number(
        low,
        positive=True,
    )
    high_value = _number(
        high,
        positive=True,
    )

    if (
        low_value is None
        or high_value is None
    ):
        return None

    zone_low = min(
        low_value,
        high_value,
    )
    zone_high = max(
        low_value,
        high_value,
    )

    if (
        zone_low <= 0.0
        or zone_high <= 0.0
        or not math.isfinite(zone_low)
        or not math.isfinite(zone_high)
    ):
        return None

    return (
        zone_low,
        zone_high,
    )


def _add_zone(
    zones: list[dict],
    *,
    zone_type: str,
    direction: str,
    low: Any,
    high: Any,
    active: bool = True,
    priority: int = 0,
) -> None:
    if len(zones) >= MAXIMUM_ZONES:
        return

    if not _safe_bool(
        active,
        default=False,
    ):
        return

    normalised = _normalise_zone(
        low,
        high,
    )

    if normalised is None:
        return

    resolved_direction = str(
        direction or "NONE"
    ).strip().upper()

    if resolved_direction not in {
        "BUY",
        "SELL",
    }:
        return

    resolved_type = str(
        zone_type or "NONE"
    ).strip().upper()[
        :MAXIMUM_TEXT_LENGTH
    ]

    if not resolved_type:
        return

    try:
        resolved_priority = int(priority)
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        resolved_priority = 0

    resolved_priority = max(
        0,
        min(
            1_000,
            resolved_priority,
        ),
    )

    zone_low, zone_high = normalised

    zones.append(
        {
            "zone_type": resolved_type,
            "direction": (
                resolved_direction
            ),
            "zone_low": zone_low,
            "zone_high": zone_high,
            "priority": (
                resolved_priority
            ),
        }
    )


def _candle_rejection(
    candle: dict,
    direction: str,
) -> tuple[bool, str, int]:
    resolved_candle = _normalise_candle(
        candle
    )

    if resolved_candle is None:
        return (
            False,
            "NONE",
            0,
        )

    resolved_direction = str(
        direction or "NONE"
    ).strip().upper()

    if resolved_direction not in {
        "BUY",
        "SELL",
    }:
        return (
            False,
            "NONE",
            0,
        )

    candle_range = (
        resolved_candle["high"]
        - resolved_candle["low"]
    )

    if (
        not math.isfinite(candle_range)
        or candle_range <= 0.0
    ):
        return (
            False,
            "NONE",
            0,
        )

    open_price = resolved_candle["open"]
    close_price = resolved_candle["close"]
    high_price = resolved_candle["high"]
    low_price = resolved_candle["low"]

    body = abs(
        close_price - open_price
    )
    upper_wick = max(
        0.0,
        high_price
        - max(
            open_price,
            close_price,
        ),
    )
    lower_wick = max(
        0.0,
        min(
            open_price,
            close_price,
        )
        - low_price,
    )

    close_position = (
        close_price - low_price
    ) / candle_range

    body_ratio = (
        body / candle_range
    )

    if not all(
        math.isfinite(value)
        for value in (
            body,
            upper_wick,
            lower_wick,
            close_position,
            body_ratio,
        )
    ):
        return (
            False,
            "NONE",
            0,
        )

    if resolved_direction == "BUY":
        bullish_close = (
            close_price > open_price
        )

        strong_close = (
            close_position >= 0.65
        )

        wick_rejection = (
            lower_wick
            >= max(
                body * 0.8,
                candle_range * 0.25,
            )
        )

        confirmed = (
            bullish_close
            and strong_close
            and (
                wick_rejection
                or body_ratio >= 0.55
            )
        )

        if not confirmed:
            return (
                False,
                "NONE",
                0,
            )

        rejection_type = (
            "BULLISH_WICK_REJECTION"
            if wick_rejection
            else "BULLISH_DISPLACEMENT"
        )

        strength = min(
            100,
            round(
                45
                + close_position * 25
                + min(
                    lower_wick
                    / candle_range,
                    0.5,
                )
                * 40
            ),
        )

        return (
            True,
            rejection_type,
            int(
                max(
                    0,
                    strength,
                )
            ),
        )

    bearish_close = (
        close_price < open_price
    )

    strong_close = (
        close_position <= 0.35
    )

    wick_rejection = (
        upper_wick
        >= max(
            body * 0.8,
            candle_range * 0.25,
        )
    )

    confirmed = (
        bearish_close
        and strong_close
        and (
            wick_rejection
            or body_ratio >= 0.55
        )
    )

    if not confirmed:
        return (
            False,
            "NONE",
            0,
        )

    rejection_type = (
        "BEARISH_WICK_REJECTION"
        if wick_rejection
        else "BEARISH_DISPLACEMENT"
    )

    strength = min(
        100,
        round(
            45
            + (
                1.0 - close_position
            )
            * 25
            + min(
                upper_wick
                / candle_range,
                0.5,
            )
            * 40
        ),
    )

    return (
        True,
        rejection_type,
        int(
            max(
                0,
                strength,
            )
        ),
    )


def _safe_mapping(
    value: Any,
) -> dict[str, Any]:
    if not isinstance(
        value,
        Mapping,
    ):
        return {}

    return dict(value)


def _upper(
    value: Any,
) -> str:
    return str(
        value or ""
    ).strip().upper()[
        :MAXIMUM_TEXT_LENGTH
    ]


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


def _distance_percent(
    distance: float,
    current_price: float,
) -> float | None:
    if (
        not math.isfinite(distance)
        or not math.isfinite(
            current_price
        )
        or current_price <= 0.0
    ):
        return None

    value = (
        abs(distance)
        / current_price
        * 100.0
    )

    if not math.isfinite(value):
        return None

    return round(
        value,
        4,
    )


def detect_retest_confirmation(
    candles: list,
    *,
    preferred_direction: str,
    atr: float | None = None,
    support: float | None = None,
    resistance: float | None = None,
    bos: dict | None = None,
    choch: dict | None = None,
    order_block: dict | None = None,
    fair_value_gap: dict | None = None,
    optimal_trade_entry: dict | None = None,
    supply_demand: dict | None = None,
    breaker_block: dict | None = None,
    mitigation_block: dict | None = None,
    lookback: int = 5,
    max_confirmation_age: int = 2,
    max_distance_atr: float = 0.15,
) -> dict:
    """Confirm a recent touch and directional rejection from a valid entry zone."""

    direction = str(
        preferred_direction
        or "NONE"
    ).strip().upper()

    if direction not in {
        "BUY",
        "SELL",
    }:
        return _default(
            "NO_DIRECTION"
        )

    resolved_candles = (
        _normalise_candles(
            candles
        )
    )

    if not resolved_candles:
        if isinstance(
            candles,
            (list, tuple),
        ) and len(candles) < MINIMUM_CANDLES:
            return _default(
                "INSUFFICIENT_DATA"
            )

        return _default(
            "INSUFFICIENT_OHLC_DATA"
        )

    resolved_lookback = (
        _normalise_positive_int(
            lookback,
            minimum=2,
            maximum=MAXIMUM_LOOKBACK,
        )
    )

    resolved_confirmation_age = (
        _normalise_non_negative_int(
            max_confirmation_age,
            maximum=MAXIMUM_CONFIRMATION_AGE,
        )
    )

    resolved_max_distance_atr = (
        _normalise_non_negative_float(
            max_distance_atr,
            maximum=MAXIMUM_DISTANCE_ATR,
        )
    )

    if (
        resolved_lookback is None
        or resolved_confirmation_age
        is None
        or resolved_max_distance_atr
        is None
    ):
        return _default(
            "INVALID_CONFIGURATION"
        )

    current_price = float(
        resolved_candles[
            -1
        ][
            "close"
        ]
    )

    atr_value = _number(
        atr,
        positive=True,
    )

    tolerance = max(
        (
            atr_value * 0.15
            if atr_value is not None
            else 0.0
        ),
        current_price * 0.0004,
    )

    max_action_distance = max(
        (
            atr_value
            * resolved_max_distance_atr
            if atr_value is not None
            else 0.0
        ),
        current_price * 0.0004,
    )

    if (
        not math.isfinite(tolerance)
        or tolerance < 0.0
        or not math.isfinite(
            max_action_distance
        )
        or max_action_distance < 0.0
    ):
        return _default(
            "INVALID_CONFIGURATION"
        )

    order_block = _safe_mapping(
        order_block
    )
    fair_value_gap = _safe_mapping(
        fair_value_gap
    )
    optimal_trade_entry = (
        _safe_mapping(
            optimal_trade_entry
        )
    )
    supply_demand = _safe_mapping(
        supply_demand
    )
    breaker_block = _safe_mapping(
        breaker_block
    )
    mitigation_block = _safe_mapping(
        mitigation_block
    )
    bos = _safe_mapping(bos)
    choch = _safe_mapping(choch)

    zones: list[dict] = []

    if direction == "BUY":
        _add_zone(
            zones,
            zone_type="BULLISH_OTE",
            direction=direction,
            low=optimal_trade_entry.get(
                "ote_zone_low"
            ),
            high=optimal_trade_entry.get(
                "ote_zone_high"
            ),
            active=(
                _upper(
                    optimal_trade_entry.get(
                        "direction"
                    )
                )
                == "BULLISH_OTE"
            ),
            priority=70,
        )

        _add_zone(
            zones,
            zone_type="DEMAND",
            direction=direction,
            low=supply_demand.get(
                "zone_low"
            ),
            high=supply_demand.get(
                "zone_high"
            ),
            active=(
                _upper(
                    supply_demand.get(
                        "direction"
                    )
                )
                == "BULLISH"
                and _upper(
                    supply_demand.get(
                        "status"
                    )
                )
                == "ACTIVE"
                and not _safe_bool(
                    supply_demand.get(
                        "mitigated",
                        False,
                    )
                )
            ),
            priority=75,
        )

        _add_zone(
            zones,
            zone_type=(
                "BULLISH_ORDER_BLOCK"
            ),
            direction=direction,
            low=order_block.get(
                "zone_low"
            ),
            high=order_block.get(
                "zone_high"
            ),
            active=(
                _upper(
                    order_block.get(
                        "direction"
                    )
                )
                == "BULLISH_ORDER_BLOCK"
                and _upper(
                    order_block.get(
                        "status"
                    )
                )
                == "ACTIVE"
                and not _safe_bool(
                    order_block.get(
                        "mitigated",
                        False,
                    )
                )
            ),
            priority=90,
        )

        _add_zone(
            zones,
            zone_type="BULLISH_FVG",
            direction=direction,
            low=fair_value_gap.get(
                "zone_low"
            ),
            high=fair_value_gap.get(
                "zone_high"
            ),
            active=(
                _upper(
                    fair_value_gap.get(
                        "direction"
                    )
                )
                == "BULLISH_FVG"
                and _upper(
                    fair_value_gap.get(
                        "status"
                    )
                )
                == "ACTIVE"
                and not _safe_bool(
                    fair_value_gap.get(
                        "filled",
                        False,
                    )
                )
            ),
            priority=60,
        )

        _add_zone(
            zones,
            zone_type=(
                "BULLISH_BREAKER"
            ),
            direction=direction,
            low=breaker_block.get(
                "zone_low"
            ),
            high=breaker_block.get(
                "zone_high"
            ),
            active=(
                _upper(
                    breaker_block.get(
                        "direction"
                    )
                )
                == "BULLISH"
                and _upper(
                    breaker_block.get(
                        "status"
                    )
                )
                in {
                    "DETECTED",
                    "ACTIVE",
                }
                and not _safe_bool(
                    breaker_block.get(
                        "mitigated",
                        False,
                    )
                )
            ),
            priority=85,
        )

        _add_zone(
            zones,
            zone_type=(
                "BULLISH_MITIGATION"
            ),
            direction=direction,
            low=mitigation_block.get(
                "zone_low"
            ),
            high=mitigation_block.get(
                "zone_high"
            ),
            active=(
                _upper(
                    mitigation_block.get(
                        "direction"
                    )
                )
                == "BULLISH"
                and _upper(
                    mitigation_block.get(
                        "status"
                    )
                )
                in {
                    "DETECTED",
                    "ACTIVE",
                }
                and not _safe_bool(
                    mitigation_block.get(
                        "mitigated",
                        False,
                    )
                )
            ),
            priority=80,
        )

        support_value = _number(
            support,
            positive=True,
        )

        if support_value is not None:
            _add_zone(
                zones,
                zone_type="SUPPORT",
                direction=direction,
                low=max(
                    support_value
                    - tolerance,
                    support_value
                    * 0.000001,
                ),
                high=(
                    support_value
                    + tolerance
                ),
                priority=50,
            )

        bos_level = _number(
            bos.get("level"),
            positive=True,
        )

        if (
            _upper(
                bos.get(
                    "direction"
                )
            )
            == "BULLISH_BOS"
            and bos_level is not None
        ):
            _add_zone(
                zones,
                zone_type=(
                    "BULLISH_BOS_RETEST"
                ),
                direction=direction,
                low=max(
                    bos_level
                    - tolerance,
                    bos_level
                    * 0.000001,
                ),
                high=(
                    bos_level
                    + tolerance
                ),
                priority=100,
            )

        choch_level = _number(
            choch.get("level"),
            positive=True,
        )

        if (
            _upper(
                choch.get(
                    "direction"
                )
            )
            == "BULLISH_CHOCH"
            and choch_level is not None
        ):
            _add_zone(
                zones,
                zone_type=(
                    "BULLISH_CHOCH_RETEST"
                ),
                direction=direction,
                low=max(
                    choch_level
                    - tolerance,
                    choch_level
                    * 0.000001,
                ),
                high=(
                    choch_level
                    + tolerance
                ),
                priority=95,
            )

    else:
        _add_zone(
            zones,
            zone_type="BEARISH_OTE",
            direction=direction,
            low=optimal_trade_entry.get(
                "ote_zone_low"
            ),
            high=optimal_trade_entry.get(
                "ote_zone_high"
            ),
            active=(
                _upper(
                    optimal_trade_entry.get(
                        "direction"
                    )
                )
                == "BEARISH_OTE"
            ),
            priority=70,
        )

        _add_zone(
            zones,
            zone_type="SUPPLY",
            direction=direction,
            low=supply_demand.get(
                "zone_low"
            ),
            high=supply_demand.get(
                "zone_high"
            ),
            active=(
                _upper(
                    supply_demand.get(
                        "direction"
                    )
                )
                == "BEARISH"
                and _upper(
                    supply_demand.get(
                        "status"
                    )
                )
                == "ACTIVE"
                and not _safe_bool(
                    supply_demand.get(
                        "mitigated",
                        False,
                    )
                )
            ),
            priority=75,
        )

        _add_zone(
            zones,
            zone_type=(
                "BEARISH_ORDER_BLOCK"
            ),
            direction=direction,
            low=order_block.get(
                "zone_low"
            ),
            high=order_block.get(
                "zone_high"
            ),
            active=(
                _upper(
                    order_block.get(
                        "direction"
                    )
                )
                == "BEARISH_ORDER_BLOCK"
                and _upper(
                    order_block.get(
                        "status"
                    )
                )
                == "ACTIVE"
                and not _safe_bool(
                    order_block.get(
                        "mitigated",
                        False,
                    )
                )
            ),
            priority=90,
        )

        _add_zone(
            zones,
            zone_type="BEARISH_FVG",
            direction=direction,
            low=fair_value_gap.get(
                "zone_low"
            ),
            high=fair_value_gap.get(
                "zone_high"
            ),
            active=(
                _upper(
                    fair_value_gap.get(
                        "direction"
                    )
                )
                == "BEARISH_FVG"
                and _upper(
                    fair_value_gap.get(
                        "status"
                    )
                )
                == "ACTIVE"
                and not _safe_bool(
                    fair_value_gap.get(
                        "filled",
                        False,
                    )
                )
            ),
            priority=60,
        )

        _add_zone(
            zones,
            zone_type=(
                "BEARISH_BREAKER"
            ),
            direction=direction,
            low=breaker_block.get(
                "zone_low"
            ),
            high=breaker_block.get(
                "zone_high"
            ),
            active=(
                _upper(
                    breaker_block.get(
                        "direction"
                    )
                )
                == "BEARISH"
                and _upper(
                    breaker_block.get(
                        "status"
                    )
                )
                in {
                    "DETECTED",
                    "ACTIVE",
                }
                and not _safe_bool(
                    breaker_block.get(
                        "mitigated",
                        False,
                    )
                )
            ),
            priority=85,
        )

        _add_zone(
            zones,
            zone_type=(
                "BEARISH_MITIGATION"
            ),
            direction=direction,
            low=mitigation_block.get(
                "zone_low"
            ),
            high=mitigation_block.get(
                "zone_high"
            ),
            active=(
                _upper(
                    mitigation_block.get(
                        "direction"
                    )
                )
                == "BEARISH"
                and _upper(
                    mitigation_block.get(
                        "status"
                    )
                )
                in {
                    "DETECTED",
                    "ACTIVE",
                }
                and not _safe_bool(
                    mitigation_block.get(
                        "mitigated",
                        False,
                    )
                )
            ),
            priority=80,
        )

        resistance_value = _number(
            resistance,
            positive=True,
        )

        if resistance_value is not None:
            _add_zone(
                zones,
                zone_type="RESISTANCE",
                direction=direction,
                low=max(
                    resistance_value
                    - tolerance,
                    resistance_value
                    * 0.000001,
                ),
                high=(
                    resistance_value
                    + tolerance
                ),
                priority=50,
            )

        bos_level = _number(
            bos.get("level"),
            positive=True,
        )

        if (
            _upper(
                bos.get(
                    "direction"
                )
            )
            == "BEARISH_BOS"
            and bos_level is not None
        ):
            _add_zone(
                zones,
                zone_type=(
                    "BEARISH_BOS_RETEST"
                ),
                direction=direction,
                low=max(
                    bos_level
                    - tolerance,
                    bos_level
                    * 0.000001,
                ),
                high=(
                    bos_level
                    + tolerance
                ),
                priority=100,
            )

        choch_level = _number(
            choch.get("level"),
            positive=True,
        )

        if (
            _upper(
                choch.get(
                    "direction"
                )
            )
            == "BEARISH_CHOCH"
            and choch_level is not None
        ):
            _add_zone(
                zones,
                zone_type=(
                    "BEARISH_CHOCH_RETEST"
                ),
                direction=direction,
                low=max(
                    choch_level
                    - tolerance,
                    choch_level
                    * 0.000001,
                ),
                high=(
                    choch_level
                    + tolerance
                ),
                priority=95,
            )

    result = _default(
        "WAITING_FOR_RETEST"
    )

    result["direction"] = direction
    result["current_price"] = (
        current_price
    )
    result["candidates_checked"] = (
        len(zones)
    )
    result["max_confirmation_age"] = (
        resolved_confirmation_age
    )
    result["max_action_distance"] = round(
        max_action_distance,
        8,
    )

    if not zones:
        result["status"] = (
            "NO_VALID_RETEST_ZONE"
        )
        result["reason"] = [
            "No active entry zone is available for retest confirmation"
        ]
        return result

    start_index = max(
        0,
        len(resolved_candles)
        - resolved_lookback,
    )

    matches: list[dict] = []

    for zone in zones:
        expanded_low = max(
            zone["zone_low"]
            - tolerance,
            zone["zone_low"]
            * 0.000001,
        )
        expanded_high = (
            zone["zone_high"]
            + tolerance
        )

        if (
            expanded_low <= 0.0
            or expanded_low
            > expanded_high
        ):
            continue

        for index in range(
            start_index,
            len(resolved_candles),
        ):
            candle = resolved_candles[
                index
            ]

            touched = (
                candle["low"]
                <= expanded_high
                and candle["high"]
                >= expanded_low
            )

            if not touched:
                continue

            (
                confirmed,
                rejection_type,
                rejection_strength,
            ) = _candle_rejection(
                candle,
                direction,
            )

            if not confirmed:
                continue

            zone_mid = (
                zone["zone_low"]
                + zone["zone_high"]
            ) / 2.0

            if (
                not math.isfinite(zone_mid)
                or zone_mid <= 0.0
            ):
                continue

            correct_close = (
                candle["close"] >= zone_mid
                if direction == "BUY"
                else candle["close"] <= zone_mid
            )

            if not correct_close:
                continue

            matches.append(
                {
                    **zone,
                    "touch_index": index,
                    "confirmation_index": index,
                    "zone_mid": zone_mid,
                    "rejection_type": (
                        rejection_type
                    ),
                    "rejection_strength": (
                        rejection_strength
                    ),
                    "candles_since_confirmation": (
                        len(resolved_candles)
                        - 1
                        - index
                    ),
                }
            )

    if not matches:
        nearest = min(
            zones,
            key=lambda zone: (
                0.0
                if (
                    zone["zone_low"]
                    <= current_price
                    <= zone["zone_high"]
                )
                else min(
                    abs(
                        current_price
                        - zone["zone_low"]
                    ),
                    abs(
                        current_price
                        - zone["zone_high"]
                    ),
                )
            ),
        )

        distance = _distance_to_zone(
            current_price,
            nearest["zone_low"],
            nearest["zone_high"],
        )

        distance_percent = (
            _distance_percent(
                distance,
                current_price,
            )
        )

        result.update(
            {
                "zone_type": (
                    nearest[
                        "zone_type"
                    ]
                ),
                "zone_low": (
                    nearest[
                        "zone_low"
                    ]
                ),
                "zone_high": (
                    nearest[
                        "zone_high"
                    ]
                ),
                "zone_mid": (
                    (
                        nearest[
                            "zone_low"
                        ]
                        + nearest[
                            "zone_high"
                        ]
                    )
                    / 2.0
                ),
                "distance_to_zone": round(
                    distance,
                    8,
                ),
                "distance_percent": (
                    distance_percent
                ),
                "reason": [
                    (
                        f"Waiting for {direction} retest and rejection at "
                        f"{nearest['zone_type']}"
                    )[:300]
                ],
            }
        )

        return result

    fresh_matches = [
        item
        for item in matches
        if (
            item[
                "candles_since_confirmation"
            ]
            <= resolved_confirmation_age
        )
    ]

    if not fresh_matches:
        newest = max(
            matches,
            key=lambda item: (
                item[
                    "confirmation_index"
                ]
            ),
        )

        age = int(
            newest[
                "candles_since_confirmation"
            ]
        )

        result.update(
            {
                "detected": True,
                "confirmed": False,
                "status": "EXPIRED",
                "zone_type": (
                    newest["zone_type"]
                ),
                "zone_low": (
                    newest["zone_low"]
                ),
                "zone_high": (
                    newest["zone_high"]
                ),
                "zone_mid": (
                    newest["zone_mid"]
                ),
                "touch_index": (
                    newest["touch_index"]
                ),
                "confirmation_index": (
                    newest[
                        "confirmation_index"
                    ]
                ),
                "rejection_type": (
                    newest[
                        "rejection_type"
                    ]
                ),
                "rejection_strength": (
                    newest[
                        "rejection_strength"
                    ]
                ),
                "candles_since_confirmation": (
                    age
                ),
                "freshness_score": 0,
                "reason": [
                    (
                        f"{direction} retest expired: confirmation is "
                        f"{age} candles old"
                    )[:300]
                ],
            }
        )

        return result

    fresh_matches.sort(
        key=lambda item: (
            int(item["priority"]),
            -int(
                item[
                    "candles_since_confirmation"
                ]
            ),
            int(
                item[
                    "rejection_strength"
                ]
            ),
            int(
                item[
                    "confirmation_index"
                ]
            ),
        ),
        reverse=True,
    )

    best = fresh_matches[0]

    distance = _distance_to_zone(
        current_price,
        best["zone_low"],
        best["zone_high"],
    )

    age = int(
        best[
            "candles_since_confirmation"
        ]
    )

    freshness_score = (
        100
        if age == 0
        else 90
        if age == 1
        else 75
        if age == 2
        else max(
            0,
            75
            - (
                age - 2
            )
            * 15,
        )
    )

    if abs(distance) > max_action_distance:
        result.update(
            {
                "detected": True,
                "confirmed": False,
                "status": (
                    "EXPIRED_DISTANCE"
                ),
                "zone_type": (
                    best["zone_type"]
                ),
                "zone_low": (
                    best["zone_low"]
                ),
                "zone_high": (
                    best["zone_high"]
                ),
                "zone_mid": (
                    best["zone_mid"]
                ),
                "touch_index": (
                    best["touch_index"]
                ),
                "confirmation_index": (
                    best[
                        "confirmation_index"
                    ]
                ),
                "rejection_type": (
                    best[
                        "rejection_type"
                    ]
                ),
                "rejection_strength": (
                    best[
                        "rejection_strength"
                    ]
                ),
                "candles_since_confirmation": (
                    age
                ),
                "freshness_score": 0,
                "distance_to_zone": round(
                    distance,
                    8,
                ),
                "distance_percent": (
                    _distance_percent(
                        distance,
                        current_price,
                    )
                ),
                "reason": [
                    (
                        f"{direction} retest expired: price moved beyond "
                        "the actionable distance"
                    )[:300]
                ],
            }
        )

        return result

    result.update(
        {
            "detected": True,
            "confirmed": True,
            "status": "CONFIRMED",
            "zone_type": (
                best["zone_type"]
            ),
            "zone_low": (
                best["zone_low"]
            ),
            "zone_high": (
                best["zone_high"]
            ),
            "zone_mid": (
                best["zone_mid"]
            ),
            "touch_index": (
                best["touch_index"]
            ),
            "confirmation_index": (
                best[
                    "confirmation_index"
                ]
            ),
            "rejection_type": (
                best[
                    "rejection_type"
                ]
            ),
            "rejection_strength": (
                best[
                    "rejection_strength"
                ]
            ),
            "candles_since_confirmation": (
                age
            ),
            "freshness_score": (
                freshness_score
            ),
            "distance_to_zone": round(
                distance,
                8,
            ),
            "distance_percent": (
                _distance_percent(
                    distance,
                    current_price,
                )
            ),
            "reason": [
                (
                    f"{direction} retest confirmed at {best['zone_type']}"
                )[:300],
                (
                    "Directional rejection confirmed: "
                    f"{best['rejection_type']}"
                )[:300],
                (
                    f"Retest freshness score: {freshness_score}"
                )[:300],
            ][
                :MAXIMUM_REASON_ITEMS
            ],
        }
    )

    return result


__all__ = [
    "MAXIMUM_CANDLES",
    "MAXIMUM_CONFIRMATION_AGE",
    "MAXIMUM_DISTANCE_ATR",
    "MAXIMUM_LOOKBACK",
    "detect_retest_confirmation",
]