from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services.market_session_service import (
    apply_market_session_confidence,
)


# ============================================================
# BLUE-TRADING-AI
# VERSION 22
# MARKET SESSION SIGNAL INTEGRATION
# ============================================================


def integrate_market_session_into_signal(
    signal_result: dict[str, Any],
    *,
    symbol: str,
    current_datetime: datetime | None = None,
) -> dict[str, Any]:
    """
    Apply Market Session Intelligence
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

    session_result = apply_market_session_confidence(
        symbol=symbol,
        base_confidence=base_confidence,
        current_datetime=current_datetime,
    )

    confidence_result = session_result[
        "confidence_result"
    ]

    adjusted_confidence = confidence_result[
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

    session_passed = bool(
        confidence_result[
            "session_confidence_passed"
        ]
    )

    confirmations_passed = (
        confirmations >= 3
    )

    signal_approved = (
        session_passed
        and confirmations_passed
    )

    updated_signal = dict(signal_result)

    updated_signal["project"] = (
        "Blue-Trading-AI"
    )

    updated_signal["version"] = 22

    updated_signal[
        "base_confidence_before_session"
    ] = base_confidence

    updated_signal[
        "final_confidence"
    ] = adjusted_confidence

    updated_signal[
        "market_session_intelligence"
    ] = session_result[
        "session_analysis"
    ]

    updated_signal[
        "session_confidence_result"
    ] = confidence_result

    updated_signal[
        "minimum_required_confidence"
    ] = 80.0

    updated_signal[
        "minimum_required_confirmations"
    ] = 3

    updated_signal[
        "session_approval"
    ] = session_passed

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

        if not session_passed:

            reasons.append(
                "Final confidence below 80 after session adjustment."
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