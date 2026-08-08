from __future__ import annotations

import math
from typing import Any, Final


BUY: Final = "BUY"
SELL: Final = "SELL"
WAIT: Final = "WAIT"

BULLISH: Final = "BULLISH"
BEARISH: Final = "BEARISH"
NEUTRAL: Final = "NEUTRAL"

MINIMUM_ALIGNMENT_SCORE: Final = 75.0
MINIMUM_HIGHER_TIMEFRAME_SCORE: Final = 70.0
MINIMUM_ALIGNED_TIMEFRAMES: Final = 3
MAXIMUM_TIMEFRAME_SCORE: Final = 100.0
MAXIMUM_TIMEFRAME_COUNT: Final = 8

SUPPORTED_TIMEFRAMES = [
    "MN",
    "W1",
    "D1",
    "H4",
    "H1",
    "M30",
    "M15",
    "M5",
]

TIMEFRAME_WEIGHTS = {
    "MN": 1.5,
    "W1": 2.0,
    "D1": 3.0,
    "H4": 4.0,
    "H1": 3.5,
    "M30": 2.5,
    "M15": 2.0,
    "M5": 1.0,
}

HIGHER_TIMEFRAMES = [
    "MN",
    "W1",
    "D1",
    "H4",
]

LOWER_TIMEFRAMES = [
    "H1",
    "M30",
    "M15",
    "M5",
]


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """Safely convert a value to a finite float."""

    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return float(default)

    if not math.isfinite(number):
        return float(default)

    return number


def safe_bool(
    value: Any,
) -> bool:
    """Safely convert common boolean representations."""

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value == 1:
            return True
        if value == 0:
            return False
        return False

    if isinstance(value, str):
        normalized = value.strip().lower()

        if normalized in {
            "true",
            "1",
            "yes",
            "approved",
            "confirmed",
            "pass",
            "passed",
        }:
            return True

        if normalized in {
            "false",
            "0",
            "no",
            "rejected",
            "unconfirmed",
            "fail",
            "failed",
        }:
            return False

    return False


def clamp(
    value: Any,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    """Restrict a numeric value between minimum and maximum."""

    safe_minimum = safe_float(minimum, 0.0)
    safe_maximum = safe_float(maximum, 100.0)

    if safe_minimum > safe_maximum:
        safe_minimum, safe_maximum = (
            safe_maximum,
            safe_minimum,
        )

    number = safe_float(
        value,
        safe_minimum,
    )

    return max(
        safe_minimum,
        min(
            number,
            safe_maximum,
        ),
    )


def normalize_direction(
    value: Any,
) -> str:
    """
    Normalizes different directional labels.
    """

    direction = str(
        value or NEUTRAL
    ).strip().upper()

    if direction in {
        BUY,
        BULLISH,
        "LONG",
        "UP",
    }:
        return BUY

    if direction in {
        SELL,
        BEARISH,
        "SHORT",
        "DOWN",
    }:
        return SELL

    return WAIT


def normalize_zone(
    value: Any,
) -> str:
    """
    Normalizes premium and discount zones.
    """

    zone = str(
        value or "EQUILIBRIUM"
    ).strip().upper()

    if zone == "PREMIUM":
        return "PREMIUM"

    if zone == "DISCOUNT":
        return "DISCOUNT"

    return "EQUILIBRIUM"


def calculate_grade(
    score: Any,
) -> str:
    """
    Converts alignment score to grade.
    """

    value = clamp(score)

    if value >= 92.0:
        return "A+"

    if value >= 85.0:
        return "A"

    if value >= 75.0:
        return "B"

    if value >= 65.0:
        return "C"

    return "D"


def calculate_strength(
    score: Any,
) -> str:
    """
    Converts alignment score to strength.
    """

    value = clamp(score)

    if value >= 90.0:
        return "VERY_STRONG"

    if value >= 80.0:
        return "STRONG"

    if value >= 70.0:
        return "MODERATE"

    return "WEAK"


def calculate_timeframe_score(
    direction: Any,
    trend_strength: Any,
    momentum_score: Any,
    bos_detected: bool,
    choch_detected: bool,
    institutional_bias: Any,
    premium_discount_zone: Any,
) -> dict[str, Any]:
    """
    Calculates the quality score for one timeframe.
    """

    normalized_direction = normalize_direction(
        direction
    )

    normalized_institutional_bias = (
        normalize_direction(
            institutional_bias
        )
    )

    normalized_zone = normalize_zone(
        premium_discount_zone
    )

    trend_value = clamp(
        trend_strength
    )

    momentum_value = clamp(
        momentum_score
    )

    score = 0.0
    reasons: list[str] = []
    warnings: list[str] = []

    if normalized_direction in {
        BUY,
        SELL,
    }:
        score += trend_value * 0.45
        score += momentum_value * 0.25

        reasons.append(
            "Directional trend is available."
        )
    else:
        warnings.append(
            "Timeframe direction is neutral."
        )

    if safe_bool(bos_detected):
        score += 10.0
        reasons.append(
            "Break of Structure detected."
        )

    if safe_bool(choch_detected):
        score += 8.0
        reasons.append(
            "Change of Character detected."
        )

    institutional_alignment = (
        normalized_direction
        == normalized_institutional_bias
        and normalized_direction in {
            BUY,
            SELL,
        }
    )

    if institutional_alignment:
        score += 12.0
        reasons.append(
            "Institutional bias matches "
            "the timeframe direction."
        )
    elif (
        normalized_institutional_bias
        != WAIT
    ):
        warnings.append(
            "Institutional bias conflicts "
            "with timeframe direction."
        )

    zone_alignment = False

    if (
        normalized_direction == BUY
        and normalized_zone == "DISCOUNT"
    ):
        score += 5.0
        zone_alignment = True

        reasons.append(
            "Bullish direction is located "
            "in the discount zone."
        )

    elif (
        normalized_direction == SELL
        and normalized_zone == "PREMIUM"
    ):
        score += 5.0
        zone_alignment = True

        reasons.append(
            "Bearish direction is located "
            "in the premium zone."
        )

    elif normalized_zone == "EQUILIBRIUM":
        warnings.append(
            "Price is near equilibrium."
        )

    else:
        warnings.append(
            "Premium or discount location does "
            "not support the timeframe direction."
        )

    score = clamp(score)

    confirmed = (
        normalized_direction in {
            BUY,
            SELL,
        }
        and score >= 60.0
    )

    return {
        "direction": normalized_direction,
        "trend_strength": round(
            trend_value,
            2,
        ),
        "momentum_score": round(
            momentum_value,
            2,
        ),
        "bos_detected": safe_bool(
            bos_detected
        ),
        "choch_detected": safe_bool(
            choch_detected
        ),
        "institutional_bias": (
            normalized_institutional_bias
        ),
        "institutional_alignment": (
            institutional_alignment
        ),
        "premium_discount_zone": (
            normalized_zone
        ),
        "zone_alignment": zone_alignment,
        "timeframe_score": round(
            score,
            2,
        ),
        "timeframe_strength": (
            calculate_strength(score)
        ),
        "confirmed": confirmed,
        "reasons": reasons,
        "warnings": warnings,
    }


def determine_dominant_direction(
    timeframe_results: dict[str, dict[str, Any]],
    selected_timeframes: list[str],
) -> dict[str, Any]:
    """
    Determines the weighted dominant direction.
    """

    buy_weight = 0.0
    sell_weight = 0.0
    neutral_weight = 0.0

    for timeframe in selected_timeframes:
        result = timeframe_results.get(
            timeframe
        )

        if not result:
            continue

        weight = TIMEFRAME_WEIGHTS.get(
            timeframe,
            1.0,
        )

        quality_multiplier = (
            clamp(
                result.get(
                    "timeframe_score",
                    0.0,
                )
            )
            / 100.0
        )

        weighted_value = (
            weight * quality_multiplier
        )

        result_direction = normalize_direction(
            result.get(
                "direction",
                WAIT,
            )
        )

        if result_direction == BUY:
            buy_weight += weighted_value

        elif result_direction == SELL:
            sell_weight += weighted_value

        else:
            neutral_weight += weight

    if buy_weight > sell_weight:
        dominant_direction = BUY

    elif sell_weight > buy_weight:
        dominant_direction = SELL

    else:
        dominant_direction = WAIT

    return {
        "dominant_direction": (
            dominant_direction
        ),
        "buy_weight": round(
            buy_weight,
            4,
        ),
        "sell_weight": round(
            sell_weight,
            4,
        ),
        "neutral_weight": round(
            neutral_weight,
            4,
        ),
    }


def evaluate_multi_timeframe_intelligence(
    timeframe_data: dict[str, dict[str, Any]],
    requested_direction: Any,
    execution_timeframe: str = "M15",
) -> dict[str, Any]:
    """
    Evaluates hierarchical multi-timeframe
    alignment for Blue-Trading-AI.

    This service provides market analysis and
    signal filtering only. It does not connect
    to brokers or execute trades.
    """

    normalized_requested_direction = (
        normalize_direction(
            requested_direction
        )
    )

    if not isinstance(
        timeframe_data,
        dict,
    ):
        timeframe_data = {}

    normalized_timeframe_data: dict[
        str,
        dict[str, Any],
    ] = {}

    for raw_timeframe, raw_data in list(
        timeframe_data.items()
    )[:MAXIMUM_TIMEFRAME_COUNT]:
        normalized_timeframe = str(
            raw_timeframe or ""
        ).strip().upper()

        if (
            normalized_timeframe
            not in SUPPORTED_TIMEFRAMES
            or not isinstance(
                raw_data,
                dict,
            )
        ):
            continue

        normalized_timeframe_data[
            normalized_timeframe
        ] = raw_data

    timeframe_data = normalized_timeframe_data

    normalized_execution_timeframe = str(
        execution_timeframe or "M15"
    ).strip().upper()

    if (
        normalized_execution_timeframe
        not in SUPPORTED_TIMEFRAMES
    ):
        normalized_execution_timeframe = "M15"

    timeframe_results: dict[
        str,
        dict[str, Any],
    ] = {}

    missing_timeframes: list[str] = []

    for timeframe in SUPPORTED_TIMEFRAMES:
        data = timeframe_data.get(
            timeframe
        )

        if not isinstance(
            data,
            dict,
        ) or not data:
            missing_timeframes.append(
                timeframe
            )
            continue

        timeframe_results[timeframe] = (
            calculate_timeframe_score(
                direction=data.get(
                    "direction",
                    WAIT,
                ),
                trend_strength=data.get(
                    "trend_strength",
                    0.0,
                ),
                momentum_score=data.get(
                    "momentum_score",
                    0.0,
                ),
                bos_detected=data.get(
                    "bos_detected",
                    False,
                ),
                choch_detected=data.get(
                    "choch_detected",
                    False,
                ),
                institutional_bias=data.get(
                    "institutional_bias",
                    WAIT,
                ),
                premium_discount_zone=data.get(
                    "premium_discount_zone",
                    "EQUILIBRIUM",
                ),
            )
        )

    available_timeframes = list(
        timeframe_results.keys()
    )

    higher_timeframes_available = [
        timeframe
        for timeframe in HIGHER_TIMEFRAMES
        if timeframe in timeframe_results
    ]

    lower_timeframes_available = [
        timeframe
        for timeframe in LOWER_TIMEFRAMES
        if timeframe in timeframe_results
    ]

    overall_direction_result = (
        determine_dominant_direction(
            timeframe_results=(
                timeframe_results
            ),
            selected_timeframes=(
                available_timeframes
            ),
        )
    )

    higher_direction_result = (
        determine_dominant_direction(
            timeframe_results=(
                timeframe_results
            ),
            selected_timeframes=(
                higher_timeframes_available
            ),
        )
    )

    lower_direction_result = (
        determine_dominant_direction(
            timeframe_results=(
                timeframe_results
            ),
            selected_timeframes=(
                lower_timeframes_available
            ),
        )
    )

    overall_direction = (
        overall_direction_result[
            "dominant_direction"
        ]
    )

    higher_timeframe_bias = (
        higher_direction_result[
            "dominant_direction"
        ]
    )

    lower_timeframe_bias = (
        lower_direction_result[
            "dominant_direction"
        ]
    )

    requested_alignment_count = 0
    opposite_alignment_count = 0
    neutral_count = 0
    confirmed_timeframe_count = 0

    weighted_alignment_points = 0.0
    maximum_weighted_points = 0.0

    confirmation_reasons: list[str] = []
    conflict_reasons: list[str] = []
    warnings: list[str] = []

    for timeframe, result in (
        timeframe_results.items()
    ):
        weight = TIMEFRAME_WEIGHTS.get(
            timeframe,
            1.0,
        )

        maximum_weighted_points += (
            weight * 100.0
        )

        if safe_bool(
            result.get(
                "confirmed",
                False,
            )
        ):
            confirmed_timeframe_count += 1

        if (
            normalize_direction(
                result.get(
                    "direction",
                    WAIT,
                )
            )
            == normalized_requested_direction
            and normalized_requested_direction
            in {BUY, SELL}
        ):
            requested_alignment_count += 1

            weighted_alignment_points += (
                weight
                * clamp(
                    result.get(
                        "timeframe_score",
                        0.0,
                    )
                )
            )

            confirmation_reasons.append(
                f"{timeframe} supports the "
                f"{normalized_requested_direction} "
                "direction."
            )

        elif normalize_direction(
            result.get(
                "direction",
                WAIT,
            )
        ) == WAIT:
            neutral_count += 1

            warnings.append(
                f"{timeframe} is neutral."
            )

        else:
            opposite_alignment_count += 1

            conflict_reasons.append(
                f"{timeframe} conflicts with the "
                f"{normalized_requested_direction} "
                "direction."
            )

    if maximum_weighted_points > 0:
        alignment_score = (
            weighted_alignment_points
            / maximum_weighted_points
        ) * 100.0
    else:
        alignment_score = 0.0

    alignment_score = clamp(
        alignment_score
    )

    higher_scores = [
        clamp(
            timeframe_results[
                timeframe
            ].get(
                "timeframe_score",
                0.0,
            )
        )
        for timeframe
        in higher_timeframes_available
    ]

    if higher_scores:
        higher_timeframe_score = (
            sum(higher_scores)
            / len(higher_scores)
        )
    else:
        higher_timeframe_score = 0.0

    higher_timeframe_score = clamp(
        higher_timeframe_score
    )

    execution_result = (
        timeframe_results.get(
            normalized_execution_timeframe
        )
    )

    execution_timeframe_matches = False
    execution_timeframe_confirmed = False

    if execution_result:
        execution_timeframe_matches = (
            normalize_direction(
                execution_result.get(
                    "direction",
                    WAIT,
                )
            )
            == normalized_requested_direction
            and normalized_requested_direction
            in {BUY, SELL}
        )

        execution_timeframe_confirmed = safe_bool(
            execution_result.get(
                "confirmed",
                False,
            )
        )
    else:
        warnings.append(
            "Execution timeframe data is missing."
        )

    higher_timeframe_matches = (
        higher_timeframe_bias
        == normalized_requested_direction
        and normalized_requested_direction
        in {BUY, SELL}
    )

    lower_timeframe_matches = (
        lower_timeframe_bias
        == normalized_requested_direction
        and normalized_requested_direction
        in {BUY, SELL}
    )

    overall_direction_matches = (
        overall_direction
        == normalized_requested_direction
        and normalized_requested_direction
        in {BUY, SELL}
    )

    hierarchy_conflict = (
        higher_timeframe_bias
        in {BUY, SELL}
        and lower_timeframe_bias
        in {BUY, SELL}
        and higher_timeframe_bias
        != lower_timeframe_bias
    )

    if hierarchy_conflict:
        conflict_reasons.append(
            "Higher and lower timeframe "
            "directions are conflicting."
        )

    if not higher_timeframe_matches:
        conflict_reasons.append(
            "Higher timeframe bias does not "
            "support the requested direction."
        )

    if (
        higher_timeframe_score
        < MINIMUM_HIGHER_TIMEFRAME_SCORE
    ):
        conflict_reasons.append(
            "Higher timeframe score is below "
            "the minimum required score of 70."
        )

    if not execution_timeframe_matches:
        conflict_reasons.append(
            "Execution timeframe direction does "
            "not match the requested direction."
        )

    if not execution_timeframe_confirmed:
        conflict_reasons.append(
            "Execution timeframe is not confirmed."
        )

    if (
        requested_alignment_count
        < MINIMUM_ALIGNED_TIMEFRAMES
    ):
        conflict_reasons.append(
            "Fewer than 3 timeframes support "
            "the requested direction."
        )

    if (
        alignment_score
        < MINIMUM_ALIGNMENT_SCORE
    ):
        conflict_reasons.append(
            "Multi-timeframe alignment score is "
            "below the minimum required score of 75."
        )

    entry_allowed = all(
        [
            normalized_requested_direction
            in {BUY, SELL},
            len(available_timeframes) >= 3,
            requested_alignment_count
            >= MINIMUM_ALIGNED_TIMEFRAMES,
            alignment_score
            >= MINIMUM_ALIGNMENT_SCORE,
            higher_timeframe_score
            >= MINIMUM_HIGHER_TIMEFRAME_SCORE,
            higher_timeframe_matches,
            overall_direction_matches,
            execution_timeframe_matches,
            execution_timeframe_confirmed,
            not hierarchy_conflict,
        ]
    )

    if entry_allowed:
        final_decision = (
            normalized_requested_direction
        )
    else:
        final_decision = WAIT

    conflict_reasons = list(
        dict.fromkeys(
            conflict_reasons
        )
    )

    confirmation_reasons = list(
        dict.fromkeys(
            confirmation_reasons
        )
    )

    warnings = list(
        dict.fromkeys(
            warnings
        )
    )

    return {
        "status": "success",
        "project": "Blue-Trading-AI",
        "safety_version": 17,
        "requested_direction": (
            normalized_requested_direction
        ),
        "final_decision": final_decision,
        "entry_allowed": entry_allowed,
        "alignment_score": round(
            alignment_score,
            2,
        ),
        "alignment_strength": (
            calculate_strength(
                alignment_score
            )
        ),
        "alignment_grade": calculate_grade(
            alignment_score
        ),
        "overall_direction": (
            overall_direction
        ),
        "higher_timeframe_bias": (
            higher_timeframe_bias
        ),
        "lower_timeframe_bias": (
            lower_timeframe_bias
        ),
        "higher_timeframe_score": round(
            higher_timeframe_score,
            2,
        ),
        "execution_timeframe": (
            normalized_execution_timeframe
        ),
        "execution_timeframe_matches": (
            execution_timeframe_matches
        ),
        "execution_timeframe_confirmed": (
            execution_timeframe_confirmed
        ),
        "hierarchy_conflict": (
            hierarchy_conflict
        ),
        "timeframe_summary": {
            "supported_timeframes": list(
                SUPPORTED_TIMEFRAMES
            ),
            "available_timeframes": (
                available_timeframes
            ),
            "missing_timeframes": (
                missing_timeframes
            ),
            "higher_timeframes_available": (
                higher_timeframes_available
            ),
            "lower_timeframes_available": (
                lower_timeframes_available
            ),
            "requested_alignment_count": (
                requested_alignment_count
            ),
            "opposite_alignment_count": (
                opposite_alignment_count
            ),
            "neutral_count": neutral_count,
            "confirmed_timeframe_count": (
                confirmed_timeframe_count
            ),
        },
        "direction_weights": {
            "overall": (
                overall_direction_result
            ),
            "higher_timeframes": (
                higher_direction_result
            ),
            "lower_timeframes": (
                lower_direction_result
            ),
        },
        "confirmation_reasons": (
            confirmation_reasons
        ),
        "conflict_reasons": (
            conflict_reasons
        ),
        "warnings": warnings,
        "timeframe_results": (
            timeframe_results
        ),
        "safety_rules": {
            "minimum_alignment_score": (
                MINIMUM_ALIGNMENT_SCORE
            ),
            "minimum_higher_timeframe_score": (
                MINIMUM_HIGHER_TIMEFRAME_SCORE
            ),
            "minimum_aligned_timeframes": (
                MINIMUM_ALIGNED_TIMEFRAMES
            ),
            "higher_timeframe_alignment_required": (
                True
            ),
            "execution_timeframe_confirmation_required": (
                True
            ),
            "hierarchy_conflict_blocks_signal": True,
            "broker_connection_enabled": False,
            "trade_execution_enabled": False,
        },
        "important_notice": (
            "Blue-Trading-AI provides multi-timeframe "
            "market analysis and signals only. It does "
            "not connect to brokers or execute trades."
        ),
    }

__all__ = [
    "BEARISH",
    "BULLISH",
    "BUY",
    "HIGHER_TIMEFRAMES",
    "LOWER_TIMEFRAMES",
    "MAXIMUM_TIMEFRAME_COUNT",
    "MINIMUM_ALIGNED_TIMEFRAMES",
    "MINIMUM_ALIGNMENT_SCORE",
    "MINIMUM_HIGHER_TIMEFRAME_SCORE",
    "NEUTRAL",
    "SELL",
    "SUPPORTED_TIMEFRAMES",
    "TIMEFRAME_WEIGHTS",
    "WAIT",
    "calculate_grade",
    "calculate_strength",
    "calculate_timeframe_score",
    "clamp",
    "determine_dominant_direction",
    "evaluate_multi_timeframe_intelligence",
    "normalize_direction",
    "normalize_zone",
    "safe_bool",
    "safe_float",
]