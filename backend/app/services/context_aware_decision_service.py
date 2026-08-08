from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Final

from app.services.market_context_service import (
    analyze_market_context,
)


MINIMUM_CONFIDENCE: Final = 80.0
MINIMUM_CONFIRMATIONS: Final = 3
MAXIMUM_CONFIRMATIONS: Final = 100

BUY_DECISION: Final = "BUY"
SELL_DECISION: Final = "SELL"
WAIT_DECISION: Final = "WAIT"

HIGH_RISK: Final = "HIGH"
WEAK_QUALITY: Final = "WEAK"


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


def normalize_decision(
    decision: Any,
) -> str:
    """
    Convert a decision into a supported
    Blue-Trading-AI decision.
    """

    normalized = str(
        decision or WAIT_DECISION
    ).strip().upper()

    if normalized in {
        BUY_DECISION,
        SELL_DECISION,
        WAIT_DECISION,
    }:
        return normalized

    return WAIT_DECISION


def get_decision_value(
    decision_result: dict[str, Any],
    possible_keys: list[str],
    default: Any,
) -> Any:
    """
    Retrieve a value from the decision result
    using multiple possible key names.
    """

    for key in possible_keys:
        if key in decision_result:
            return decision_result[key]

    return default


def evaluate_context_aware_decision(
    decision_result: dict[str, Any],
    trend_score: Any,
    volatility_score: Any,
    conflicting_factors_count: Any = 0,
    current_datetime: datetime | None = None,
) -> dict[str, Any]:
    """
    Combine a Decision Intelligence result
    with the current Market Context result.

    Blue-Trading-AI remains an analysis and signal
    platform only. This function cannot execute trades.
    """

    if not isinstance(
        decision_result,
        dict,
    ):
        decision_result = {}

    original_decision = normalize_decision(
        get_decision_value(
            decision_result=decision_result,
            possible_keys=[
                "decision",
                "signal",
                "final_decision",
                "trade_decision",
            ],
            default=WAIT_DECISION,
        )
    )

    confidence = min(
        max(
            safe_float(
                get_decision_value(
                    decision_result=decision_result,
                    possible_keys=[
                        "confidence",
                        "confidence_score",
                        "decision_confidence",
                    ],
                    default=0.0,
                )
            ),
            0.0,
        ),
        100.0,
    )

    confirmations_count = safe_int(
        get_decision_value(
            decision_result=decision_result,
            possible_keys=[
                "confirmations",
                "confirmations_count",
                "confirmation_count",
            ],
            default=0,
        )
    )

    market_context = analyze_market_context(
        trend_score=trend_score,
        volatility_score=volatility_score,
        confidence=confidence,
        confirmations_count=confirmations_count,
        conflicting_factors_count=(
            conflicting_factors_count
        ),
        current_datetime=current_datetime,
    )

    if not isinstance(
        market_context,
        dict,
    ):
        market_context = {
            "risk_environment": HIGH_RISK,
            "signal_quality": WEAK_QUALITY,
            "context_supports_trade": False,
            "status": "error",
        }

    risk_environment = str(
        market_context.get(
            "risk_environment",
            HIGH_RISK,
        )
    ).strip().upper()

    signal_quality = str(
        market_context.get(
            "signal_quality",
            WEAK_QUALITY,
        )
    ).strip().upper()

    context_supports_trade = (
        market_context.get(
            "context_supports_trade"
        )
        is True
    )

    blocking_reasons: list[str] = []
    approval_reasons: list[str] = []

    final_decision = original_decision

    if original_decision == WAIT_DECISION:
        blocking_reasons.append(
            "The Decision Intelligence Engine "
            "returned WAIT."
        )

    if confidence < MINIMUM_CONFIDENCE:
        blocking_reasons.append(
            "Decision confidence is below the "
            "minimum required level of 80."
        )

    if confirmations_count < MINIMUM_CONFIRMATIONS:
        blocking_reasons.append(
            "The decision has fewer than the "
            "required 3 confirmations."
        )

    if risk_environment == HIGH_RISK:
        blocking_reasons.append(
            "The current market context is "
            "classified as HIGH risk."
        )

    if signal_quality == WEAK_QUALITY:
        blocking_reasons.append(
            "The market-context signal quality "
            "is classified as WEAK."
        )

    if not context_supports_trade:
        blocking_reasons.append(
            "The current market context does "
            "not support the trade signal."
        )

    if blocking_reasons:
        final_decision = WAIT_DECISION
    else:
        approval_reasons.extend(
            [
                (
                    "Decision confidence meets the "
                    "minimum requirement."
                ),
                (
                    "Confirmation count meets the "
                    "minimum requirement."
                ),
                (
                    "Market risk is not classified "
                    "as HIGH."
                ),
                (
                    "Market-context quality is not "
                    "classified as WEAK."
                ),
                (
                    "The market context supports "
                    "the original decision."
                ),
            ]
        )

    blocking_reasons = list(
        dict.fromkeys(
            blocking_reasons
        )
    )

    decision_approved = (
        final_decision
        in {
            BUY_DECISION,
            SELL_DECISION,
        }
        and not blocking_reasons
    )

    return {
        "status": "success",
        "project": "Blue-Trading-AI",
        "safety_version": 14,
        "original_decision": original_decision,
        "final_decision": final_decision,
        "decision_approved": decision_approved,
        "confidence": round(
            confidence,
            2,
        ),
        "confirmations_count": confirmations_count,
        "market_context": market_context,
        "blocking_reasons": blocking_reasons,
        "approval_reasons": approval_reasons,
        "safety_checks": {
            "minimum_confidence": (
                MINIMUM_CONFIDENCE
            ),
            "minimum_confirmations": (
                MINIMUM_CONFIRMATIONS
            ),
            "confidence_requirement_met": (
                confidence
                >= MINIMUM_CONFIDENCE
            ),
            "confirmation_requirement_met": (
                confirmations_count
                >= MINIMUM_CONFIRMATIONS
            ),
            "high_risk_context_detected": (
                risk_environment
                == HIGH_RISK
            ),
            "weak_signal_quality_detected": (
                signal_quality
                == WEAK_QUALITY
            ),
            "context_supports_trade": (
                context_supports_trade
            ),
            "broker_connection_enabled": False,
            "trade_execution_enabled": False,
        },
        "important_notice": (
            "Blue-Trading-AI provides market "
            "analysis and signals only. It does "
            "not connect to brokers or execute "
            "trades."
        ),
    }


__all__ = [
    "BUY_DECISION",
    "HIGH_RISK",
    "MAXIMUM_CONFIRMATIONS",
    "MINIMUM_CONFIDENCE",
    "MINIMUM_CONFIRMATIONS",
    "SELL_DECISION",
    "WAIT_DECISION",
    "WEAK_QUALITY",
    "evaluate_context_aware_decision",
    "get_decision_value",
    "normalize_decision",
    "safe_float",
    "safe_int",
]