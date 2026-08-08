from __future__ import annotations

import math
from typing import Any, Final


BULLISH: Final = "BULLISH"
BEARISH: Final = "BEARISH"
NEUTRAL: Final = "NEUTRAL"

BUY: Final = "BUY"
SELL: Final = "SELL"
WAIT: Final = "WAIT"

PREMIUM: Final = "PREMIUM"
DISCOUNT: Final = "DISCOUNT"
EQUILIBRIUM: Final = "EQUILIBRIUM"

WEAK: Final = "WEAK"
MODERATE: Final = "MODERATE"
STRONG: Final = "STRONG"
VERY_STRONG: Final = "VERY_STRONG"

MINIMUM_INSTITUTIONAL_SCORE: Final = 70.0
MINIMUM_INSTITUTIONAL_CONFIRMATIONS: Final = 3
MAXIMUM_CONFIRMATIONS: Final = 100


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """Safely convert a value to a finite float."""

    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default

    if not math.isfinite(number):
        return default

    return number


def safe_bool(
    value: Any,
) -> bool:
    """Safely convert explicit truthy values to boolean."""

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value == 1

    if isinstance(value, str):
        return value.strip().lower() in {
            "true",
            "1",
            "yes",
            "approved",
            "confirmed",
        }

    return False


def clamp(
    value: Any,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    """Restrict a finite number between minimum and maximum."""

    number = safe_float(
        value,
        default=minimum,
    )

    return max(
        minimum,
        min(
            number,
            maximum,
        ),
    )


def normalize_direction(
    value: Any,
) -> str:
    """
    Normalizes market direction.
    """

    normalized = str(
        value or NEUTRAL
    ).strip().upper()

    if normalized in {
        BULLISH,
        "BUY",
        "LONG",
        "UP",
    }:
        return BULLISH

    if normalized in {
        BEARISH,
        "SELL",
        "SHORT",
        "DOWN",
    }:
        return BEARISH

    return NEUTRAL


def calculate_range_position(
    current_price: Any,
    range_high: Any,
    range_low: Any,
) -> dict[str, Any]:
    """
    Calculates premium, discount, or equilibrium
    position inside the dealing range.
    """

    price = safe_float(
        current_price,
        default=float("nan"),
    )
    high = safe_float(
        range_high,
        default=float("nan"),
    )
    low = safe_float(
        range_low,
        default=float("nan"),
    )

    if not all(
        math.isfinite(value)
        for value in (
            price,
            high,
            low,
        )
    ):
        return {
            "valid_range": False,
            "zone": EQUILIBRIUM,
            "range_position_percent": 50.0,
            "equilibrium_price": 0.0,
        }

    if (
        high <= low
        or high <= 0.0
        or low <= 0.0
        or price <= 0.0
    ):
        return {
            "valid_range": False,
            "zone": EQUILIBRIUM,
            "range_position_percent": 50.0,
            "equilibrium_price": 0.0,
        }

    equilibrium = (
        high + low
    ) / 2

    if not low <= price <= high:
        return {
            "valid_range": False,
            "zone": EQUILIBRIUM,
            "range_position_percent": 50.0,
            "equilibrium_price": round(
                equilibrium,
                5,
            ),
        }

    position = (
        (price - low)
        / (high - low)
    ) * 100

    position = clamp(position)

    if position < 45.0:
        zone = DISCOUNT

    elif position > 55.0:
        zone = PREMIUM

    else:
        zone = EQUILIBRIUM

    return {
        "valid_range": True,
        "zone": zone,
        "range_position_percent": round(
            position,
            2,
        ),
        "equilibrium_price": round(
            equilibrium,
            5,
        ),
    }


def score_fair_value_gap(
    detected: bool,
    direction: str,
    gap_size_percent: Any,
    mitigated: bool,
) -> dict[str, Any]:
    """
    Scores a Fair Value Gap.
    """

    if not detected:
        return {
            "detected": False,
            "direction": NEUTRAL,
            "score": 0.0,
            "strength": WEAK,
        }

    size = clamp(
        safe_float(gap_size_percent),
        0.0,
        5.0,
    )

    score = 20.0

    score += min(
        size * 10.0,
        30.0,
    )

    if not mitigated:
        score += 25.0

    else:
        score += 5.0

    score = clamp(score)

    return {
        "detected": True,
        "direction": normalize_direction(
            direction
        ),
        "gap_size_percent": size,
        "mitigated": mitigated,
        "score": round(score, 2),
        "strength": classify_strength(
            score
        ),
    }


def score_order_block(
    detected: bool,
    direction: str,
    displacement_score: Any,
    freshness_score: Any,
    respected: bool,
) -> dict[str, Any]:
    """
    Scores an institutional order block.
    """

    if not detected:
        return {
            "detected": False,
            "direction": NEUTRAL,
            "score": 0.0,
            "strength": WEAK,
        }

    displacement = clamp(
        safe_float(displacement_score)
    )

    freshness = clamp(
        safe_float(freshness_score)
    )

    score = (
        displacement * 0.45
        + freshness * 0.35
    )

    if respected:
        score += 20.0

    score = clamp(score)

    return {
        "detected": True,
        "direction": normalize_direction(
            direction
        ),
        "displacement_score": displacement,
        "freshness_score": freshness,
        "respected": respected,
        "score": round(score, 2),
        "strength": classify_strength(
            score
        ),
    }


def classify_strength(
    score: Any,
) -> str:
    """
    Classifies an institutional score.
    """

    value = clamp(
        safe_float(score)
    )

    if value >= 85.0:
        return VERY_STRONG

    if value >= 70.0:
        return STRONG

    if value >= 50.0:
        return MODERATE

    return WEAK


def calculate_grade(
    score: Any,
) -> str:
    """
    Converts the institutional score to a grade.
    """

    value = clamp(
        safe_float(score)
    )

    if value >= 92.0:
        return "A+"

    if value >= 85.0:
        return "A"

    if value >= 75.0:
        return "B"

    if value >= 65.0:
        return "C"

    return "D"


def evaluate_institutional_smc(
    market_direction: Any,
    current_price: Any,
    range_high: Any,
    range_low: Any,
    fvg_detected: bool = False,
    fvg_direction: Any = NEUTRAL,
    fvg_gap_size_percent: Any = 0.0,
    fvg_mitigated: bool = False,
    order_block_detected: bool = False,
    order_block_direction: Any = NEUTRAL,
    order_block_displacement_score: Any = 0.0,
    order_block_freshness_score: Any = 0.0,
    order_block_respected: bool = False,
    liquidity_sweep_detected: bool = False,
    liquidity_sweep_direction: Any = NEUTRAL,
    equal_high_detected: bool = False,
    equal_low_detected: bool = False,
    inducement_detected: bool = False,
    mitigation_block_detected: bool = False,
    breaker_block_detected: bool = False,
    structure_alignment: bool = False,
) -> dict[str, Any]:
    """
    Evaluates institutional Smart Money Concept
    conditions for Blue-Trading-AI.

    This function produces analysis and signals only.
    It cannot connect to brokers or execute trades.
    """

    direction = normalize_direction(
        market_direction
    )

    fvg_detected = safe_bool(
        fvg_detected
    )
    fvg_mitigated = safe_bool(
        fvg_mitigated
    )
    order_block_detected = safe_bool(
        order_block_detected
    )
    order_block_respected = safe_bool(
        order_block_respected
    )
    liquidity_sweep_detected = safe_bool(
        liquidity_sweep_detected
    )
    equal_high_detected = safe_bool(
        equal_high_detected
    )
    equal_low_detected = safe_bool(
        equal_low_detected
    )
    inducement_detected = safe_bool(
        inducement_detected
    )
    mitigation_block_detected = safe_bool(
        mitigation_block_detected
    )
    breaker_block_detected = safe_bool(
        breaker_block_detected
    )
    structure_alignment = safe_bool(
        structure_alignment
    )

    range_analysis = calculate_range_position(
        current_price=current_price,
        range_high=range_high,
        range_low=range_low,
    )

    fvg_analysis = score_fair_value_gap(
        detected=fvg_detected,
        direction=normalize_direction(
            fvg_direction
        ),
        gap_size_percent=fvg_gap_size_percent,
        mitigated=fvg_mitigated,
    )

    order_block_analysis = score_order_block(
        detected=order_block_detected,
        direction=normalize_direction(
            order_block_direction
        ),
        displacement_score=(
            order_block_displacement_score
        ),
        freshness_score=(
            order_block_freshness_score
        ),
        respected=order_block_respected,
    )

    bullish_score = 0.0
    bearish_score = 0.0

    bullish_confirmations: list[str] = []
    bearish_confirmations: list[str] = []
    warnings: list[str] = []

    if not range_analysis.get(
        "valid_range",
        False,
    ):
        warnings.append(
            "The supplied dealing range is invalid or the current price "
            "is outside the range."
        )

    # Premium and discount analysis
    range_zone = range_analysis["zone"]

    if (
        direction == BULLISH
        and range_zone == DISCOUNT
    ):
        bullish_score += 15.0
        bullish_confirmations.append(
            "Bullish setup is located in the discount zone."
        )

    elif (
        direction == BEARISH
        and range_zone == PREMIUM
    ):
        bearish_score += 15.0
        bearish_confirmations.append(
            "Bearish setup is located in the premium zone."
        )

    elif range_zone == EQUILIBRIUM:
        warnings.append(
            "Price is near the dealing-range equilibrium."
        )

    else:
        warnings.append(
            "Price location does not strongly support "
            "the selected market direction."
        )

    # Fair Value Gap analysis
    if fvg_analysis["detected"]:
        fvg_points = (
            fvg_analysis["score"]
            * 0.20
        )

        if (
            fvg_analysis["direction"]
            == BULLISH
        ):
            bullish_score += fvg_points
            bullish_confirmations.append(
                "A bullish Fair Value Gap is present."
            )

        elif (
            fvg_analysis["direction"]
            == BEARISH
        ):
            bearish_score += fvg_points
            bearish_confirmations.append(
                "A bearish Fair Value Gap is present."
            )

    # Order block analysis
    if order_block_analysis["detected"]:
        order_block_points = (
            order_block_analysis["score"]
            * 0.25
        )

        if (
            order_block_analysis["direction"]
            == BULLISH
        ):
            bullish_score += (
                order_block_points
            )
            bullish_confirmations.append(
                "A bullish institutional order block is present."
            )

        elif (
            order_block_analysis["direction"]
            == BEARISH
        ):
            bearish_score += (
                order_block_points
            )
            bearish_confirmations.append(
                "A bearish institutional order block is present."
            )

    # Liquidity sweep
    liquidity_direction = (
        normalize_direction(
            liquidity_sweep_direction
        )
    )

    if liquidity_sweep_detected:
        if liquidity_direction == BULLISH:
            bullish_score += 15.0
            bullish_confirmations.append(
                "Sell-side liquidity was swept before "
                "a bullish reaction."
            )

        elif liquidity_direction == BEARISH:
            bearish_score += 15.0
            bearish_confirmations.append(
                "Buy-side liquidity was swept before "
                "a bearish reaction."
            )

    # Equal highs and equal lows
    if equal_low_detected:
        bullish_score += 5.0
        bullish_confirmations.append(
            "Equal lows indicate potential "
            "sell-side liquidity."
        )

    if equal_high_detected:
        bearish_score += 5.0
        bearish_confirmations.append(
            "Equal highs indicate potential "
            "buy-side liquidity."
        )

    # Advanced institutional concepts
    if inducement_detected:
        if direction == BULLISH:
            bullish_score += 8.0
            bullish_confirmations.append(
                "Bullish inducement behavior was detected."
            )

        elif direction == BEARISH:
            bearish_score += 8.0
            bearish_confirmations.append(
                "Bearish inducement behavior was detected."
            )

    if mitigation_block_detected:
        if direction == BULLISH:
            bullish_score += 8.0
            bullish_confirmations.append(
                "A bullish mitigation block was detected."
            )

        elif direction == BEARISH:
            bearish_score += 8.0
            bearish_confirmations.append(
                "A bearish mitigation block was detected."
            )

    if breaker_block_detected:
        if direction == BULLISH:
            bullish_score += 10.0
            bullish_confirmations.append(
                "A bullish breaker block was detected."
            )

        elif direction == BEARISH:
            bearish_score += 10.0
            bearish_confirmations.append(
                "A bearish breaker block was detected."
            )

    if structure_alignment:
        if direction == BULLISH:
            bullish_score += 14.0
            bullish_confirmations.append(
                "Market structure supports the bullish setup."
            )

        elif direction == BEARISH:
            bearish_score += 14.0
            bearish_confirmations.append(
                "Market structure supports the bearish setup."
            )

    bullish_score = clamp(
        bullish_score
    )

    bearish_score = clamp(
        bearish_score
    )

    if bullish_score > bearish_score:
        dominant_direction = BULLISH
        institutional_score = bullish_score
        confirmations = bullish_confirmations

    elif bearish_score > bullish_score:
        dominant_direction = BEARISH
        institutional_score = bearish_score
        confirmations = bearish_confirmations

    else:
        dominant_direction = NEUTRAL
        institutional_score = max(
            bullish_score,
            bearish_score,
        )
        confirmations = []

    confirmation_count = len(
        confirmations
    )

    direction_matches = (
        dominant_direction == direction
        and direction != NEUTRAL
    )

    setup_approved = (
        institutional_score
        >= MINIMUM_INSTITUTIONAL_SCORE
        and confirmation_count
        >= MINIMUM_INSTITUTIONAL_CONFIRMATIONS
        and direction_matches
        and range_analysis.get(
            "valid_range",
            False,
        )
    )

    if setup_approved:
        if dominant_direction == BULLISH:
            institutional_decision = BUY
        else:
            institutional_decision = SELL

    else:
        institutional_decision = WAIT

    blocking_reasons: list[str] = []

    if not range_analysis.get(
        "valid_range",
        False,
    ):
        blocking_reasons.append(
            "A valid dealing range containing the current price is required."
        )

    if institutional_score < MINIMUM_INSTITUTIONAL_SCORE:
        blocking_reasons.append(
            "Institutional score is below the "
            "minimum required score of 70."
        )

    if (
        confirmation_count
        < MINIMUM_INSTITUTIONAL_CONFIRMATIONS
    ):
        blocking_reasons.append(
            "The setup has fewer than the required "
            "3 institutional confirmations."
        )

    if not direction_matches:
        blocking_reasons.append(
            "The dominant institutional direction "
            "does not match the selected market direction."
        )

    confirmations = list(
        dict.fromkeys(
            confirmations[
                :MAXIMUM_CONFIRMATIONS
            ]
        )
    )
    blocking_reasons = list(
        dict.fromkeys(
            blocking_reasons
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
        "safety_version": 15,
        "market_direction": direction,
        "dominant_institutional_direction": (
            dominant_direction
        ),
        "institutional_decision": (
            institutional_decision
        ),
        "setup_approved": setup_approved,
        "institutional_score": round(
            institutional_score,
            2,
        ),
        "institutional_strength": (
            classify_strength(
                institutional_score
            )
        ),
        "institutional_grade": (
            calculate_grade(
                institutional_score
            )
        ),
        "institutional_confirmations_count": (
            confirmation_count
        ),
        "confirmations": confirmations,
        "blocking_reasons": blocking_reasons,
        "warnings": warnings,
        "bullish_score": round(
            bullish_score,
            2,
        ),
        "bearish_score": round(
            bearish_score,
            2,
        ),
        "range_analysis": range_analysis,
        "fair_value_gap_analysis": (
            fvg_analysis
        ),
        "order_block_analysis": (
            order_block_analysis
        ),
        "advanced_smc": {
            "liquidity_sweep_detected": (
                liquidity_sweep_detected
            ),
            "liquidity_sweep_direction": (
                liquidity_direction
            ),
            "equal_high_detected": (
                equal_high_detected
            ),
            "equal_low_detected": (
                equal_low_detected
            ),
            "inducement_detected": (
                inducement_detected
            ),
            "mitigation_block_detected": (
                mitigation_block_detected
            ),
            "breaker_block_detected": (
                breaker_block_detected
            ),
            "structure_alignment": (
                structure_alignment
            ),
        },
        "safety_rules": {
            "minimum_institutional_score": (
                MINIMUM_INSTITUTIONAL_SCORE
            ),
            "minimum_institutional_confirmations": (
                MINIMUM_INSTITUTIONAL_CONFIRMATIONS
            ),
            "weak_institutional_setup_blocks_signal": True,
            "direction_mismatch_blocks_signal": True,
            "broker_connection_enabled": False,
            "trade_execution_enabled": False,
        },
        "important_notice": (
            "Blue-Trading-AI provides institutional "
            "market analysis and signals only. It does "
            "not connect to brokers or execute trades."
        ),
    }

__all__ = [
    "BEARISH",
    "BULLISH",
    "BUY",
    "DISCOUNT",
    "EQUILIBRIUM",
    "MAXIMUM_CONFIRMATIONS",
    "MINIMUM_INSTITUTIONAL_CONFIRMATIONS",
    "MINIMUM_INSTITUTIONAL_SCORE",
    "MODERATE",
    "NEUTRAL",
    "PREMIUM",
    "SELL",
    "STRONG",
    "VERY_STRONG",
    "WAIT",
    "WEAK",
    "calculate_grade",
    "calculate_range_position",
    "classify_strength",
    "clamp",
    "evaluate_institutional_smc",
    "normalize_direction",
    "safe_bool",
    "safe_float",
    "score_fair_value_gap",
    "score_order_block",
]