"""
Blue-Trading-AI
Version 25 - Market Regime Signal Integration

Purpose:
- Integrate AI Market Regime Intelligence into existing signal results
- Preserve existing signal fields
- Apply regime-based confidence adjustment
- Enforce direction alignment, 80% confidence and 3 confirmations
- Keep the platform analysis-only
"""

from __future__ import annotations

from copy import deepcopy
import math
from typing import Any, Dict, Final, Iterable, List, Mapping, Optional

from app.services.market_regime_service import (
    MINIMUM_CONFIRMATIONS,
    MINIMUM_SIGNAL_CONFIDENCE,
    analyze_market_regime,
    apply_market_regime_confidence,
)


INTEGRATION_VERSION: Final[str] = "25.0.0"
MAXIMUM_SYMBOL_LENGTH: Final[int] = 40
MAXIMUM_TIMEFRAME_LENGTH: Final[int] = 20
MAXIMUM_CONFIRMATIONS: Final[int] = 100
MAXIMUM_TOP_LEVEL_SIGNAL_KEYS: Final[int] = 500
MAXIMUM_REASON_ITEMS: Final[int] = 200


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        resolved = float(value)
    except (TypeError, ValueError, OverflowError):
        try:
            resolved = float(default)
        except (TypeError, ValueError, OverflowError):
            resolved = 0.0

    if not math.isfinite(resolved):
        try:
            fallback = float(default)
        except (TypeError, ValueError, OverflowError):
            fallback = 0.0
        return fallback if math.isfinite(fallback) else 0.0

    return resolved


def _safe_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default

    try:
        resolved = int(value)
    except (TypeError, ValueError, OverflowError):
        return default

    return max(0, min(resolved, MAXIMUM_CONFIRMATIONS))


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value == 1:
            return True
        if value == 0:
            return False
        return default

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "approved", "pass", "passed"}:
            return True
        if normalized in {
            "false", "0", "no", "blocked", "rejected",
            "wait", "no_trade", "no trade", "fail", "failed"
        }:
            return False

    return default


def _normalize_direction(direction: Optional[str]) -> str:
    normalized = str(direction or "").strip().upper()

    aliases = {
        "LONG": "BUY",
        "BULLISH": "BUY",
        "SHORT": "SELL",
        "BEARISH": "SELL",
        "NONE": "WAIT",
        "NEUTRAL": "WAIT",
        "NO_TRADE": "WAIT",
        "NO TRADE": "WAIT",
        "HOLD": "WAIT",
    }

    resolved = aliases.get(normalized, normalized or "WAIT")
    return resolved if resolved in {"BUY", "SELL", "WAIT"} else "WAIT"


def _get_first_value(
    source: Mapping[str, Any],
    keys: Iterable[str],
    default: Any = None,
) -> Any:
    for key in keys:
        if key in source and source.get(key) is not None:
            return source.get(key)
    return default


def _extract_direction(signal: Mapping[str, Any]) -> str:
    value = _get_first_value(
        signal,
        ("decision", "signal", "direction", "trade_direction", "final_decision", "action"),
        "WAIT",
    )
    return _normalize_direction(value)


def _extract_confidence(signal: Mapping[str, Any]) -> float:
    value = _get_first_value(
        signal,
        (
            "final_confidence",
            "adjusted_confidence",
            "dynamic_confidence",
            "confidence",
            "confidence_score",
            "score",
        ),
        0.0,
    )
    return max(0.0, min(100.0, _safe_float(value)))


def _extract_confirmations(signal: Mapping[str, Any]) -> int:
    direct_value = _get_first_value(
        signal,
        ("total_confirmations", "confirmation_count", "confirmations_count", "confirmations"),
        None,
    )

    if isinstance(direct_value, (list, tuple, set, dict)):
        return min(len(direct_value), MAXIMUM_CONFIRMATIONS)

    if direct_value is not None:
        return _safe_int(direct_value)

    for source in (
        signal.get("confirmation_details"),
        signal.get("confluence_factors"),
        signal.get("reasons"),
        signal.get("technical_confirmations"),
    ):
        if isinstance(source, (list, tuple, set, dict)):
            return min(len(source), MAXIMUM_CONFIRMATIONS)

    return 0


def _normalize_symbol_value(value: Any) -> Optional[str]:
    if value is None:
        return None

    resolved = str(value).strip().upper()
    if not resolved or len(resolved) > MAXIMUM_SYMBOL_LENGTH:
        return None

    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/")
    if any(character not in allowed for character in resolved):
        return None

    return resolved


def _normalize_timeframe_value(value: Any) -> Optional[str]:
    if value is None:
        return None

    resolved = str(value).strip().upper()
    if not resolved or len(resolved) > MAXIMUM_TIMEFRAME_LENGTH:
        return None

    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if any(character not in allowed for character in resolved):
        return None

    return resolved


def _extract_symbol(
    signal: Mapping[str, Any],
    explicit_symbol: Optional[str],
) -> Optional[str]:
    if explicit_symbol:
        return _normalize_symbol_value(explicit_symbol)

    return _normalize_symbol_value(
        _get_first_value(
            signal,
            ("symbol", "market", "instrument", "pair"),
            None,
        )
    )


def _extract_timeframe(
    signal: Mapping[str, Any],
    explicit_timeframe: Optional[str],
) -> Optional[str]:
    if explicit_timeframe:
        return _normalize_timeframe_value(explicit_timeframe)

    return _normalize_timeframe_value(
        _get_first_value(
            signal,
            ("timeframe", "interval", "execution_timeframe"),
            None,
        )
    )


def _merge_unique_strings(*collections: Any) -> List[str]:
    merged: List[str] = []

    for collection in collections:
        if isinstance(collection, str):
            collection = [collection]

        if not isinstance(collection, (list, tuple, set)):
            continue

        for item in collection:
            text = str(item).strip()
            if text and text not in merged:
                merged.append(text)

            if len(merged) >= MAXIMUM_REASON_ITEMS:
                return merged

    return merged


def _materialize_candles(
    candles: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if isinstance(candles, list):
        source = candles
    else:
        try:
            source = list(candles)
        except TypeError as exc:
            raise TypeError(
                "candles must be an iterable of dictionaries."
            ) from exc

    return [
        dict(candle)
        for candle in source
        if isinstance(candle, Mapping)
    ]


def integrate_market_regime_into_signal(
    signal_result: Dict[str, Any],
    candles: Iterable[Dict[str, Any]],
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Integrate Version 25 market-regime intelligence into a signal.
    """

    if not isinstance(signal_result, dict):
        raise TypeError("signal_result must be a dictionary.")

    if len(signal_result) > MAXIMUM_TOP_LEVEL_SIGNAL_KEYS:
        raise ValueError(
            "signal_result contains too many top-level fields."
        )

    integrated = deepcopy(signal_result)
    resolved_candles = _materialize_candles(candles)

    resolved_symbol = _extract_symbol(integrated, symbol)
    resolved_timeframe = _extract_timeframe(integrated, timeframe)

    original_direction = _extract_direction(integrated)
    original_confidence = _extract_confidence(integrated)
    confirmations = _extract_confirmations(integrated)

    regime_adjustment = apply_market_regime_confidence(
        confidence=original_confidence,
        candles=resolved_candles,
        signal_direction=original_direction,
        confirmations=confirmations,
        symbol=resolved_symbol,
        timeframe=resolved_timeframe,
    )

    if not isinstance(regime_adjustment, Mapping):
        raise ValueError(
            "Market regime confidence service returned an invalid response."
        )

    regime_adjustment = dict(regime_adjustment)
    market_regime = regime_adjustment.get("market_regime")

    if not isinstance(market_regime, Mapping):
        market_regime = analyze_market_regime(
            candles=resolved_candles,
            symbol=resolved_symbol,
            timeframe=resolved_timeframe,
        )

    if not isinstance(market_regime, Mapping):
        raise ValueError(
            "Market regime analysis returned an invalid response."
        )

    market_regime = dict(market_regime)

    adjusted_confidence = max(
        0.0,
        min(
            100.0,
            _safe_float(
                regime_adjustment.get("adjusted_confidence"),
                original_confidence,
            ),
        ),
    )

    regime_approved = _safe_bool(
        regime_adjustment.get("approved", False)
    )

    existing_approved = integrated.get("approved")
    if existing_approved is None:
        existing_approved = integrated.get("signal_approved")

    if existing_approved is None:
        existing_approved = (
            original_direction in {"BUY", "SELL"}
            and original_confidence >= MINIMUM_SIGNAL_CONFIDENCE
            and confirmations >= MINIMUM_CONFIRMATIONS
        )
    else:
        existing_approved = _safe_bool(existing_approved)

    final_approved = (
        existing_approved
        and regime_approved
        and adjusted_confidence >= MINIMUM_SIGNAL_CONFIDENCE
        and confirmations >= MINIMUM_CONFIRMATIONS
        and original_direction in {"BUY", "SELL"}
    )

    final_decision = original_direction if final_approved else "WAIT"

    existing_blocking_reasons = _merge_unique_strings(
        integrated.get("blocking_reasons"),
        integrated.get("rejection_reasons"),
        integrated.get("block_reasons"),
    )

    regime_blocking_reasons = _merge_unique_strings(
        regime_adjustment.get("blocking_reasons"),
        market_regime.get("blocking_reasons"),
    )

    blocking_reasons = _merge_unique_strings(
        existing_blocking_reasons,
        regime_blocking_reasons,
    )

    if not existing_approved:
        blocking_reasons = _merge_unique_strings(
            blocking_reasons,
            ["Previous signal pipeline did not approve the signal."],
        )

    if adjusted_confidence < MINIMUM_SIGNAL_CONFIDENCE:
        blocking_reasons = _merge_unique_strings(
            blocking_reasons,
            ["Final confidence is below the required 80%."],
        )

    if confirmations < MINIMUM_CONFIRMATIONS:
        blocking_reasons = _merge_unique_strings(
            blocking_reasons,
            ["At least 3 confirmations are required."],
        )

    if original_direction not in {"BUY", "SELL"}:
        blocking_reasons = _merge_unique_strings(
            blocking_reasons,
            ["Signal direction must be BUY or SELL."],
        )

    if not regime_approved:
        blocking_reasons = _merge_unique_strings(
            blocking_reasons,
            ["Market regime did not approve the signal."],
        )

    regime_reasons = _merge_unique_strings(
        regime_adjustment.get("reasons"),
        market_regime.get("reasons"),
    )

    existing_reasons = _merge_unique_strings(
        integrated.get("reasons"),
        integrated.get("analysis_reasons"),
    )

    confidence_adjustment = _safe_float(
        regime_adjustment.get("confidence_adjustment"),
        0.0,
    )

    integrated.update(
        {
            "symbol": resolved_symbol,
            "timeframe": resolved_timeframe,
            "pre_regime_decision": original_direction,
            "pre_regime_confidence": round(original_confidence, 2),
            "market_regime_adjustment": round(confidence_adjustment, 2),
            "market_regime": market_regime,
            "market_regime_integration": {
                "version": INTEGRATION_VERSION,
                "approved": regime_approved,
                "signal_direction": original_direction,
                "regime_direction": _normalize_direction(
                    regime_adjustment.get("regime_direction", "WAIT")
                ),
                "original_confidence": round(original_confidence, 2),
                "adjusted_confidence": round(adjusted_confidence, 2),
                "confirmations": confirmations,
                "minimum_confidence_required": MINIMUM_SIGNAL_CONFIDENCE,
                "minimum_confirmations_required": MINIMUM_CONFIRMATIONS,
                "reasons": regime_reasons,
                "blocking_reasons": regime_blocking_reasons,
                "analysis_only": True,
                "trade_execution_enabled": False,
            },
            "final_confidence": round(adjusted_confidence, 2),
            "confidence": round(adjusted_confidence, 2),
            "final_decision": final_decision,
            "decision": final_decision,
            "signal": final_decision,
            "approved": final_approved,
            "signal_approved": final_approved,
            "total_confirmations": confirmations,
            "reasons": _merge_unique_strings(
                existing_reasons,
                regime_reasons,
            ),
            "blocking_reasons": blocking_reasons,
            "analysis_only": True,
            "broker_connection_enabled": False,
            "trade_execution_enabled": False,
            "automatic_order_placement_enabled": False,
        }
    )

    if not final_approved:
        integrated["status"] = "WAIT"
    elif not integrated.get("status"):
        integrated["status"] = "APPROVED"

    return integrated


def evaluate_market_regime_signal_integration(
    signal_result: Dict[str, Any],
    candles: Iterable[Dict[str, Any]],
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
) -> Dict[str, Any]:
    """Compatibility wrapper for service naming consistency."""

    return integrate_market_regime_into_signal(
        signal_result=signal_result,
        candles=candles,
        symbol=symbol,
        timeframe=timeframe,
    )


__all__ = [
    "INTEGRATION_VERSION",
    "evaluate_market_regime_signal_integration",
    "integrate_market_regime_into_signal",
]