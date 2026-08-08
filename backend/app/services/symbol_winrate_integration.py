"""
Blue-Trading-AI
Version 26
Symbol Win Rate Integration
"""

from __future__ import annotations

import math
from typing import Any, Dict, Final, Iterable, Mapping

from app.services.symbol_winrate_service import (
    SymbolWinRateDecision,
    apply_symbol_winrate_confidence,
    normalize_symbol,
    symbol_winrate_intelligence,
)


SAFETY_VERSION: Final[int] = 26
MAXIMUM_SIGNAL_KEYS: Final[int] = 500
MAXIMUM_RECORDS: Final[int] = 100_000


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        resolved = float(
            value
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        try:
            resolved = float(
                default
            )
        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            resolved = 0.0

    if not math.isfinite(
        resolved
    ):
        try:
            fallback = float(
                default
            )
        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            fallback = 0.0

        return (
            fallback
            if math.isfinite(
                fallback
            )
            else 0.0
        )

    return resolved


def _normalise_trade_records(
    trade_records: Any,
) -> Iterable[Any]:
    if trade_records is None:
        return symbol_winrate_intelligence.get_records()

    try:
        iterator = iter(
            trade_records
        )
    except TypeError as exc:
        raise ValueError(
            "trade_records must be iterable."
        ) from exc

    records: list[Any] = []

    for index, record in enumerate(
        iterator
    ):
        if index >= MAXIMUM_RECORDS:
            break

        records.append(
            record
        )

    return records


def _validate_decision(
    decision: Any,
) -> SymbolWinRateDecision:
    if isinstance(
        decision,
        SymbolWinRateDecision,
    ):
        return decision

    required_attributes = (
        "symbol",
        "original_confidence",
        "confidence_adjustment",
        "adjusted_confidence",
        "applied",
        "reason",
        "statistics",
    )

    if decision is None or any(
        not hasattr(
            decision,
            attribute,
        )
        for attribute in required_attributes
    ):
        raise ValueError(
            "Symbol win-rate service returned an invalid decision."
        )

    return decision


def integrate_symbol_winrate(
    *,
    symbol: str,
    confidence: float,
    trade_records: Any = None,
) -> Dict[str, Any]:
    """Integrate symbol win-rate intelligence into the signal pipeline."""

    resolved_symbol = normalize_symbol(
        symbol
    )

    if not resolved_symbol:
        raise ValueError(
            "A valid symbol is required."
        )

    resolved_confidence = max(
        0.0,
        min(
            100.0,
            _safe_float(
                confidence
            ),
        ),
    )

    resolved_trade_records = (
        _normalise_trade_records(
            trade_records
        )
    )

    decision = _validate_decision(
        apply_symbol_winrate_confidence(
            symbol=resolved_symbol,
            original_confidence=resolved_confidence,
            trade_records=resolved_trade_records,
        )
    )

    statistics = decision.statistics

    if statistics is None or not hasattr(
        statistics,
        "to_dict",
    ):
        raise ValueError(
            "Symbol win-rate statistics response is invalid."
        )

    statistics_payload = (
        statistics.to_dict()
    )

    if not isinstance(
        statistics_payload,
        dict,
    ):
        raise ValueError(
            "Symbol win-rate statistics payload is invalid."
        )

    return {
        "status": "success",
        "module": "Symbol Win Rate Integration",
        "safety_version": SAFETY_VERSION,
        "symbol": decision.symbol,
        "symbol_winrate_approved": True,
        "confidence_before": (
            decision.original_confidence
        ),
        "confidence_adjustment": (
            decision.confidence_adjustment
        ),
        "confidence_after": (
            decision.adjusted_confidence
        ),
        "adjustment_applied": bool(
            decision.applied
        ),
        "reason": str(
            decision.reason
        ),
        "statistics": statistics_payload,
    }


def evaluate_symbol_winrate(
    *,
    signal: Dict[str, Any],
    trade_records: Any = None,
) -> Dict[str, Any]:
    """Apply symbol win-rate intelligence to an existing signal dictionary."""

    if not isinstance(
        signal,
        Mapping,
    ):
        raise ValueError(
            "signal must be a mapping."
        )

    if len(
        signal
    ) > MAXIMUM_SIGNAL_KEYS:
        raise ValueError(
            "signal contains too many top-level fields."
        )

    updated = dict(
        signal
    )

    result = integrate_symbol_winrate(
        symbol=str(
            updated.get(
                "symbol",
                "",
            )
            or ""
        ),
        confidence=_safe_float(
            updated.get(
                "confidence",
                updated.get(
                    "confidence_score",
                    updated.get(
                        "final_confidence",
                        0.0,
                    ),
                ),
            )
        ),
        trade_records=trade_records,
    )

    confidence_after = max(
        0.0,
        min(
            100.0,
            _safe_float(
                result.get(
                    "confidence_after",
                    0.0,
                )
            ),
        ),
    )

    updated[
        "confidence"
    ] = confidence_after
    updated[
        "confidence_score"
    ] = confidence_after
    updated[
        "symbol"
    ] = result[
        "symbol"
    ]
    updated[
        "symbol_winrate"
    ] = result
    updated[
        "symbol_winrate_applied"
    ] = bool(
        result.get(
            "adjustment_applied",
            False,
        )
    )
    updated[
        "symbol_winrate_safety_version"
    ] = SAFETY_VERSION
    updated[
        "analysis_only"
    ] = True
    updated[
        "broker_connection_enabled"
    ] = False
    updated[
        "trade_execution_enabled"
    ] = False

    return updated


__all__ = [
    "SAFETY_VERSION",
    "evaluate_symbol_winrate",
    "integrate_symbol_winrate",
]