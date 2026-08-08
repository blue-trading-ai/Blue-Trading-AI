from __future__ import annotations

import math
from typing import Any, Final


BUY: Final = "BUY"
SELL: Final = "SELL"
WAIT: Final = "WAIT"

MINIMUM_APPROVAL_CONFIDENCE: Final = 80.0
MINIMUM_RANKING_SCORE: Final = 75.0
MINIMUM_CONFIRMATIONS: Final = 3
MINIMUM_RISK_REWARD_RATIO: Final = 1.5

MAXIMUM_CONFIDENCE: Final = 98.0
MAXIMUM_CONFIDENCE_INCREASE: Final = 8.0
MAXIMUM_CONFIRMATIONS: Final = 100
MAXIMUM_SIGNAL_BATCH_SIZE: Final = 100

SUPPORTED_DECISIONS: Final[frozenset[str]] = frozenset(
    {
        BUY,
        SELL,
        WAIT,
    }
)


COMPONENT_WEIGHTS: Final[dict[str, float]] = {
    "base_confidence": 0.12,
    "ai_confluence": 0.20,
    "multi_timeframe": 0.17,
    "institutional": 0.13,
    "market_context": 0.08,
    "market_structure": 0.08,
    "trend": 0.06,
    "momentum": 0.05,
    "risk_reward": 0.06,
    "confirmations": 0.05,
}


def validate_component_weights() -> None:
    """Validate the fixed Version 18 ranking-weight model."""

    total_weight = sum(
        COMPONENT_WEIGHTS.values()
    )

    if not math.isclose(
        total_weight,
        1.0,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise RuntimeError(
            "Dynamic-confidence component weights must total 1.0."
        )

    for component, weight in COMPONENT_WEIGHTS.items():
        if not component:
            raise RuntimeError(
                "Dynamic-confidence component names cannot be empty."
            )

        if (
            not math.isfinite(weight)
            or weight < 0.0
        ):
            raise RuntimeError(
                "Dynamic-confidence component weights must be finite "
                "and non-negative."
            )


validate_component_weights()


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


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    """Safely convert a value into a bounded non-negative integer."""

    if isinstance(value, bool):
        return default

    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return default

    return min(
        max(
            number,
            0,
        ),
        MAXIMUM_CONFIRMATIONS,
    )


def safe_bool(
    value: Any,
) -> bool:
    """
    Safely converts a value into a boolean.
    """

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in {
            "true",
            "1",
            "yes",
            "approved",
            "confirmed",
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
    Restricts a value between minimum and maximum.
    """

    number = safe_float(value)

    return max(
        minimum,
        min(number, maximum),
    )


def normalize_decision(
    value: Any,
) -> str:
    """
    Normalizes signal direction.
    """

    decision = str(
        value or WAIT
    ).strip().upper()

    if decision in {
        BUY,
        "BULLISH",
        "LONG",
    }:
        return BUY

    if decision in {
        SELL,
        "BEARISH",
        "SHORT",
    }:
        return SELL

    return WAIT


def calculate_grade(
    score: Any,
) -> str:
    """
    Converts a score into a signal grade.
    """

    value = clamp(score)

    if value >= 92.0:
        return "A+"

    if value >= 86.0:
        return "A"

    if value >= 80.0:
        return "B+"

    if value >= 75.0:
        return "B"

    if value >= 65.0:
        return "C"

    return "REJECTED"


def calculate_strength(
    score: Any,
) -> str:
    """
    Converts a score into a strength label.
    """

    value = clamp(score)

    if value >= 92.0:
        return "ELITE"

    if value >= 85.0:
        return "VERY_STRONG"

    if value >= 80.0:
        return "STRONG"

    if value >= 75.0:
        return "MODERATE"

    return "WEAK"


def calculate_risk_reward_score(
    risk_reward_ratio: Any,
) -> float:
    """
    Converts risk-reward ratio into a score.
    """

    rr = safe_float(
        risk_reward_ratio
    )

    if rr >= 3.0:
        return 100.0

    if rr >= 2.5:
        return 92.0

    if rr >= 2.0:
        return 85.0

    if rr >= 1.5:
        return 75.0

    if rr >= 1.0:
        return 55.0

    return 25.0


def calculate_confirmation_score(
    confirmations: Any,
) -> float:
    """
    Converts confirmation count into a score.

    The score is capped to prevent confidence inflation.
    """

    count = max(
        0,
        safe_int(confirmations),
    )

    if count >= 10:
        return 100.0

    if count >= 8:
        return 94.0

    if count >= 6:
        return 88.0

    if count >= 5:
        return 84.0

    if count >= 4:
        return 80.0

    if count >= 3:
        return 75.0

    if count == 2:
        return 55.0

    if count == 1:
        return 35.0

    return 0.0


def evaluate_dynamic_confidence(
    signal_id: Any,
    symbol: Any,
    timeframe: Any,
    decision: Any,
    base_confidence: Any,
    confirmations: Any,
    ai_confluence_score: Any,
    multi_timeframe_score: Any,
    institutional_score: Any,
    context_score: Any,
    market_structure_score: Any,
    trend_score: Any,
    momentum_score: Any,
    risk_reward_ratio: Any,
    context_approved: Any,
    institutional_approved: Any,
    multi_timeframe_approved: Any,
    risk_management_approved: Any,
    direction_alignment: Any,
    hierarchy_conflict: Any = False,
    high_risk_environment: Any = False,
    weak_signal_quality: Any = False,
    blocking_reasons: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """
    Calculates the final dynamic confidence and
    ranking score for one trading signal.

    This service performs analysis and signal ranking
    only. It does not connect to brokers or execute trades.
    """

    normalized_decision = normalize_decision(
        decision
    )

    normalized_symbol = str(
        symbol or "UNKNOWN"
    ).strip().upper()

    normalized_timeframe = str(
        timeframe or "UNKNOWN"
    ).strip().upper()

    original_confidence = clamp(
        base_confidence
    )

    confirmation_count = max(
        0,
        safe_int(confirmations),
    )

    confluence_value = clamp(
        ai_confluence_score
    )

    multi_timeframe_value = clamp(
        multi_timeframe_score
    )

    institutional_value = clamp(
        institutional_score
    )

    context_value = clamp(
        context_score
    )

    structure_value = clamp(
        market_structure_score
    )

    trend_value = clamp(
        trend_score
    )

    momentum_value = clamp(
        momentum_score
    )

    rr_value = max(
        0.0,
        safe_float(risk_reward_ratio),
    )

    rr_score = calculate_risk_reward_score(
        rr_value
    )

    confirmation_score = calculate_confirmation_score(
        confirmation_count
    )

    context_is_approved = safe_bool(
        context_approved
    )

    institutional_is_approved = safe_bool(
        institutional_approved
    )

    multi_timeframe_is_approved = safe_bool(
        multi_timeframe_approved
    )

    risk_is_approved = safe_bool(
        risk_management_approved
    )

    direction_is_aligned = safe_bool(
        direction_alignment
    )

    hierarchy_has_conflict = safe_bool(
        hierarchy_conflict
    )

    environment_is_high_risk = safe_bool(
        high_risk_environment
    )

    quality_is_weak = safe_bool(
        weak_signal_quality
    )

    received_blocking_reasons = [
        str(reason).strip()
        for reason in (
            blocking_reasons or []
        )
        if str(reason).strip()
    ][:100]

    received_warnings = [
        str(warning).strip()
        for warning in (
            warnings or []
        )
        if str(warning).strip()
    ][:100]

    approval_score = 0.0

    approval_checks = [
        context_is_approved,
        institutional_is_approved,
        multi_timeframe_is_approved,
        risk_is_approved,
        direction_is_aligned,
    ]

    passed_approval_checks = sum(
        1
        for check in approval_checks
        if check
    )

    approval_score = (
        passed_approval_checks
        / len(approval_checks)
    ) * 100.0

    component_weights = COMPONENT_WEIGHTS

    raw_ranking_score = (
        original_confidence
        * component_weights["base_confidence"]
        + confluence_value
        * component_weights["ai_confluence"]
        + multi_timeframe_value
        * component_weights["multi_timeframe"]
        + institutional_value
        * component_weights["institutional"]
        + context_value
        * component_weights["market_context"]
        + structure_value
        * component_weights["market_structure"]
        + trend_value
        * component_weights["trend"]
        + momentum_value
        * component_weights["momentum"]
        + rr_score
        * component_weights["risk_reward"]
        + confirmation_score
        * component_weights["confirmations"]
    )

    positive_adjustments: list[dict[str, Any]] = []
    penalties: list[dict[str, Any]] = []
    confirmation_reasons: list[str] = []
    final_blocking_reasons = list(
        received_blocking_reasons
    )
    final_warnings = list(
        received_warnings
    )

    confidence_adjustment = 0.0
    total_penalty = 0.0

    if confluence_value >= 90.0:
        confidence_adjustment += 2.0

        positive_adjustments.append(
            {
                "reason": (
                    "AI confluence score is very strong."
                ),
                "value": 2.0,
            }
        )

        confirmation_reasons.append(
            "AI Confluence Engine strongly supports the signal."
        )

    elif confluence_value >= 80.0:
        confidence_adjustment += 1.0

        positive_adjustments.append(
            {
                "reason": (
                    "AI confluence score supports the signal."
                ),
                "value": 1.0,
            }
        )

    if multi_timeframe_value >= 90.0:
        confidence_adjustment += 2.0

        positive_adjustments.append(
            {
                "reason": (
                    "Multi-timeframe alignment is very strong."
                ),
                "value": 2.0,
            }
        )

        confirmation_reasons.append(
            "Multi-timeframe direction is strongly aligned."
        )

    elif multi_timeframe_value >= 80.0:
        confidence_adjustment += 1.0

        positive_adjustments.append(
            {
                "reason": (
                    "Multi-timeframe alignment supports the signal."
                ),
                "value": 1.0,
            }
        )

    if institutional_value >= 85.0:
        confidence_adjustment += 1.5

        positive_adjustments.append(
            {
                "reason": (
                    "Institutional Smart Money score is strong."
                ),
                "value": 1.5,
            }
        )

        confirmation_reasons.append(
            "Institutional Smart Money analysis supports the signal."
        )

    if rr_value >= 2.0:
        confidence_adjustment += 1.0

        positive_adjustments.append(
            {
                "reason": (
                    "Risk-reward ratio is at least 2.0."
                ),
                "value": 1.0,
            }
        )

        confirmation_reasons.append(
            "Risk-reward ratio supports the setup."
        )

    if confirmation_count >= 5:
        confidence_adjustment += 1.0

        positive_adjustments.append(
            {
                "reason": (
                    "Signal has at least 5 confirmations."
                ),
                "value": 1.0,
            }
        )

    confidence_adjustment = min(
        confidence_adjustment,
        MAXIMUM_CONFIDENCE_INCREASE,
    )

    if normalized_decision == WAIT:
        total_penalty += 30.0

        penalties.append(
            {
                "reason": (
                    "Original signal decision is WAIT."
                ),
                "value": 30.0,
            }
        )

        final_blocking_reasons.append(
            "Original signal decision is WAIT."
        )

    if not context_is_approved:
        total_penalty += 12.0

        penalties.append(
            {
                "reason": (
                    "Market context is not approved."
                ),
                "value": 12.0,
            }
        )

        final_blocking_reasons.append(
            "Market context approval is required."
        )

    if not institutional_is_approved:
        total_penalty += 14.0

        penalties.append(
            {
                "reason": (
                    "Institutional analysis is not approved."
                ),
                "value": 14.0,
            }
        )

        final_blocking_reasons.append(
            "Institutional Smart Money approval is required."
        )

    if not multi_timeframe_is_approved:
        total_penalty += 16.0

        penalties.append(
            {
                "reason": (
                    "Multi-timeframe analysis is not approved."
                ),
                "value": 16.0,
            }
        )

        final_blocking_reasons.append(
            "Multi-timeframe approval is required."
        )

    if not risk_is_approved:
        total_penalty += 18.0

        penalties.append(
            {
                "reason": (
                    "Risk management is not approved."
                ),
                "value": 18.0,
            }
        )

        final_blocking_reasons.append(
            "Risk-management approval is required."
        )

    if not direction_is_aligned:
        total_penalty += 18.0

        penalties.append(
            {
                "reason": (
                    "Major engine directions are not aligned."
                ),
                "value": 18.0,
            }
        )

        final_blocking_reasons.append(
            "Major direction alignment is required."
        )

    if hierarchy_has_conflict:
        total_penalty += 20.0

        penalties.append(
            {
                "reason": (
                    "Higher and lower timeframe hierarchy conflicts."
                ),
                "value": 20.0,
            }
        )

        final_blocking_reasons.append(
            "Timeframe hierarchy conflict blocks the signal."
        )

    if environment_is_high_risk:
        total_penalty += 15.0

        penalties.append(
            {
                "reason": (
                    "Market environment is classified as high risk."
                ),
                "value": 15.0,
            }
        )

        final_blocking_reasons.append(
            "High-risk market environment blocks the signal."
        )

    if quality_is_weak:
        total_penalty += 12.0

        penalties.append(
            {
                "reason": (
                    "Signal quality is classified as weak."
                ),
                "value": 12.0,
            }
        )

        final_blocking_reasons.append(
            "Weak signal quality blocks the signal."
        )

    if confirmation_count < MINIMUM_CONFIRMATIONS:
        total_penalty += 15.0

        penalties.append(
            {
                "reason": (
                    "Signal has fewer than 3 confirmations."
                ),
                "value": 15.0,
            }
        )

        final_blocking_reasons.append(
            "At least 3 confirmations are required."
        )

    if rr_value < MINIMUM_RISK_REWARD_RATIO:
        total_penalty += 15.0

        penalties.append(
            {
                "reason": (
                    "Risk-reward ratio is below 1.5."
                ),
                "value": 15.0,
            }
        )

        final_blocking_reasons.append(
            "Minimum risk-reward ratio is 1.5."
        )

    if confluence_value < 75.0:
        total_penalty += 10.0

        penalties.append(
            {
                "reason": (
                    "AI confluence score is below 75."
                ),
                "value": 10.0,
            }
        )

        final_blocking_reasons.append(
            "AI confluence score is below the minimum requirement."
        )

    if multi_timeframe_value < 75.0:
        total_penalty += 12.0

        penalties.append(
            {
                "reason": (
                    "Multi-timeframe score is below 75."
                ),
                "value": 12.0,
            }
        )

        final_blocking_reasons.append(
            "Multi-timeframe score is below the minimum requirement."
        )

    adjusted_confidence_before_cap = (
        original_confidence
        + confidence_adjustment
        - total_penalty
    )

    dynamic_confidence = clamp(
        adjusted_confidence_before_cap,
        minimum=0.0,
        maximum=MAXIMUM_CONFIDENCE,
    )

    ranking_score = clamp(
        raw_ranking_score
        + confidence_adjustment
        - total_penalty
    )

    final_blocking_reasons = list(
        dict.fromkeys(
            final_blocking_reasons
        )
    )

    final_warnings = list(
        dict.fromkeys(
            final_warnings
        )
    )

    confirmation_reasons = list(
        dict.fromkeys(
            confirmation_reasons
        )
    )

    hard_safety_checks = all(
        [
            normalized_decision in {
                BUY,
                SELL,
            },
            context_is_approved,
            institutional_is_approved,
            multi_timeframe_is_approved,
            risk_is_approved,
            direction_is_aligned,
            not hierarchy_has_conflict,
            not environment_is_high_risk,
            not quality_is_weak,
            confirmation_count
            >= MINIMUM_CONFIRMATIONS,
            rr_value
            >= MINIMUM_RISK_REWARD_RATIO,
            confluence_value >= 75.0,
            multi_timeframe_value >= 75.0,
        ]
    )

    signal_approved = all(
        [
            hard_safety_checks,
            dynamic_confidence
            >= MINIMUM_APPROVAL_CONFIDENCE,
            ranking_score
            >= MINIMUM_RANKING_SCORE,
            len(final_blocking_reasons) == 0,
        ]
    )

    final_decision = (
        normalized_decision
        if signal_approved
        else WAIT
    )

    signal_grade = calculate_grade(
        ranking_score
    )

    signal_strength = calculate_strength(
        ranking_score
    )

    return {
        "status": "success",
        "project": "Blue-Trading-AI",
        "safety_version": 18,
        "signal_id": str(
            signal_id or ""
        ).strip()[:128],
        "symbol": normalized_symbol,
        "timeframe": normalized_timeframe,
        "original_decision": normalized_decision,
        "final_decision": final_decision,
        "signal_approved": signal_approved,
        "base_confidence": round(
            original_confidence,
            2,
        ),
        "dynamic_confidence": round(
            dynamic_confidence,
            2,
        ),
        "confidence_adjustment": round(
            confidence_adjustment,
            2,
        ),
        "total_penalty": round(
            total_penalty,
            2,
        ),
        "ranking_score": round(
            ranking_score,
            2,
        ),
        "signal_grade": signal_grade,
        "signal_strength": signal_strength,
        "confirmation_count": confirmation_count,
        "approval_score": round(
            approval_score,
            2,
        ),
        "risk_reward_ratio": round(
            rr_value,
            2,
        ),
        "confirmation_reasons": confirmation_reasons,
        "blocking_reasons": final_blocking_reasons,
        "warnings": final_warnings,
        "positive_adjustments": positive_adjustments,
        "penalties": penalties,
        "component_scores": {
            "base_confidence": round(
                original_confidence,
                2,
            ),
            "ai_confluence_score": round(
                confluence_value,
                2,
            ),
            "multi_timeframe_score": round(
                multi_timeframe_value,
                2,
            ),
            "institutional_score": round(
                institutional_value,
                2,
            ),
            "context_score": round(
                context_value,
                2,
            ),
            "market_structure_score": round(
                structure_value,
                2,
            ),
            "trend_score": round(
                trend_value,
                2,
            ),
            "momentum_score": round(
                momentum_value,
                2,
            ),
            "risk_reward_score": round(
                rr_score,
                2,
            ),
            "confirmation_score": round(
                confirmation_score,
                2,
            ),
        },
        "approval_checks": {
            "context_approved": context_is_approved,
            "institutional_approved": (
                institutional_is_approved
            ),
            "multi_timeframe_approved": (
                multi_timeframe_is_approved
            ),
            "risk_management_approved": (
                risk_is_approved
            ),
            "direction_alignment": (
                direction_is_aligned
            ),
            "hierarchy_conflict": (
                hierarchy_has_conflict
            ),
            "high_risk_environment": (
                environment_is_high_risk
            ),
            "weak_signal_quality": (
                quality_is_weak
            ),
        },
        "safety_rules": {
            "minimum_approval_confidence": (
                MINIMUM_APPROVAL_CONFIDENCE
            ),
            "minimum_ranking_score": (
                MINIMUM_RANKING_SCORE
            ),
            "minimum_confirmations": (
                MINIMUM_CONFIRMATIONS
            ),
            "minimum_risk_reward_ratio": (
                MINIMUM_RISK_REWARD_RATIO
            ),
            "maximum_dynamic_confidence": (
                MAXIMUM_CONFIDENCE
            ),
            "maximum_confidence_increase": (
                MAXIMUM_CONFIDENCE_INCREASE
            ),
            "all_approvals_required": True,
            "hierarchy_conflict_blocks_signal": True,
            "high_risk_environment_blocks_signal": True,
            "weak_signal_quality_blocks_signal": True,
            "broker_connection_enabled": False,
            "trade_execution_enabled": False,
        },
        "important_notice": (
            "Blue-Trading-AI provides market analysis, "
            "confidence scoring and signal ranking only. "
            "It does not connect to brokers or execute trades."
        ),
    }


def rank_trading_signals(
    signals: list[dict[str, Any]],
    maximum_results: int = 10,
) -> dict[str, Any]:
    """
    Evaluate and rank multiple trading signals.

    Rejected signals remain visible but are ranked
    below approved signals.
    """

    if not isinstance(
        signals,
        list,
    ):
        signals = []

    bounded_signals = signals[
        :MAXIMUM_SIGNAL_BATCH_SIZE
    ]

    evaluated_signals: list[dict[str, Any]] = []

    for position, signal in enumerate(
        bounded_signals,
        start=1,
    ):
        if not isinstance(
            signal,
            dict,
        ):
            signal = {}
        evaluation = evaluate_dynamic_confidence(
            signal_id=signal.get(
                "signal_id",
                f"SIGNAL-{position}",
            ),
            symbol=signal.get(
                "symbol",
                "UNKNOWN",
            ),
            timeframe=signal.get(
                "timeframe",
                "UNKNOWN",
            ),
            decision=signal.get(
                "decision",
                WAIT,
            ),
            base_confidence=signal.get(
                "base_confidence",
                0.0,
            ),
            confirmations=signal.get(
                "confirmations",
                0,
            ),
            ai_confluence_score=signal.get(
                "ai_confluence_score",
                0.0,
            ),
            multi_timeframe_score=signal.get(
                "multi_timeframe_score",
                0.0,
            ),
            institutional_score=signal.get(
                "institutional_score",
                0.0,
            ),
            context_score=signal.get(
                "context_score",
                0.0,
            ),
            market_structure_score=signal.get(
                "market_structure_score",
                0.0,
            ),
            trend_score=signal.get(
                "trend_score",
                0.0,
            ),
            momentum_score=signal.get(
                "momentum_score",
                0.0,
            ),
            risk_reward_ratio=signal.get(
                "risk_reward_ratio",
                0.0,
            ),
            context_approved=signal.get(
                "context_approved",
                False,
            ),
            institutional_approved=signal.get(
                "institutional_approved",
                False,
            ),
            multi_timeframe_approved=signal.get(
                "multi_timeframe_approved",
                False,
            ),
            risk_management_approved=signal.get(
                "risk_management_approved",
                False,
            ),
            direction_alignment=signal.get(
                "direction_alignment",
                False,
            ),
            hierarchy_conflict=signal.get(
                "hierarchy_conflict",
                False,
            ),
            high_risk_environment=signal.get(
                "high_risk_environment",
                False,
            ),
            weak_signal_quality=signal.get(
                "weak_signal_quality",
                False,
            ),
            blocking_reasons=signal.get(
                "blocking_reasons",
                [],
            ),
            warnings=signal.get(
                "warnings",
                [],
            ),
        )

        evaluated_signals.append(
            evaluation
        )

    evaluated_signals.sort(
        key=lambda item: (
            item["signal_approved"],
            item["ranking_score"],
            item["dynamic_confidence"],
            item["risk_reward_ratio"],
        ),
        reverse=True,
    )

    maximum_results = max(
        1,
        min(
            safe_int(
                maximum_results,
                10,
            ),
            100,
        ),
    )

    ranked_signals: list[dict[str, Any]] = []

    for rank, signal in enumerate(
        evaluated_signals[
            :maximum_results
        ],
        start=1,
    ):
        signal_with_rank = {
            **signal,
            "rank": rank,
        }

        ranked_signals.append(
            signal_with_rank
        )

    approved_signals = [
        signal
        for signal in ranked_signals
        if signal["signal_approved"]
    ]

    rejected_signals = [
        signal
        for signal in ranked_signals
        if not signal["signal_approved"]
    ]

    best_signal = (
        approved_signals[0]
        if approved_signals
        else None
    )

    return {
        "status": "success",
        "project": "Blue-Trading-AI",
        "safety_version": 18,
        "total_received": len(
            bounded_signals
        ),
        "total_ranked": len(
            ranked_signals
        ),
        "approved_signal_count": len(
            approved_signals
        ),
        "rejected_signal_count": len(
            rejected_signals
        ),
        "best_signal_available": (
            best_signal is not None
        ),
        "best_signal": best_signal,
        "ranked_signals": ranked_signals,
        "ranking_rules": {
            "approved_signals_rank_first": True,
            "ranking_score_priority": True,
            "dynamic_confidence_priority": True,
            "risk_reward_used_as_tiebreaker": True,
            "minimum_approval_confidence": (
                MINIMUM_APPROVAL_CONFIDENCE
            ),
            "minimum_ranking_score": (
                MINIMUM_RANKING_SCORE
            ),
            "maximum_results": (
                maximum_results
            ),
            "broker_connection_enabled": False,
            "trade_execution_enabled": False,
        },
        "important_notice": (
            "Blue-Trading-AI ranks analysis signals only. "
            "It does not connect to brokers or execute trades."
        ),
    }

__all__ = [
    "BUY",
    "COMPONENT_WEIGHTS",
    "MAXIMUM_CONFIDENCE",
    "MAXIMUM_CONFIDENCE_INCREASE",
    "MAXIMUM_CONFIRMATIONS",
    "MAXIMUM_SIGNAL_BATCH_SIZE",
    "MINIMUM_APPROVAL_CONFIDENCE",
    "MINIMUM_CONFIRMATIONS",
    "MINIMUM_RANKING_SCORE",
    "MINIMUM_RISK_REWARD_RATIO",
    "SELL",
    "SUPPORTED_DECISIONS",
    "WAIT",
    "calculate_confirmation_score",
    "calculate_grade",
    "calculate_risk_reward_score",
    "calculate_strength",
    "clamp",
    "evaluate_dynamic_confidence",
    "normalize_decision",
    "rank_trading_signals",
    "safe_bool",
    "safe_float",
    "safe_int",
    "validate_component_weights",
]