from __future__ import annotations

import math
from typing import Any, Final


MINIMUM_CONFIDENCE: Final = 80.0
MINIMUM_CONFIRMATIONS: Final = 3

MAXIMUM_SCORE: Final = 100.0


BULLISH_DIRECTION: Final = "BULLISH"
BEARISH_DIRECTION: Final = "BEARISH"
NEUTRAL_DIRECTION: Final = "NEUTRAL"


FACTOR_WEIGHTS: Final[dict[str, float]] = {
    "market_structure": 14.0,
    "bos": 10.0,
    "choch": 10.0,
    "trend": 12.0,
    "support_resistance": 9.0,
    "order_block": 9.0,
    "fair_value_gap": 7.0,
    "liquidity": 7.0,
    "candlestick": 6.0,
    "chart_pattern": 6.0,
    "breakout": 5.0,
    "multi_timeframe": 5.0,
}


def normalize_direction(
    value: Any,
) -> str:
    """
    Converts different direction values into:
    BULLISH, BEARISH, or NEUTRAL.
    """

    normalized = str(
        value or ""
    ).strip().upper()

    bullish_values = {
        "BUY",
        "BULLISH",
        "UP",
        "LONG",
        "UPTREND",
    }

    bearish_values = {
        "SELL",
        "BEARISH",
        "DOWN",
        "SHORT",
        "DOWNTREND",
    }

    if normalized in bullish_values:
        return BULLISH_DIRECTION

    if normalized in bearish_values:
        return BEARISH_DIRECTION

    return NEUTRAL_DIRECTION


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """Safely convert a value into a finite float."""

    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default

    if not math.isfinite(number):
        return default

    return number


def clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    """
    Restricts a number between minimum and maximum.
    """

    return max(
        minimum,
        min(value, maximum),
    )


def create_factor_result(
    factor_name: str,
    factor_value: Any,
    requested_direction: str,
) -> dict[str, Any]:
    """
    Scores one technical-analysis factor.
    """

    weight = FACTOR_WEIGHTS.get(
        factor_name,
        0.0,
    )

    factor_direction = normalize_direction(
        factor_value
    )

    requested = normalize_direction(
        requested_direction
    )

    bullish_score = 0.0
    bearish_score = 0.0

    if factor_direction == BULLISH_DIRECTION:
        bullish_score = weight

    elif factor_direction == BEARISH_DIRECTION:
        bearish_score = weight

    supports_requested_direction = (
        factor_direction == requested
        and requested != NEUTRAL_DIRECTION
    )

    conflicts_with_requested_direction = (
        factor_direction
        != NEUTRAL_DIRECTION
        and requested
        != NEUTRAL_DIRECTION
        and factor_direction != requested
    )

    if supports_requested_direction:
        explanation = (
            f"{factor_name.replace('_', ' ').title()} "
            f"supports the {requested} direction."
        )

    elif conflicts_with_requested_direction:
        explanation = (
            f"{factor_name.replace('_', ' ').title()} "
            f"conflicts with the {requested} direction."
        )

    else:
        explanation = (
            f"{factor_name.replace('_', ' ').title()} "
            "is neutral or unavailable."
        )

    return {
        "factor": factor_name,
        "weight": weight,
        "detected_direction": factor_direction,
        "supports_requested_direction": (
            supports_requested_direction
        ),
        "conflicts_with_requested_direction": (
            conflicts_with_requested_direction
        ),
        "bullish_score": bullish_score,
        "bearish_score": bearish_score,
        "explanation": explanation,
    }


def calculate_direction_confidence(
    direction_score: float,
    opposing_score: float,
) -> float:
    """
    Calculate confidence using directional evidence
    and opposing evidence.

    Opposing evidence reduces final confidence.
    """

    safe_direction_score = safe_float(
        direction_score
    )
    safe_opposing_score = safe_float(
        opposing_score
    )

    adjusted_score = (
        safe_direction_score
        - safe_opposing_score
    )

    return round(
        clamp(
            adjusted_score,
            0.0,
            MAXIMUM_SCORE,
        ),
        2,
    )


def get_trade_quality_grade(
    confidence: float,
    confirmations_count: int,
) -> str:
    """
    Assigns a transparent trade-quality grade.
    """

    if (
        confidence >= 92.0
        and confirmations_count >= 7
    ):
        return "A+"

    if (
        confidence >= 88.0
        and confirmations_count >= 6
    ):
        return "A"

    if (
        confidence >= 84.0
        and confirmations_count >= 5
    ):
        return "B+"

    if (
        confidence >= 80.0
        and confirmations_count >= 3
    ):
        return "B"

    if confidence >= 70.0:
        return "C"

    return "D"


def validate_factor_weights() -> None:
    """Validate the fixed Decision Intelligence weighting model."""

    total_weight = sum(
        safe_float(weight)
        for weight in FACTOR_WEIGHTS.values()
    )

    if round(
        total_weight,
        8,
    ) != MAXIMUM_SCORE:
        raise RuntimeError(
            "Decision Intelligence factor weights must total 100."
        )

    for factor_name, weight in FACTOR_WEIGHTS.items():
        if not factor_name:
            raise RuntimeError(
                "Decision Intelligence factor names cannot be empty."
            )

        if (
            not math.isfinite(weight)
            or weight < 0.0
        ):
            raise RuntimeError(
                "Decision Intelligence factor weights must be finite and non-negative."
            )


validate_factor_weights()


def evaluate_trade_decision(
    requested_direction: str,
    factors: dict[str, Any],
) -> dict[str, Any]:
    """
    Evaluate technical-analysis evidence and produce
    a BUY, SELL, or WAIT decision.

    Safety rules:
    - Minimum confidence is 80%.
    - Minimum confirmations is 3.
    - Conflicting evidence reduces confidence.
    - Neutral evidence does not count as confirmation.
    """

    if not isinstance(
        factors,
        dict,
    ):
        factors = {}

    normalized_requested_direction = (
        normalize_direction(
            requested_direction
        )
    )

    factor_results: list[dict[str, Any]] = []

    for factor_name in FACTOR_WEIGHTS:
        factor_result = create_factor_result(
            factor_name=factor_name,
            factor_value=factors.get(
                factor_name
            ),
            requested_direction=(
                normalized_requested_direction
            ),
        )

        factor_results.append(
            factor_result
        )

    bullish_score = round(
        sum(
            item["bullish_score"]
            for item in factor_results
        ),
        2,
    )

    bearish_score = round(
        sum(
            item["bearish_score"]
            for item in factor_results
        ),
        2,
    )

    bullish_confirmations = sum(
        1
        for item in factor_results
        if item["detected_direction"]
        == BULLISH_DIRECTION
    )

    bearish_confirmations = sum(
        1
        for item in factor_results
        if item["detected_direction"]
        == BEARISH_DIRECTION
    )

    bullish_confidence = (
        calculate_direction_confidence(
            direction_score=bullish_score,
            opposing_score=bearish_score,
        )
    )

    bearish_confidence = (
        calculate_direction_confidence(
            direction_score=bearish_score,
            opposing_score=bullish_score,
        )
    )

    if bullish_score > bearish_score:
        dominant_direction = (
            BULLISH_DIRECTION
        )
        confidence = bullish_confidence
        confirmations_count = (
            bullish_confirmations
        )

    elif bearish_score > bullish_score:
        dominant_direction = (
            BEARISH_DIRECTION
        )
        confidence = bearish_confidence
        confirmations_count = (
            bearish_confirmations
        )

    else:
        dominant_direction = (
            NEUTRAL_DIRECTION
        )
        confidence = 0.0
        confirmations_count = 0

    direction_matches_request = (
        dominant_direction
        == normalized_requested_direction
    )

    trade_allowed = (
        dominant_direction
        in {
            BULLISH_DIRECTION,
            BEARISH_DIRECTION,
        }
        and confidence >= MINIMUM_CONFIDENCE
        and confirmations_count
        >= MINIMUM_CONFIRMATIONS
        and direction_matches_request
    )

    if trade_allowed:
        action = (
            "BUY"
            if dominant_direction
            == BULLISH_DIRECTION
            else "SELL"
        )

        decision_reason = (
            f"{action} approved with "
            f"{confidence:.2f}% confidence and "
            f"{confirmations_count} confirmations."
        )

    else:
        action = "WAIT"

        reasons: list[str] = []

        if dominant_direction == NEUTRAL_DIRECTION:
            reasons.append(
                "Bullish and bearish evidence are balanced."
            )

        if not direction_matches_request:
            reasons.append(
                "The dominant market direction does not "
                "match the requested direction."
            )

        if confidence < MINIMUM_CONFIDENCE:
            reasons.append(
                "Confidence is below the required 80%."
            )

        if confirmations_count < MINIMUM_CONFIRMATIONS:
            reasons.append(
                "Fewer than three confirmations exist."
            )

        decision_reason = " ".join(
            reasons
        )

    supporting_factors = [
        item
        for item in factor_results
        if item[
            "supports_requested_direction"
        ]
    ]

    conflicting_factors = [
        item
        for item in factor_results
        if item[
            "conflicts_with_requested_direction"
        ]
    ]

    neutral_factors = [
        item
        for item in factor_results
        if item["detected_direction"]
        == NEUTRAL_DIRECTION
    ]

    trade_quality_grade = (
        get_trade_quality_grade(
            confidence=confidence,
            confirmations_count=(
                confirmations_count
            ),
        )
    )

    return {
        "status": "success",
        "safety_version": 12,
        "action": action,
        "trade_allowed": trade_allowed,
        "requested_direction": (
            normalized_requested_direction
        ),
        "dominant_direction": (
            dominant_direction
        ),
        "direction_matches_request": (
            direction_matches_request
        ),
        "confidence": confidence,
        "minimum_confidence_required": (
            MINIMUM_CONFIDENCE
        ),
        "confirmations_count": (
            confirmations_count
        ),
        "minimum_confirmations_required": (
            MINIMUM_CONFIRMATIONS
        ),
        "trade_quality_grade": (
            trade_quality_grade
        ),
        "scores": {
            "bullish_score": bullish_score,
            "bearish_score": bearish_score,
            "maximum_score": MAXIMUM_SCORE,
        },
        "confirmation_summary": {
            "bullish_confirmations": (
                bullish_confirmations
            ),
            "bearish_confirmations": (
                bearish_confirmations
            ),
            "supporting_factors_count": len(
                supporting_factors
            ),
            "conflicting_factors_count": len(
                conflicting_factors
            ),
            "neutral_factors_count": len(
                neutral_factors
            ),
        },
        "supporting_factors": (
            supporting_factors
        ),
        "conflicting_factors": (
            conflicting_factors
        ),
        "neutral_factors": neutral_factors,
        "all_factor_results": (
            factor_results
        ),
        "decision_reason": decision_reason,
        "safety_rules": {
            "weak_trade_cannot_be_approved": True,
            "minimum_80_confidence": True,
            "minimum_3_confirmations": True,
            "learning_adjustment_not_applied_here": (
                True
            ),
            "broker_execution_enabled": False,
        },
    }

__all__ = [
    "BEARISH_DIRECTION",
    "BULLISH_DIRECTION",
    "FACTOR_WEIGHTS",
    "MAXIMUM_SCORE",
    "MINIMUM_CONFIDENCE",
    "MINIMUM_CONFIRMATIONS",
    "NEUTRAL_DIRECTION",
    "calculate_direction_confidence",
    "clamp",
    "create_factor_result",
    "evaluate_trade_decision",
    "get_trade_quality_grade",
    "normalize_direction",
    "safe_float",
    "validate_factor_weights",
]