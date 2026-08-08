"""Market regime classification for Blue Trading AI.

The module classifies the current environment without creating directional
BUY/SELL confirmations. Its score adjustment is intentionally capped between
-5 and +5 and should only be applied to an already preferred direction.
"""

from __future__ import annotations

import math
from typing import Any, Final, Iterable, Mapping


REGIME_SCORE_POLICY: Final[dict[str, int]] = {
    "TRENDING": 5,
    "BREAKOUT": 4,
    "REVERSAL": 3,
    "RANGING": 0,
    "VOLATILE": -3,
    "LOW_VOLATILITY": -5,
}

MINIMUM_PRICES: Final[int] = 10
MAXIMUM_PRICES: Final[int] = 100_000
MAXIMUM_CANDLES: Final[int] = 100_000
MAXIMUM_MTF_ENTRIES: Final[int] = 16
MAXIMUM_REASON_ITEMS: Final[int] = 20
MAXIMUM_TEXT_LENGTH: Final[int] = 128


def _upper(
    value: Any,
    default: str = "NONE",
) -> str:
    text = str(
        value
        if value is not None
        else default
    ).strip().upper()

    if not text:
        text = default

    return text[:MAXIMUM_TEXT_LENGTH]


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


def _safe_float(
    value: Any,
    *,
    default: float = 0.0,
) -> float:
    try:
        resolved = float(value)
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return default

    if not math.isfinite(resolved):
        return default

    return resolved


def _positive_float_or_none(
    value: Any,
) -> float | None:
    resolved = _safe_float(
        value,
        default=float("nan"),
    )

    if (
        not math.isfinite(resolved)
        or resolved <= 0.0
    ):
        return None

    return resolved


def _normalise_prices(
    prices: Any,
) -> list[float]:
    if not isinstance(
        prices,
        (list, tuple),
    ):
        return []

    if (
        len(prices) < MINIMUM_PRICES
        or len(prices) > MAXIMUM_PRICES
    ):
        return []

    output: list[float] = []

    for value in prices:
        number = _positive_float_or_none(
            value
        )

        if number is None:
            return []

        output.append(number)

    return output


def _is_detected(
    data: Mapping[str, Any] | None,
) -> bool:
    return bool(
        isinstance(data, Mapping)
        and _safe_bool(
            data.get(
                "detected",
                False,
            )
        )
    )


def _trend_vote(
    value: Any,
) -> int:
    resolved = _upper(value)

    if resolved in {
        "UPTREND",
        "BULLISH",
        "BUY",
        "BULLISH_BOS",
        "BULLISH_CHOCH",
    }:
        return 1

    if resolved in {
        "DOWNTREND",
        "BEARISH",
        "SELL",
        "BEARISH_BOS",
        "BEARISH_CHOCH",
    }:
        return -1

    return 0


def _extract_ranges(
    candles: Iterable[Any] | None,
) -> list[float]:
    ranges: list[float] = []

    if candles is None:
        return ranges

    if isinstance(
        candles,
        (str, bytes, bytearray),
    ):
        return ranges

    try:
        materialised = list(candles)
    except TypeError:
        return ranges

    if len(materialised) > MAXIMUM_CANDLES:
        materialised = materialised[
            -MAXIMUM_CANDLES:
        ]

    for candle in materialised[-20:]:
        if not isinstance(
            candle,
            Mapping,
        ):
            continue

        high = _positive_float_or_none(
            candle.get("high")
        )
        low = _positive_float_or_none(
            candle.get("low")
        )

        if (
            high is None
            or low is None
            or high < low
        ):
            continue

        candle_range = (
            high - low
        )

        if (
            math.isfinite(candle_range)
            and candle_range >= 0.0
        ):
            ranges.append(
                candle_range
            )

    return ranges


def _safe_mapping(
    value: Any,
) -> dict[str, Any]:
    if not isinstance(
        value,
        Mapping,
    ):
        return {}

    return dict(value)


def _insufficient_result(
    reason: str,
) -> dict:
    return {
        "detected": False,
        "status": "INSUFFICIENT_DATA",
        "regime": "UNKNOWN",
        "strength": 0,
        "confidence": 0,
        "confidence_adjustment": 0,
        "trade_allowed": False,
        "recommended_strategy": (
            "WAIT_FOR_DATA"
        ),
        "reason": [
            str(reason)[:300]
        ],
        "metrics": {},
        "rules": {
            "adds_directional_confirmation": False,
            "can_bypass_minimum_confidence": False,
            "can_bypass_entry_validation": False,
            "can_bypass_market_alignment": False,
        },
        "scoring_policy": (
            REGIME_SCORE_POLICY.copy()
        ),
    }


def analyze_market_regime(
    *,
    prices: list[float],
    candles: list | None = None,
    trend: str | None = None,
    ema: float | None = None,
    moving_average: float | None = None,
    market_structure: dict | None = None,
    bos: dict | None = None,
    choch: dict | None = None,
    liquidity_sweep: dict | None = None,
    candlestick_pattern: dict | None = None,
    atr_volatility: dict | None = None,
    trendline: dict | None = None,
    breakout: Any = None,
    multi_timeframe: dict | None = None,
) -> dict:
    """Classify the current market environment.

    The result is direction-neutral. ``confidence_adjustment`` changes only
    confidence quality; it must never be counted as a BUY/SELL confirmation.
    """

    resolved_prices = _normalise_prices(
        prices
    )

    if not resolved_prices:
        return _insufficient_result(
            "At least 10 valid prices are required"
        )

    current_price = resolved_prices[-1]
    recent = resolved_prices[-20:]

    recent_high = max(recent)
    recent_low = min(recent)

    range_size = max(
        recent_high - recent_low,
        0.0,
    )

    range_percent = (
        range_size
        / current_price
        * 100.0
    )

    if not math.isfinite(
        range_percent
    ):
        return _insufficient_result(
            "Market range calculation is invalid"
        )

    atr_data = _safe_mapping(
        atr_volatility
    )

    atr_type = _upper(
        atr_data.get(
            "volatility"
        ),
        "UNKNOWN",
    )

    atr_percent = max(
        0.0,
        _safe_float(
            atr_data.get(
                "atr_percent",
                0,
            ),
            default=0.0,
        ),
    )

    atr_too_low = (
        _safe_bool(
            atr_data.get(
                "too_low",
                False,
            )
        )
        or atr_type
        in {
            "LOW",
            "VERY_LOW",
            "LOW_VOLATILITY",
        }
    )

    atr_too_high = (
        _safe_bool(
            atr_data.get(
                "too_high",
                False,
            )
        )
        or atr_type
        in {
            "HIGH",
            "VERY_HIGH",
            "EXTREME",
        }
    )

    ranges = _extract_ranges(
        candles
    )

    range_expansion = 1.0

    if len(ranges) >= 6:
        baseline_values = ranges[:-3]
        latest_values = ranges[-3:]

        baseline = (
            sum(baseline_values)
            / len(baseline_values)
        )
        latest = (
            sum(latest_values)
            / len(latest_values)
        )

        if (
            math.isfinite(baseline)
            and baseline > 0.0
            and math.isfinite(latest)
        ):
            calculated_expansion = (
                latest / baseline
            )

            if (
                math.isfinite(
                    calculated_expansion
                )
                and calculated_expansion
                >= 0.0
            ):
                range_expansion = (
                    calculated_expansion
                )

    structure_data = _safe_mapping(
        market_structure
    )

    structure = _upper(
        structure_data.get(
            "structure"
        ),
        "RANGE",
    )

    trend_direction = _trend_vote(
        trend
    )

    structure_direction = _trend_vote(
        "BULLISH"
        if structure == "HH-HL"
        else "BEARISH"
        if structure == "LH-LL"
        else "NONE"
    )

    mtf = _safe_mapping(
        multi_timeframe
    )

    mtf_votes: list[int] = []

    for _, data in list(
        mtf.items()
    )[:MAXIMUM_MTF_ENTRIES]:
        if not isinstance(
            data,
            Mapping,
        ):
            continue

        mtf_votes.append(
            _trend_vote(
                data.get(
                    "trend"
                )
            )
        )

    bullish_mtf = sum(
        vote > 0
        for vote in mtf_votes
    )
    bearish_mtf = sum(
        vote < 0
        for vote in mtf_votes
    )

    mtf_direction = (
        1
        if bullish_mtf > bearish_mtf
        else -1
        if bearish_mtf > bullish_mtf
        else 0
    )

    mtf_agreement = max(
        bullish_mtf,
        bearish_mtf,
    )

    bos_data = _safe_mapping(bos)
    choch_data = _safe_mapping(choch)
    liquidity_data = _safe_mapping(
        liquidity_sweep
    )
    candle_data = _safe_mapping(
        candlestick_pattern
    )
    trendline_data = _safe_mapping(
        trendline
    )

    bos_detected = _is_detected(
        bos_data
    )
    choch_detected = _is_detected(
        choch_data
    )
    liquidity_detected = _is_detected(
        liquidity_data
    )

    candle_strength = max(
        0.0,
        min(
            100.0,
            _safe_float(
                candle_data.get(
                    "strength",
                    0,
                ),
                default=0.0,
            ),
        ),
    )

    candle_confirmed = (
        _is_detected(
            candle_data
        )
        and _upper(
            candle_data.get(
                "status"
            )
        )
        == "CONFIRMED"
        and candle_strength >= 65.0
    )

    trendline_broken = (
        _safe_bool(
            trendline_data.get(
                "break_detected",
                False,
            )
        )
        or _upper(
            trendline_data.get(
                "status"
            )
        )
        in {
            "BROKEN",
            "BROKEN_RETESTED",
        }
    )

    breakout_text = _upper(
        breakout
    )

    breakout_detected = (
        breakout_text
        not in {
            "NONE",
            "NO BREAKOUT",
            "NO_BREAKOUT",
            "FALSE",
            "0",
            "NULL",
            "",
        }
    )

    resolved_ema = _positive_float_or_none(
        ema
    )
    resolved_moving_average = (
        _positive_float_or_none(
            moving_average
        )
    )

    ema_aligned = False

    if (
        resolved_ema is not None
        and resolved_moving_average
        is not None
    ):
        if trend_direction > 0:
            ema_aligned = (
                resolved_ema
                > resolved_moving_average
                and current_price
                >= resolved_ema
            )

        elif trend_direction < 0:
            ema_aligned = (
                resolved_ema
                < resolved_moving_average
                and current_price
                <= resolved_ema
            )

    trend_votes = [
        trend_direction,
        structure_direction,
        mtf_direction,
    ]

    directional_votes = [
        vote
        for vote in trend_votes
        if vote != 0
    ]

    directional_sum = sum(
        directional_votes
    )

    majority_direction = (
        1
        if directional_sum > 0
        else -1
        if directional_sum < 0
        else 0
    )

    mtf_direction_consistent = (
        mtf_agreement >= 2
        and mtf_direction != 0
        and (
            trend_direction == 0
            or mtf_direction
            == trend_direction
        )
    )

    full_mtf_alignment = (
        bool(mtf_votes)
        and mtf_agreement
        == len(mtf_votes)
        and mtf_direction != 0
    )

    direction_consistent = bool(
        mtf_direction_consistent
        and (
            structure_direction
            in {
                0,
                mtf_direction,
            }
            or full_mtf_alignment
            or majority_direction
            == mtf_direction
        )
    )

    reversal_points = sum(
        [
            bos_detected,
            choch_detected,
            liquidity_detected,
            candle_confirmed,
        ]
    )

    breakout_points = sum(
        [
            breakout_detected,
            trendline_broken,
            bos_detected,
            range_expansion >= 1.20,
        ]
    )

    trending_points = 0

    if direction_consistent:
        trending_points += 2

    if ema_aligned:
        trending_points += 1

    if mtf_agreement >= 2:
        trending_points += 1

    if (
        structure_direction
        == mtf_direction
        and structure_direction != 0
    ):
        trending_points += 1

    reasons: list[str] = []

    if (
        atr_too_high
        or range_expansion >= 2.0
    ):
        regime = "VOLATILE"

        volatile_strength = (
            65
            + int(
                max(
                    0.0,
                    range_expansion - 1.0,
                )
                * 20
            )
        )

        strength = min(
            100,
            volatile_strength,
        )

        trade_allowed = True
        strategy = (
            "REDUCE_POSITION_SIZE_AND_WIDEN_SL"
        )

        reasons.append(
            "ATR or recent candle expansion indicates excessive volatility"
        )

    elif (
        atr_too_low
        or (
            atr_percent > 0.0
            and atr_percent < 0.08
        )
    ):
        regime = "LOW_VOLATILITY"
        strength = 80
        trade_allowed = False
        strategy = "NO_TRADE"

        reasons.append(
            "ATR indicates insufficient movement for reliable execution"
        )

    elif (
        reversal_points >= 3
        and (
            choch_detected
            or bos_detected
        )
    ):
        regime = "REVERSAL"
        strength = min(
            100,
            55
            + reversal_points * 10,
        )
        trade_allowed = True
        strategy = (
            "WAIT_FOR_REVERSAL_RETEST"
        )

        if bos_detected:
            reasons.append(
                "Break of Structure is detected"
            )

        if choch_detected:
            reasons.append(
                "Change of Character is detected"
            )

        if liquidity_detected:
            reasons.append(
                "Liquidity sweep supports reversal conditions"
            )

        if candle_confirmed:
            reasons.append(
                "Confirmed reversal candlestick is present"
            )

    elif breakout_points >= 3:
        regime = "BREAKOUT"
        strength = min(
            100,
            55
            + breakout_points * 10,
        )
        trade_allowed = True
        strategy = (
            "WAIT_FOR_BREAKOUT_RETEST"
        )

        if breakout_detected:
            reasons.append(
                "Price breakout is detected"
            )

        if trendline_broken:
            reasons.append(
                "Trendline break confirms market expansion"
            )

        if bos_detected:
            reasons.append(
                "BOS supports the breakout regime"
            )

        if range_expansion >= 1.20:
            reasons.append(
                "Recent candle ranges are expanding"
            )

    elif trending_points >= 3:
        regime = "TRENDING"
        strength = min(
            100,
            55
            + trending_points * 10,
        )
        trade_allowed = True

        strategy = (
            "TREND_FOLLOWING_WAIT_FOR_RETRACE"
            if breakout_points >= 2
            else "TREND_FOLLOWING"
        )

        if direction_consistent:
            reasons.append(
                "Current trend and multi-timeframe direction are consistent"
            )

        if (
            structure_direction
            not in {
                0,
                mtf_direction,
            }
            and full_mtf_alignment
        ):
            reasons.append(
                "Market structure is lagging the fully aligned multi-timeframe trend"
            )

        if ema_aligned:
            reasons.append(
                "Price, EMA, and moving average are aligned"
            )

        if mtf_agreement >= 2:
            reasons.append(
                "Multiple timeframes agree on direction"
            )

        if structure in {
            "HH-HL",
            "LH-LL",
        }:
            reasons.append(
                f"Directional market structure is {structure}"
            )

    else:
        regime = "RANGING"

        ranging_strength = int(
            70
            - min(
                range_percent,
                5.0,
            )
            * 4
        )

        strength = max(
            45,
            min(
                80,
                ranging_strength,
            ),
        )

        trade_allowed = True
        strategy = (
            "BUY_SUPPORT_SELL_RESISTANCE"
        )

        reasons.append(
            "Directional modules do not show sufficient trend agreement"
        )

        if (
            not bos_detected
            and not choch_detected
        ):
            reasons.append(
                "No confirmed BOS or CHoCH"
            )

        reasons.append(
            "Use range boundaries and wait for location confirmation"
        )

    strength = max(
        0,
        min(
            100,
            int(strength),
        ),
    )

    adjustment = int(
        REGIME_SCORE_POLICY.get(
            regime,
            0,
        )
    )

    adjustment = max(
        -5,
        min(
            5,
            adjustment,
        ),
    )

    confidence = strength

    reasons = [
        str(reason)[:300]
        for reason in reasons[
            :MAXIMUM_REASON_ITEMS
        ]
    ]

    return {
        "detected": True,
        "status": "ACTIVE",
        "regime": regime,
        "strength": strength,
        "confidence": confidence,
        "confidence_adjustment": (
            adjustment
        ),
        "trade_allowed": bool(
            trade_allowed
        ),
        "recommended_strategy": (
            strategy
        ),
        "reason": reasons,
        "metrics": {
            "atr_volatility": (
                atr_type
            ),
            "atr_percent": round(
                atr_percent,
                4,
            ),
            "recent_range_percent": round(
                range_percent,
                4,
            ),
            "candle_range_expansion": round(
                range_expansion,
                3,
            ),
            "trend_points": (
                trending_points
            ),
            "breakout_points": (
                breakout_points
            ),
            "reversal_points": (
                reversal_points
            ),
            "mtf_agreement_count": (
                mtf_agreement
            ),
            "mtf_total_count": (
                len(mtf_votes)
            ),
            "mtf_direction": (
                "BULLISH"
                if mtf_direction > 0
                else "BEARISH"
                if mtf_direction < 0
                else "NEUTRAL"
            ),
            "full_mtf_alignment": (
                bool(
                    full_mtf_alignment
                )
            ),
            "direction_consistent": (
                bool(
                    direction_consistent
                )
            ),
            "ema_aligned": bool(
                ema_aligned
            ),
        },
        "rules": {
            "adds_directional_confirmation": False,
            "can_bypass_minimum_confidence": False,
            "can_bypass_entry_validation": False,
            "can_bypass_market_alignment": False,
        },
        "scoring_policy": (
            REGIME_SCORE_POLICY.copy()
        ),
    }


__all__ = [
    "MAXIMUM_CANDLES",
    "MAXIMUM_MTF_ENTRIES",
    "MAXIMUM_PRICES",
    "MINIMUM_PRICES",
    "REGIME_SCORE_POLICY",
    "analyze_market_regime",
]