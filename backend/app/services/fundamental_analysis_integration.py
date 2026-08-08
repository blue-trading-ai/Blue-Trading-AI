from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, Optional

from app.services.fundamental_analysis_service import (
    apply_fundamental_confidence,
)


def integrate_fundamental_analysis_into_signal(
    signal_result: Dict[str, Any],
    symbol: str,
    current_datetime: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Version 24
    Integrate Fundamental Analysis into the final signal.

    Rules:
    - Analysis only
    - No broker execution
    - Minimum confidence: 80
    - Minimum confirmations: 3
    """

    result = deepcopy(signal_result)

    confidence = float(result.get("confidence", 0.0))
    direction = str(result.get("signal", "WAIT")).upper()
    confirmations = int(result.get("confirmations", 0))

    fundamental = apply_fundamental_confidence(
        confidence=confidence,
        symbol=symbol,
        signal_direction=direction,
        confirmations=confirmations,
        current_datetime=current_datetime,
    )

    result["fundamental_analysis"] = fundamental
    result["confidence_before_fundamental"] = confidence
    result["confidence"] = fundamental["adjusted_confidence"]
    result["fundamental_adjustment"] = (
        fundamental["confidence_adjustment"]
    )
    result["fundamental_direction"] = (
        fundamental["fundamental_direction"]
    )
    result["fundamental_approved"] = (
        fundamental["approved"]
    )

    blocking = list(result.get("blocking_reasons", []))
    blocking.extend(fundamental.get("blocking_reasons", []))
    result["blocking_reasons"] = list(dict.fromkeys(blocking))

    approved = (
        fundamental["approved"]
        and result["confidence"] >= 80.0
        and confirmations >= 3
    )

    if approved:
        result["status"] = "APPROVED"
        result["trade_decision"] = direction
    else:
        result["status"] = "WAIT"
        result["trade_decision"] = "WAIT"

    result["analysis_only"] = True
    result["trade_execution_enabled"] = False

    return result