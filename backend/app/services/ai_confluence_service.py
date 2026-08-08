from __future__ import annotations

import math
from typing import Any, Final


BUY: Final = "BUY"
SELL: Final = "SELL"
WAIT: Final = "WAIT"

MINIMUM_FINAL_CONFIDENCE: Final = 80.0
MINIMUM_TOTAL_CONFIRMATIONS: Final = 3
MINIMUM_CONFLUENCE_SCORE: Final = 75.0
MINIMUM_INSTITUTIONAL_SCORE: Final = 70.0
MINIMUM_INSTITUTIONAL_CONFIRMATIONS: Final = 3
MINIMUM_RISK_REWARD_RATIO: Final = 1.5
MAXIMUM_CONFIRMATIONS_PER_COMPONENT: Final = 100

ALLOWED_DIRECTIONS = {
    BUY,
    SELL,
    WAIT,
}


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


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    """Safely convert a value to an integer."""

    if isinstance(value, bool):
        return default

    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def safe_bool(
    value: Any,
) -> bool:
    """
    Safely converts a value to boolean.
    """

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in {
            "true",
            "1",
            "yes",
            "approved",
            "pass",
            "passed",
        }

    return bool(value)


def clamp(
    value: Any,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    """
    Restricts a value between 0 and 100.
    """

    number = safe_float(value)

    return max(
        minimum,
        min(number, maximum),
    )


def normalize_direction(
    value: Any,
) -> str:
    """
    Normalizes different direction labels.
    """

    direction = str(
        value or WAIT
    ).strip().upper()

    if direction in {
        "BUY",
        "BULLISH",
        "LONG",
        "UP",
    }:
        return BUY

    if direction in {
        "SELL",
        "BEARISH",
        "SHORT",
        "DOWN",
    }:
        return SELL

    return WAIT


def calculate_grade(
    score: Any,
) -> str:
    """
    Converts a score into a final setup grade.
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
    Converts a score into a descriptive strength.
    """

    value = clamp(score)

    if value >= 90.0:
        return "VERY_STRONG"

    if value >= 80.0:
        return "STRONG"

    if value >= 70.0:
        return "MODERATE"

    return "WEAK"


def directions_match(
    first_direction: Any,
    second_direction: Any,
) -> bool:
    """
    Checks whether two directional signals match.
    """

    first = normalize_direction(
        first_direction
    )

    second = normalize_direction(
        second_direction
    )

    return (
        first == second
        and first in {BUY, SELL}
    )


def evaluate_ai_confluence(
    decision: Any,
    decision_confidence: Any,
    decision_confirmations: Any,
    context_decision: Any,
    context_approved: bool,
    context_supports_trade: bool,
    context_risk_environment: Any,
    context_signal_quality: Any,
    institutional_decision: Any,
    institutional_approved: bool,
    institutional_score: Any,
    institutional_confirmations: Any,
    market_structure_direction: Any = WAIT,
    market_structure_confirmed: bool = False,
    bos_detected: bool = False,
    choch_detected: bool = False,
    multi_timeframe_direction: Any = WAIT,
    multi_timeframe_alignment: bool = False,
    trend_direction: Any = WAIT,
    trend_strength_score: Any = 0.0,
    support_resistance_confirmed: bool = False,
    candlestick_direction: Any = WAIT,
    candlestick_confirmed: bool = False,
    breakout_confirmed: bool = False,
    risk_reward_ratio: Any = 0.0,
    stop_loss_valid: bool = False,
    take_profit_valid: bool = False,
) -> dict[str, Any]:
    """
    Combines all major Blue-Trading-AI analysis layers.

    The function returns analysis and signal decisions only.
    It cannot connect to brokers or execute trades.
    """

    original_decision = normalize_direction(
        decision
    )

    normalized_context_decision = normalize_direction(
        context_decision
    )

    normalized_institutional_decision = (
        normalize_direction(
            institutional_decision
        )
    )

    structure_direction = normalize_direction(
        market_structure_direction
    )

    timeframe_direction = normalize_direction(
        multi_timeframe_direction
    )

    normalized_trend_direction = normalize_direction(
        trend_direction
    )

    normalized_candlestick_direction = (
        normalize_direction(
            candlestick_direction
        )
    )

    confidence = clamp(
        decision_confidence
    )

    base_confirmations = min(
        max(
            safe_int(decision_confirmations),
            0,
        ),
        MAXIMUM_CONFIRMATIONS_PER_COMPONENT,
    )

    institutional_confirmation_count = min(
        max(
            safe_int(
                institutional_confirmations
            ),
            0,
        ),
        MAXIMUM_CONFIRMATIONS_PER_COMPONENT,
    )

    institutional_score_value = clamp(
        institutional_score
    )

    trend_score = clamp(
        trend_strength_score
    )

    reward_risk = max(
        safe_float(risk_reward_ratio),
        0.0,
    )

    risk_environment = str(
        context_risk_environment or "UNKNOWN"
    ).strip().upper()

    signal_quality = str(
        context_signal_quality or "UNKNOWN"
    ).strip().upper()

    confluence_score = 0.0

    confirmation_reasons: list[str] = []
    blocking_reasons: list[str] = []
    warnings: list[str] = []

    total_confirmations = base_confirmations

    # =====================================
    # 1. DECISION INTELLIGENCE
    # Maximum contribution: 25 points
    # =====================================

    if original_decision in {
        BUY,
        SELL,
    }:
        confluence_score += confidence * 0.25

        confirmation_reasons.append(
            "Decision Intelligence produced "
            f"a {original_decision} decision."
        )
    else:
        blocking_reasons.append(
            "Decision Intelligence returned WAIT."
        )

    if confidence < MINIMUM_FINAL_CONFIDENCE:
        blocking_reasons.append(
            "Decision confidence is below "
            "the minimum required level of 80."
        )

    if (
        base_confirmations
        < MINIMUM_TOTAL_CONFIRMATIONS
    ):
        blocking_reasons.append(
            "Decision Intelligence has fewer than "
            "the required 3 confirmations."
        )

    # =====================================
    # 2. CONTEXT-AWARE DECISION
    # Maximum contribution: 20 points
    # =====================================

    context_direction_matches = directions_match(
        original_decision,
        normalized_context_decision,
    )

    if (
        safe_bool(context_approved)
        and safe_bool(context_supports_trade)
        and context_direction_matches
    ):
        confluence_score += 20.0
        total_confirmations += 1

        confirmation_reasons.append(
            "Market context supports the "
            "original signal direction."
        )
    else:
        blocking_reasons.append(
            "Market context does not fully approve "
            "the original signal."
        )

    if risk_environment == "HIGH":
        blocking_reasons.append(
            "The current market context is "
            "classified as HIGH risk."
        )

    if signal_quality == "WEAK":
        blocking_reasons.append(
            "The current market-context signal "
            "quality is classified as WEAK."
        )

    # =====================================
    # 3. INSTITUTIONAL SMC
    # Maximum contribution: 20 points
    # =====================================

    institutional_direction_matches = (
        directions_match(
            original_decision,
            normalized_institutional_decision,
        )
    )

    if (
        safe_bool(institutional_approved)
        and institutional_direction_matches
    ):
        institutional_points = (
            institutional_score_value
            * 0.20
        )

        confluence_score += institutional_points
        total_confirmations += (
            institutional_confirmation_count
        )

        confirmation_reasons.append(
            "Institutional Smart Money analysis "
            "supports the signal direction."
        )
    else:
        blocking_reasons.append(
            "Institutional Smart Money analysis "
            "does not approve the signal."
        )

    if institutional_score_value < MINIMUM_INSTITUTIONAL_SCORE:
        blocking_reasons.append(
            "Institutional score is below "
            "the minimum required level of 70."
        )

    if institutional_confirmation_count < MINIMUM_INSTITUTIONAL_CONFIRMATIONS:
        blocking_reasons.append(
            "Institutional analysis has fewer than "
            "3 confirmations."
        )

    # =====================================
    # 4. MARKET STRUCTURE
    # Maximum contribution: 10 points
    # =====================================

    structure_matches = directions_match(
        original_decision,
        structure_direction,
    )

    if (
        safe_bool(market_structure_confirmed)
        and structure_matches
    ):
        confluence_score += 6.0
        total_confirmations += 1

        confirmation_reasons.append(
            "Market structure supports the "
            "signal direction."
        )
    else:
        warnings.append(
            "Market structure is not fully aligned."
        )

    if safe_bool(bos_detected):
        confluence_score += 2.0
        total_confirmations += 1

        confirmation_reasons.append(
            "Break of Structure was detected."
        )

    if safe_bool(choch_detected):
        confluence_score += 2.0
        total_confirmations += 1

        confirmation_reasons.append(
            "Change of Character was detected."
        )

    # =====================================
    # 5. MULTI-TIMEFRAME ALIGNMENT
    # Maximum contribution: 10 points
    # =====================================

    timeframe_matches = directions_match(
        original_decision,
        timeframe_direction,
    )

    if (
        safe_bool(multi_timeframe_alignment)
        and timeframe_matches
    ):
        confluence_score += 10.0
        total_confirmations += 1

        confirmation_reasons.append(
            "Multiple timeframes are aligned "
            "with the signal direction."
        )
    else:
        warnings.append(
            "Multi-timeframe direction is "
            "not fully aligned."
        )

    # =====================================
    # 6. TREND ANALYSIS
    # Maximum contribution: 5 points
    # =====================================

    trend_matches = directions_match(
        original_decision,
        normalized_trend_direction,
    )

    if trend_matches:
        trend_points = (
            trend_score * 0.05
        )

        confluence_score += trend_points
        total_confirmations += 1

        confirmation_reasons.append(
            "Trend analysis supports the "
            "signal direction."
        )
    else:
        warnings.append(
            "Trend direction does not support "
            "the original signal."
        )

    # =====================================
    # 7. SUPPORT AND RESISTANCE
    # Maximum contribution: 3 points
    # =====================================

    if safe_bool(
        support_resistance_confirmed
    ):
        confluence_score += 3.0
        total_confirmations += 1

        confirmation_reasons.append(
            "Support or resistance confirms "
            "the setup."
        )

    # =====================================
    # 8. CANDLESTICK CONFIRMATION
    # Maximum contribution: 3 points
    # =====================================

    candlestick_matches = directions_match(
        original_decision,
        normalized_candlestick_direction,
    )

    if (
        safe_bool(candlestick_confirmed)
        and candlestick_matches
    ):
        confluence_score += 3.0
        total_confirmations += 1

        confirmation_reasons.append(
            "Candlestick confirmation supports "
            "the signal direction."
        )

    # =====================================
    # 9. BREAKOUT CONFIRMATION
    # Maximum contribution: 2 points
    # =====================================

    if safe_bool(breakout_confirmed):
        confluence_score += 2.0
        total_confirmations += 1

        confirmation_reasons.append(
            "Breakout confirmation is present."
        )

    # =====================================
    # 10. RISK MANAGEMENT
    # Maximum contribution: 2 points
    # =====================================

    risk_management_approved = (
        reward_risk >= MINIMUM_RISK_REWARD_RATIO
        and safe_bool(stop_loss_valid)
        and safe_bool(take_profit_valid)
    )

    if risk_management_approved:
        confluence_score += 2.0
        total_confirmations += 1

        confirmation_reasons.append(
            "Risk-management requirements "
            "are satisfied."
        )
    else:
        blocking_reasons.append(
            "Risk-management requirements "
            "are not fully satisfied."
        )

    confluence_score = clamp(
        confluence_score
    )

    # =====================================
    # FINAL SAFETY REQUIREMENTS
    # =====================================

    if (
        total_confirmations
        < MINIMUM_TOTAL_CONFIRMATIONS
    ):
        blocking_reasons.append(
            "Total confirmation count is below "
            "the minimum required count of 3."
        )

    if (
        confluence_score
        < MINIMUM_CONFLUENCE_SCORE
    ):
        blocking_reasons.append(
            "AI confluence score is below "
            "the minimum required score of 75."
        )

    major_direction_alignment = all(
        [
            context_direction_matches,
            institutional_direction_matches,
        ]
    )

    if not major_direction_alignment:
        blocking_reasons.append(
            "Major analysis engines are not "
            "directionally aligned."
        )

    final_approved = all(
        [
            original_decision in {
                BUY,
                SELL,
            },
            confidence
            >= MINIMUM_FINAL_CONFIDENCE,
            base_confirmations
            >= MINIMUM_TOTAL_CONFIRMATIONS,
            safe_bool(context_approved),
            safe_bool(context_supports_trade),
            risk_environment != "HIGH",
            signal_quality != "WEAK",
            safe_bool(institutional_approved),
            institutional_score_value >= MINIMUM_INSTITUTIONAL_SCORE,
            institutional_confirmation_count >= MINIMUM_INSTITUTIONAL_CONFIRMATIONS,
            institutional_direction_matches,
            context_direction_matches,
            risk_management_approved,
            total_confirmations
            >= MINIMUM_TOTAL_CONFIRMATIONS,
            confluence_score
            >= MINIMUM_CONFLUENCE_SCORE,
        ]
    )

    if final_approved:
        final_decision = original_decision
    else:
        final_decision = WAIT

    # Remove duplicate messages while keeping order
    blocking_reasons = list(
        dict.fromkeys(blocking_reasons)
    )

    confirmation_reasons = list(
        dict.fromkeys(confirmation_reasons)
    )

    warnings = list(
        dict.fromkeys(warnings)
    )

    return {
        "status": "success",
        "project": "Blue-Trading-AI",
        "safety_version": 16,
        "original_decision": original_decision,
        "final_decision": final_decision,
        "decision_approved": final_approved,
        "final_confidence": round(
            confidence,
            2,
        ),
        "ai_confluence_score": round(
            confluence_score,
            2,
        ),
        "confluence_strength": (
            calculate_strength(
                confluence_score
            )
        ),
        "final_trade_grade": calculate_grade(
            confluence_score
        ),
        "total_confirmations": (
            total_confirmations
        ),
        "confirmation_reasons": (
            confirmation_reasons
        ),
        "blocking_reasons": blocking_reasons,
        "warnings": warnings,
        "engine_alignment": {
            "context_direction_matches": (
                context_direction_matches
            ),
            "institutional_direction_matches": (
                institutional_direction_matches
            ),
            "market_structure_matches": (
                structure_matches
            ),
            "multi_timeframe_matches": (
                timeframe_matches
            ),
            "trend_matches": trend_matches,
            "candlestick_matches": (
                candlestick_matches
            ),
            "major_direction_alignment": (
                major_direction_alignment
            ),
        },
        "risk_management": {
            "risk_reward_ratio": round(
                reward_risk,
                2,
            ),
            "minimum_risk_reward_ratio": MINIMUM_RISK_REWARD_RATIO,
            "stop_loss_valid": safe_bool(
                stop_loss_valid
            ),
            "take_profit_valid": safe_bool(
                take_profit_valid
            ),
            "risk_management_approved": (
                risk_management_approved
            ),
        },
        "component_results": {
            "decision_intelligence": {
                "decision": original_decision,
                "confidence": round(
                    confidence,
                    2,
                ),
                "confirmations": (
                    base_confirmations
                ),
            },
            "market_context": {
                "decision": (
                    normalized_context_decision
                ),
                "approved": safe_bool(
                    context_approved
                ),
                "supports_trade": safe_bool(
                    context_supports_trade
                ),
                "risk_environment": (
                    risk_environment
                ),
                "signal_quality": (
                    signal_quality
                ),
            },
            "institutional_smc": {
                "decision": (
                    normalized_institutional_decision
                ),
                "approved": safe_bool(
                    institutional_approved
                ),
                "score": round(
                    institutional_score_value,
                    2,
                ),
                "confirmations": (
                    institutional_confirmation_count
                ),
            },
            "market_structure": {
                "direction": structure_direction,
                "confirmed": safe_bool(
                    market_structure_confirmed
                ),
                "bos_detected": safe_bool(
                    bos_detected
                ),
                "choch_detected": safe_bool(
                    choch_detected
                ),
            },
            "multi_timeframe": {
                "direction": timeframe_direction,
                "aligned": safe_bool(
                    multi_timeframe_alignment
                ),
            },
            "trend": {
                "direction": (
                    normalized_trend_direction
                ),
                "strength_score": round(
                    trend_score,
                    2,
                ),
            },
        },
        "safety_rules": {
            "minimum_final_confidence": (
                MINIMUM_FINAL_CONFIDENCE
            ),
            "minimum_total_confirmations": (
                MINIMUM_TOTAL_CONFIRMATIONS
            ),
            "minimum_confluence_score": (
                MINIMUM_CONFLUENCE_SCORE
            ),
            "minimum_institutional_score": MINIMUM_INSTITUTIONAL_SCORE,
            "minimum_risk_reward_ratio": MINIMUM_RISK_REWARD_RATIO,
            "context_approval_required": True,
            "institutional_approval_required": True,
            "direction_alignment_required": True,
            "risk_management_required": True,
            "broker_connection_enabled": False,
            "trade_execution_enabled": False,
        },
        "important_notice": (
            "Blue-Trading-AI provides market "
            "analysis and signals only. It does "
            "not connect to brokers or execute trades."
        ),
    }

__all__ = [
    "ALLOWED_DIRECTIONS",
    "BUY",
    "MAXIMUM_CONFIRMATIONS_PER_COMPONENT",
    "MINIMUM_CONFLUENCE_SCORE",
    "MINIMUM_FINAL_CONFIDENCE",
    "MINIMUM_INSTITUTIONAL_CONFIRMATIONS",
    "MINIMUM_INSTITUTIONAL_SCORE",
    "MINIMUM_RISK_REWARD_RATIO",
    "MINIMUM_TOTAL_CONFIRMATIONS",
    "SELL",
    "WAIT",
    "calculate_grade",
    "calculate_strength",
    "clamp",
    "directions_match",
    "evaluate_ai_confluence",
    "normalize_direction",
    "safe_bool",
    "safe_float",
    "safe_int",
]