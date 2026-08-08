"""
Blue-Trading-AI
Version 30
app/services/confidence_guardrail_service.py

Safe confidence guardrail built on completed-trade learning analytics.

Rules:
- Analysis only
- No broker connection
- No automatic trade execution
- Minimum 20 completed trades before adjustment
- Maximum total adjustment: +/-4 points
- No timeframe-performance learning
- No strategy optimization
- No strategy ranking
- Final confidence remains between 0 and 100
- A signal below 80 confidence remains NO TRADE
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Dict, Final, Mapping


MINIMUM_COMPLETED_TRADES: Final[int] = 20
MAXIMUM_CONFIDENCE_ADJUSTMENT: Final[float] = 4.0
MINIMUM_SIGNAL_CONFIDENCE: Final[float] = 80.0

MAXIMUM_CONFIDENCE: Final[float] = 100.0
MAXIMUM_FACTOR_ADJUSTMENT: Final[float] = 1.5
MAXIMUM_COMPLETED_TRADES: Final[int] = 1_000_000
MAXIMUM_TEXT_LENGTH: Final[int] = 100


@dataclass(frozen=True)
class GuardrailFactor:
    """
    One evidence factor used in confidence calibration.
    """

    name: str
    category: str
    completed_trades: int
    win_rate: float
    proposed_adjustment: float
    applied_adjustment: float
    eligible: bool
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConfidenceGuardrailResult:
    """
    Final guarded confidence-calibration result.
    """

    base_confidence: float
    raw_adjustment: float
    applied_adjustment: float
    adjusted_confidence: float
    minimum_signal_confidence: float
    trade_allowed: bool
    decision: str
    completed_trade_requirement: int
    maximum_adjustment: float
    factors: tuple[GuardrailFactor, ...]
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["factors"] = [
            factor.to_dict()
            for factor in self.factors
        ]
        return payload


def clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    resolved_value = safe_float(
        value,
        default=minimum,
    )
    resolved_minimum = safe_float(
        minimum,
        default=0.0,
    )
    resolved_maximum = safe_float(
        maximum,
        default=resolved_minimum,
    )

    if resolved_minimum > resolved_maximum:
        resolved_minimum, resolved_maximum = (
            resolved_maximum,
            resolved_minimum,
        )

    return max(
        resolved_minimum,
        min(
            resolved_maximum,
            resolved_value,
        ),
    )


def normalise_text(
    value: Any,
    default: str = "unknown",
) -> str:
    text = str(value or "").strip()

    if not text:
        return default

    return text.lower()[
        :MAXIMUM_TEXT_LENGTH
    ]


def safe_float(
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


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    if isinstance(
        value,
        bool,
    ):
        return default

    try:
        resolved = int(
            value
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return default

    return max(
        0,
        min(
            resolved,
            MAXIMUM_COMPLETED_TRADES,
        ),
    )


def calculate_win_rate_adjustment(
    win_rate: float,
) -> float:
    """
    Convert a completed-trade win rate into a conservative adjustment.

    This is deliberately limited before the final global +/-4 cap:
    - >= 70%: +1.50
    - >= 65%: +1.00
    - >= 60%: +0.50
    - 45% to 59.99%: 0.00
    - 40% to 44.99%: -0.50
    - 35% to 39.99%: -1.00
    - below 35%: -1.50
    """

    rate = clamp(safe_float(win_rate), 0.0, 100.0)

    if rate >= 70.0:
        return 1.5
    if rate >= 65.0:
        return 1.0
    if rate >= 60.0:
        return 0.5
    if rate >= 45.0:
        return 0.0
    if rate >= 40.0:
        return -0.5
    if rate >= 35.0:
        return -1.0
    return -1.5


def extract_category_record(
    analytics: Mapping[str, Any] | None,
    category_name: str,
) -> Mapping[str, Any]:
    """
    Read one category entry from Version 29 analytics safely.
    """

    if not isinstance(analytics, Mapping):
        return {}

    direct = analytics.get(category_name)

    if isinstance(direct, Mapping):
        return direct

    normalised_target = normalise_text(category_name)

    for key, value in analytics.items():
        if (
            normalise_text(key) == normalised_target
            and isinstance(value, Mapping)
        ):
            return value

    return {}


def build_factor(
    *,
    name: str,
    category: str,
    record: Mapping[str, Any],
    weight: float,
) -> GuardrailFactor:
    """
    Build one guarded analytics factor.
    """

    completed_trades = safe_int(
        record.get(
            "completed_trades",
            record.get(
                "total_trades",
                record.get("trades", 0),
            ),
        )
    )

    win_rate = clamp(
        safe_float(
            record.get(
                "win_rate",
                record.get(
                    "winrate",
                    0.0,
                ),
            )
        ),
        0.0,
        100.0,
    )

    eligible = (
        completed_trades
        >= MINIMUM_COMPLETED_TRADES
    )

    if not eligible:
        return GuardrailFactor(
            name=name,
            category=category,
            completed_trades=completed_trades,
            win_rate=round(win_rate, 2),
            proposed_adjustment=0.0,
            applied_adjustment=0.0,
            eligible=False,
            reason=(
                f"Requires at least "
                f"{MINIMUM_COMPLETED_TRADES} completed trades."
            ),
        )

    resolved_weight = clamp(
        safe_float(
            weight,
            1.0,
        ),
        0.0,
        1.0,
    )

    proposed = (
        calculate_win_rate_adjustment(
            win_rate
        )
        * resolved_weight
    )

    applied = clamp(
        proposed,
        -MAXIMUM_FACTOR_ADJUSTMENT,
        MAXIMUM_FACTOR_ADJUSTMENT,
    )

    return GuardrailFactor(
        name=name,
        category=category,
        completed_trades=completed_trades,
        win_rate=round(win_rate, 2),
        proposed_adjustment=round(proposed, 2),
        applied_adjustment=round(applied, 2),
        eligible=True,
        reason=(
            "Adjustment derived from completed-trade "
            "win-rate evidence."
        ),
    )


def calculate_guarded_confidence(
    *,
    base_confidence: float,
    symbol: str,
    market_session: str,
    market_condition: str,
    direction: str,
    symbol_performance: Mapping[str, Any] | None = None,
    session_performance: Mapping[str, Any] | None = None,
    market_condition_performance: Mapping[str, Any] | None = None,
    direction_performance: Mapping[str, Any] | None = None,
) -> ConfidenceGuardrailResult:
    """
    Calculate the final Version 30 confidence recommendation.

    Weighting:
    - Symbol: 1.00
    - Session: 0.75
    - Market condition: 0.75
    - BUY/SELL direction: 0.50

    Even if all factors are strong or weak, the final adjustment is
    always clamped to +/-4 points.
    """

    clean_base = clamp(
        safe_float(
            base_confidence
        ),
        0.0,
        MAXIMUM_CONFIDENCE,
    )

    clean_symbol = str(
        symbol or ""
    ).strip().upper()[
        :MAXIMUM_TEXT_LENGTH
    ]

    clean_session = normalise_text(
        market_session
    )
    clean_condition = normalise_text(
        market_condition
    )
    clean_direction = str(
        direction or ""
    ).strip().upper()[
        :MAXIMUM_TEXT_LENGTH
    ]

    direction_aliases = {
        "LONG": "BUY",
        "BULLISH": "BUY",
        "SHORT": "SELL",
        "BEARISH": "SELL",
    }

    clean_direction = direction_aliases.get(
        clean_direction,
        clean_direction,
    )

    factors = (
        build_factor(
            name=clean_symbol or "UNKNOWN",
            category="symbol",
            record=extract_category_record(
                symbol_performance,
                clean_symbol,
            ),
            weight=1.00,
        ),
        build_factor(
            name=clean_session,
            category="session",
            record=extract_category_record(
                session_performance,
                clean_session,
            ),
            weight=0.75,
        ),
        build_factor(
            name=clean_condition,
            category="market_condition",
            record=extract_category_record(
                market_condition_performance,
                clean_condition,
            ),
            weight=0.75,
        ),
        build_factor(
            name=clean_direction or "UNKNOWN",
            category="direction",
            record=extract_category_record(
                direction_performance,
                clean_direction,
            ),
            weight=0.50,
        ),
    )

    raw_adjustment = safe_float(
        sum(
            factor.applied_adjustment
            for factor in factors
            if factor.eligible
        )
    )

    applied_adjustment = clamp(
        raw_adjustment,
        -MAXIMUM_CONFIDENCE_ADJUSTMENT,
        MAXIMUM_CONFIDENCE_ADJUSTMENT,
    )

    adjusted_confidence = clamp(
        clean_base + applied_adjustment,
        0.0,
        MAXIMUM_CONFIDENCE,
    )

    trade_allowed = (
        adjusted_confidence
        >= MINIMUM_SIGNAL_CONFIDENCE
    )

    eligible_count = sum(
        1
        for factor in factors
        if factor.eligible
    )

    if eligible_count == 0:
        reason = (
            "No analytics category has the required "
            f"{MINIMUM_COMPLETED_TRADES} completed trades. "
            "Base confidence was preserved."
        )
    elif applied_adjustment != raw_adjustment:
        reason = (
            "Completed-trade analytics were applied and the "
            "final adjustment was capped at +/-4."
        )
    else:
        reason = (
            "Completed-trade analytics were applied within "
            "the Version 30 confidence guardrail."
        )

    return ConfidenceGuardrailResult(
        base_confidence=round(clean_base, 2),
        raw_adjustment=round(raw_adjustment, 2),
        applied_adjustment=round(
            applied_adjustment,
            2,
        ),
        adjusted_confidence=round(
            adjusted_confidence,
            2,
        ),
        minimum_signal_confidence=(
            MINIMUM_SIGNAL_CONFIDENCE
        ),
        trade_allowed=trade_allowed,
        decision=(
            "TRADE_SIGNAL"
            if trade_allowed
            else "NO_TRADE"
        ),
        completed_trade_requirement=(
            MINIMUM_COMPLETED_TRADES
        ),
        maximum_adjustment=(
            MAXIMUM_CONFIDENCE_ADJUSTMENT
        ),
        factors=factors,
        reason=reason,
    )


def apply_guardrail_to_signal(
    signal: Mapping[str, Any],
    analytics_summary: Mapping[str, Any],
) -> Dict[str, Any]:
    """
    Return a copied signal with Version 30 confidence fields.

    Expected signal fields:
    - confidence or confidence_score
    - symbol
    - market_session or session
    - market_condition
    - direction or signal

    The original input mapping is never modified.
    """

    if not isinstance(
        signal,
        Mapping,
    ):
        raise ValueError(
            "signal must be a mapping."
        )

    if not isinstance(
        analytics_summary,
        Mapping,
    ):
        analytics_summary = {}

    output = dict(
        signal
    )

    base_confidence = safe_float(
        output.get(
            "confidence",
            output.get("confidence_score", 0.0),
        )
    )

    result = calculate_guarded_confidence(
        base_confidence=base_confidence,
        symbol=str(output.get("symbol", "")),
        market_session=str(
            output.get(
                "market_session",
                output.get("session", "unknown"),
            )
        ),
        market_condition=str(
            output.get("market_condition", "unknown")
        ),
        direction=str(
            output.get(
                "direction",
                output.get("signal", "unknown"),
            )
        ),
        symbol_performance=(
            analytics_summary.get(
                "symbol_performance",
                {},
            )
            if isinstance(
                analytics_summary.get(
                    "symbol_performance",
                    {},
                ),
                Mapping,
            )
            else {}
        ),
        session_performance=(
            analytics_summary.get(
                "session_performance",
                {},
            )
            if isinstance(
                analytics_summary.get(
                    "session_performance",
                    {},
                ),
                Mapping,
            )
            else {}
        ),
        market_condition_performance=(
            analytics_summary.get(
                "market_condition_performance",
                {},
            )
            if isinstance(
                analytics_summary.get(
                    "market_condition_performance",
                    {},
                ),
                Mapping,
            )
            else {}
        ),
        direction_performance=(
            analytics_summary.get(
                "direction_performance",
                {},
            )
            if isinstance(
                analytics_summary.get(
                    "direction_performance",
                    {},
                ),
                Mapping,
            )
            else {}
        ),
    )

    output["base_confidence"] = (
        result.base_confidence
    )
    output["learning_confidence_adjustment"] = (
        result.applied_adjustment
    )
    output["confidence"] = (
        result.adjusted_confidence
    )
    output["confidence_score"] = (
        result.adjusted_confidence
    )
    output["trade_allowed"] = (
        result.trade_allowed
    )
    output["decision"] = result.decision
    output["confidence_guardrail_v30"] = (
        result.to_dict()
    )

    return output


def get_confidence_guardrail_rules() -> Dict[str, Any]:
    """
    Return public Version 30 rules and safety controls.
    """

    return {
        "version": 30,
        "minimum_completed_trades": (
            MINIMUM_COMPLETED_TRADES
        ),
        "maximum_confidence_adjustment": (
            MAXIMUM_CONFIDENCE_ADJUSTMENT
        ),
        "minimum_signal_confidence": (
            MINIMUM_SIGNAL_CONFIDENCE
        ),
        "timeframe_performance_enabled": False,
        "strategy_optimization_enabled": False,
        "strategy_ranking_enabled": False,
        "analysis_only": True,
        "broker_connection_enabled": False,
        "trade_execution_enabled": False,
    }


__all__ = [
    "ConfidenceGuardrailResult",
    "MAXIMUM_CONFIDENCE",
    "MAXIMUM_FACTOR_ADJUSTMENT",
    "GuardrailFactor",
    "MAXIMUM_CONFIDENCE_ADJUSTMENT",
    "MINIMUM_COMPLETED_TRADES",
    "MINIMUM_SIGNAL_CONFIDENCE",
    "apply_guardrail_to_signal",
    "build_factor",
    "calculate_guarded_confidence",
    "calculate_win_rate_adjustment",
    "extract_category_record",
    "get_confidence_guardrail_rules",
]