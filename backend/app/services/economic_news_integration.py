from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services.economic_news_service import (
    apply_economic_news_confidence,
)


# ============================================================
# BLUE-TRADING-AI
# VERSION 23
# ECONOMIC NEWS SIGNAL INTEGRATION
# ============================================================


def integrate_economic_news_into_signal(
    signal_result: dict[str, Any],
    *,
    symbol: str,
    current_datetime: datetime | None = None,
) -> dict[str, Any]:
    """
    Apply Economic News Intelligence
    to the final trading signal.
    """

    base_confidence = float(
        signal_result.get(
            "final_confidence",
            signal_result.get(
                "confidence",
                0.0,
            ),
        )
    )

    news_result = apply_economic_news_confidence(
        symbol=symbol,
        base_confidence=base_confidence,
        current_datetime=current_datetime,
    )

    adjusted_confidence = news_result[
        "adjusted_confidence"
    ]

    confirmations = int(
        signal_result.get(
            "total_confirmations",
            signal_result.get(
                "confirmations",
                0,
            ),
        )
    )

    confidence_passed = bool(
        news_result[
            "confidence_passed"
        ]
    )

    news_approval = bool(
        news_result[
            "news_approval"
        ]
    )

    confirmations_passed = (
        confirmations >= 3
    )

    signal_approved = (
        confidence_passed
        and news_approval
        and confirmations_passed
    )

    updated_signal = dict(signal_result)

    updated_signal["project"] = (
        "Blue-Trading-AI"
    )

    updated_signal["version"] = 23

    updated_signal[
        "base_confidence_before_news"
    ] = base_confidence

    updated_signal[
        "final_confidence"
    ] = adjusted_confidence

    updated_signal[
        "economic_news"
    ] = news_result[
        "news_analysis"
    ]

    updated_signal[
        "economic_news_result"
    ] = news_result

    updated_signal[
        "minimum_required_confidence"
    ] = 80.0

    updated_signal[
        "minimum_required_confirmations"
    ] = 3

    updated_signal[
        "news_approval"
    ] = news_approval

    updated_signal[
        "confirmations_approval"
    ] = confirmations_passed

    updated_signal[
        "signal_approved"
    ] = signal_approved

    if not signal_approved:

        updated_signal["signal"] = (
            "NO_TRADE"
        )

        updated_signal["decision"] = (
            "WAIT"
        )

        reasons = list(
            updated_signal.get(
                "blocking_reasons",
                [],
            )
        )

        if not confidence_passed:

            reasons.append(
                "Final confidence below 80 after economic news adjustment."
            )

        if not news_approval:

            reasons.append(
                "Economic news filter blocked this signal."
            )

        if not confirmations_passed:

            reasons.append(
                "Less than 3 confirmations."
            )

        updated_signal[
            "blocking_reasons"
        ] = reasons

    updated_signal[
        "analysis_only"
    ] = True

    updated_signal[
        "broker_connection_enabled"
    ] = False

    updated_signal[
        "trade_execution_enabled"
    ] = False

    return updated_signal