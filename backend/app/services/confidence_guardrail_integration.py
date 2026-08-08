"""
Blue-Trading-AI
Version 30
app/services/confidence_guardrail_integration.py

Integration layer between:
- Version 29 learning analytics
- Version 30 confidence guardrail
- Master signal pipeline / trading API

Safety rules:
- Analysis only
- No broker connection
- No automatic trade execution
- Minimum 20 completed trades
- Maximum confidence adjustment: +/-4
- Minimum final confidence: 80
- No timeframe-performance learning
- No strategy optimization
- No strategy ranking
"""

from __future__ import annotations

import math
from typing import Any, Dict, Final, Mapping

from app.services.confidence_guardrail_service import (
    apply_guardrail_to_signal,
    get_confidence_guardrail_rules,
)
from app.services.learning_analytics_service import (
    get_direction_performance,
    get_market_condition_performance,
    get_session_performance,
    get_symbol_performance,
)


GUARDRAIL_VERSION: Final[int] = 30
MINIMUM_FINAL_CONFIDENCE: Final[float] = 80.0
MAXIMUM_TOP_LEVEL_KEYS: Final[int] = 500


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
        resolved = float(
            default
        )

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


def _copy_mapping(
    value: Mapping[str, Any],
    *,
    field_name: str,
) -> Dict[str, Any]:
    if not isinstance(
        value,
        Mapping,
    ):
        raise ValueError(
            f"{field_name} must be a mapping."
        )

    if len(
        value
    ) > MAXIMUM_TOP_LEVEL_KEYS:
        raise ValueError(
            f"{field_name} contains too many fields."
        )

    return dict(
        value
    )


def _safe_mapping_or_empty(
    value: Any,
) -> Dict[str, Any]:
    if isinstance(
        value,
        Mapping,
    ):
        return dict(
            value
        )

    return {}


def get_current_guardrail_analytics() -> Dict[str, Any]:
    """Return the current Version 29 analytics required by Version 30."""

    symbol_performance = _safe_mapping_or_empty(
        get_symbol_performance()
    )
    session_performance = _safe_mapping_or_empty(
        get_session_performance()
    )
    market_condition_performance = _safe_mapping_or_empty(
        get_market_condition_performance()
    )
    direction_performance = _safe_mapping_or_empty(
        get_direction_performance()
    )

    return {
        "symbol_performance": (
            symbol_performance
        ),
        "session_performance": (
            session_performance
        ),
        "market_condition_performance": (
            market_condition_performance
        ),
        "direction_performance": (
            direction_performance
        ),
    }


def normalise_signal_for_guardrail(
    signal: Mapping[str, Any],
) -> Dict[str, Any]:
    """
    Return a copied signal with standard fields expected by Version 30.

    Supported aliases:
    - confidence / confidence_score / final_confidence
    - direction / signal / trade_direction / action
    - market_session / session
    - market_condition / regime / market_regime
    """

    output = _copy_mapping(
        signal,
        field_name="signal",
    )

    if "confidence" not in output:
        output[
            "confidence"
        ] = output.get(
            "confidence_score",
            output.get(
                "final_confidence",
                0.0,
            ),
        )

    output[
        "confidence"
    ] = max(
        0.0,
        min(
            100.0,
            _safe_float(
                output.get(
                    "confidence",
                    0.0,
                )
            ),
        ),
    )

    if "direction" not in output:
        output[
            "direction"
        ] = output.get(
            "signal",
            output.get(
                "trade_direction",
                output.get(
                    "action",
                    "UNKNOWN",
                ),
            ),
        )

    direction = str(
        output.get(
            "direction",
            "UNKNOWN",
        )
        or "UNKNOWN"
    ).strip().upper()

    direction_aliases = {
        "LONG": "BUY",
        "BULLISH": "BUY",
        "SHORT": "SELL",
        "BEARISH": "SELL",
    }

    output[
        "direction"
    ] = direction_aliases.get(
        direction,
        direction,
    )

    if "market_session" not in output:
        output[
            "market_session"
        ] = output.get(
            "session",
            "unknown",
        )

    output[
        "market_session"
    ] = str(
        output.get(
            "market_session",
            "unknown",
        )
        or "unknown"
    ).strip().lower()[
        :100
    ]

    if "market_condition" not in output:
        output[
            "market_condition"
        ] = output.get(
            "regime",
            output.get(
                "market_regime",
                "unknown",
            ),
        )

    output[
        "market_condition"
    ] = str(
        output.get(
            "market_condition",
            "unknown",
        )
        or "unknown"
    ).strip().lower().replace(
        " ",
        "_",
    )[
        :100
    ]

    if "symbol" in output:
        output[
            "symbol"
        ] = str(
            output.get(
                "symbol",
                "",
            )
            or ""
        ).strip().upper()[
            :40
        ]

    return output


def integrate_confidence_guardrail(
    signal: Mapping[str, Any],
    analytics_summary: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Apply Version 30 guardrails to one signal.

    The original signal is never modified.
    """

    normalised_signal = (
        normalise_signal_for_guardrail(
            signal
        )
    )

    analytics = (
        _copy_mapping(
            analytics_summary,
            field_name="analytics_summary",
        )
        if analytics_summary is not None
        else get_current_guardrail_analytics()
    )

    guarded_signal = apply_guardrail_to_signal(
        signal=normalised_signal,
        analytics_summary=analytics,
    )

    if not isinstance(
        guarded_signal,
        dict,
    ):
        raise ValueError(
            "Confidence guardrail returned an invalid signal response."
        )

    guarded_signal = dict(
        guarded_signal
    )
    guarded_signal[
        "confidence_guardrail_applied"
    ] = True
    guarded_signal[
        "confidence_guardrail_version"
    ] = GUARDRAIL_VERSION
    guarded_signal[
        "analysis_only"
    ] = True
    guarded_signal[
        "broker_connection_enabled"
    ] = False
    guarded_signal[
        "trade_execution_enabled"
    ] = False

    return guarded_signal


def integrate_guardrail_into_pipeline_result(
    pipeline_result: Mapping[str, Any],
) -> Dict[str, Any]:
    """
    Apply Version 30 guardrails to a master-pipeline result.

    Supported result shapes:
    1. Direct signal dictionary
    2. {"signal": {...}}
    3. {"data": {...}}
    4. {"result": {...}}

    A copied result is returned.
    """

    output = _copy_mapping(
        pipeline_result,
        field_name="pipeline_result",
    )

    nested_keys = (
        "signal",
        "data",
        "result",
    )

    for key in nested_keys:
        nested_value = output.get(
            key
        )

        if isinstance(
            nested_value,
            Mapping,
        ):
            output[
                key
            ] = integrate_confidence_guardrail(
                nested_value
            )

            output[
                "confidence_guardrail_applied"
            ] = True
            output[
                "confidence_guardrail_version"
            ] = GUARDRAIL_VERSION
            output[
                "analysis_only"
            ] = True
            output[
                "broker_connection_enabled"
            ] = False
            output[
                "trade_execution_enabled"
            ] = False

            return output

    return integrate_confidence_guardrail(
        output
    )


def enforce_guardrail_decision(
    signal: Mapping[str, Any],
) -> Dict[str, Any]:
    """
    Enforce the final Version 30 decision fields.

    A confidence below 80 always becomes NO_TRADE.
    """

    output = _copy_mapping(
        signal,
        field_name="signal",
    )

    confidence = max(
        0.0,
        min(
            100.0,
            _safe_float(
                output.get(
                    "confidence",
                    output.get(
                        "confidence_score",
                        0.0,
                    ),
                )
            ),
        ),
    )

    output[
        "confidence"
    ] = confidence
    output[
        "confidence_score"
    ] = confidence

    trade_allowed = (
        confidence
        >= MINIMUM_FINAL_CONFIDENCE
    )

    output[
        "trade_allowed"
    ] = trade_allowed
    output[
        "decision"
    ] = (
        "TRADE_SIGNAL"
        if trade_allowed
        else "NO_TRADE"
    )

    if not trade_allowed:
        output[
            "signal_status"
        ] = "BLOCKED"
        output[
            "block_reason"
        ] = (
            "Final confidence is below the required 80%."
        )
    else:
        output.setdefault(
            "signal_status",
            "APPROVED",
        )
        output.pop(
            "block_reason",
            None,
        )

    output[
        "confidence_guardrail_version"
    ] = GUARDRAIL_VERSION
    output[
        "analysis_only"
    ] = True
    output[
        "broker_connection_enabled"
    ] = False
    output[
        "trade_execution_enabled"
    ] = False

    return output


def apply_complete_confidence_guardrail(
    signal: Mapping[str, Any],
) -> Dict[str, Any]:
    """Apply analytics calibration and final 80% decision enforcement."""

    guarded = integrate_confidence_guardrail(
        signal
    )

    return enforce_guardrail_decision(
        guarded
    )


def get_confidence_guardrail_integration_status() -> Dict[str, Any]:
    """Return Version 30 integration status and safety settings."""

    rules = get_confidence_guardrail_rules()

    if not isinstance(
        rules,
        dict,
    ):
        raise ValueError(
            "Confidence guardrail rules returned an invalid response."
        )

    return {
        "status": "ready",
        "version": GUARDRAIL_VERSION,
        "integration": (
            "learning_analytics_to_master_signal_pipeline"
        ),
        "guardrail_rules": dict(
            rules
        ),
        "pipeline_integration_enabled": True,
        "original_signal_mutation_enabled": False,
        "analysis_only": True,
        "broker_connection_enabled": False,
        "trade_execution_enabled": False,
    }


__all__ = [
    "GUARDRAIL_VERSION",
    "MAXIMUM_TOP_LEVEL_KEYS",
    "MINIMUM_FINAL_CONFIDENCE",
    "apply_complete_confidence_guardrail",
    "enforce_guardrail_decision",
    "get_confidence_guardrail_integration_status",
    "get_current_guardrail_analytics",
    "integrate_confidence_guardrail",
    "integrate_guardrail_into_pipeline_result",
    "normalise_signal_for_guardrail",
]