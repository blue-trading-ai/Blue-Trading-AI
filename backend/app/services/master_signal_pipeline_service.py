"""
Blue-Trading-AI
Version 30 — Master Signal Pipeline Engine

Purpose:
- Combine results from all analysis engines.
- Validate agreement between engines.
- Apply mandatory safety rules.
- Produce one final BUY, SELL, or WAIT decision.

Important:
- Analysis and signal generation only.
- No broker connection.
- No automatic trade execution.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any, Dict, Final, List, Optional

from app.services.confidence_guardrail_integration import (
    integrate_confidence_guardrail,
)


PROJECT_NAME: Final = "Blue-Trading-AI"
SAFETY_VERSION: Final = 30

SUPPORTED_DECISIONS: Final = frozenset({"BUY", "SELL", "WAIT"})

MINIMUM_FINAL_CONFIDENCE: Final = 80.0
MINIMUM_RANKING_SCORE: Final = 75.0
MINIMUM_CONFIRMATIONS: Final = 3
MINIMUM_RISK_REWARD_RATIO: Final = 1.5
MINIMUM_DIRECTION_ALIGNMENT: Final = 75.0
MAXIMUM_LEARNING_CONFIDENCE_ADJUSTMENT: Final = 4.0
MAXIMUM_CONFIRMATIONS: Final = 100
MAXIMUM_RISK_REWARD_RATIO: Final = 100.0
MAXIMUM_ENGINE_SCORE: Final = 100.0
MAXIMUM_SYMBOL_LENGTH: Final = 32
MAXIMUM_TIMEFRAME_LENGTH: Final = 16
MAXIMUM_SIGNAL_ID_LENGTH: Final = 128

BROKER_CONNECTION_ENABLED: Final = False
TRADE_EXECUTION_ENABLED: Final = False


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """Convert a value safely into a finite float."""

    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return float(default)

    if not math.isfinite(number):
        return float(default)

    return number


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    """Convert a value safely into a bounded non-negative integer."""

    if isinstance(value, bool):
        return default

    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return default

    return max(
        0,
        min(
            number,
            MAXIMUM_CONFIRMATIONS,
        ),
    )


def _safe_bool(
    value: Any,
    default: bool = False,
) -> bool:
    """Convert common boolean representations without truthy-string bugs."""

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

        if normalized in {"true", "1", "yes", "y", "on", "approved", "allowed"}:
            return True

        if normalized in {"false", "0", "no", "n", "off", "rejected", "blocked"}:
            return False

    return default


def _normalise_decision(value: Any) -> str:
    """Convert a decision into BUY, SELL, or WAIT."""

    decision = str(value or "WAIT").strip().upper()

    if decision not in SUPPORTED_DECISIONS:
        return "WAIT"

    return decision


def _extract_decision(
    engine_result: Optional[Dict[str, Any]],
) -> str:
    """
    Extract a decision from an engine result.

    Supports several common field names used by analysis engines.
    """

    if not isinstance(engine_result, dict):
        return "WAIT"

    possible_fields = (
        "final_decision",
        "decision",
        "signal",
        "direction",
        "recommended_action",
    )

    for field in possible_fields:
        if field in engine_result:
            return _normalise_decision(engine_result.get(field))

    return "WAIT"


def _extract_score(
    engine_result: Optional[Dict[str, Any]],
    possible_fields: tuple[str, ...],
) -> float:
    """Extract the first available score from an engine result."""

    if not isinstance(engine_result, dict):
        return 0.0

    for field in possible_fields:
        if field in engine_result:
            return max(
                0.0,
                min(
                    _safe_float(engine_result.get(field)),
                    MAXIMUM_ENGINE_SCORE,
                ),
            )

    return 0.0


def _extract_approval(
    engine_result: Optional[Dict[str, Any]],
    default: bool = False,
) -> bool:
    """Extract approval status from an engine result."""

    if not isinstance(engine_result, dict):
        return default

    possible_fields = (
        "signal_approved",
        "approved",
        "entry_allowed",
        "context_approved",
        "institutional_approved",
        "multi_timeframe_approved",
        "risk_management_approved",
        "market_regime_approved",
        "regime_approved",
    )

    for field in possible_fields:
        if field in engine_result:
            return _safe_bool(
                engine_result.get(field),
                default=default,
            )

    return default


def _collect_engine_directions(
    engine_results: Dict[str, Dict[str, Any]],
) -> Dict[str, str]:
    """Collect the direction returned by every engine."""

    return {
        engine_name: _extract_decision(engine_result)
        for engine_name, engine_result in engine_results.items()
    }


def _calculate_direction_summary(
    engine_directions: Dict[str, str],
) -> Dict[str, Any]:
    """Calculate BUY, SELL, and WAIT agreement counts."""

    buy_count = sum(
        1 for decision in engine_directions.values()
        if decision == "BUY"
    )

    sell_count = sum(
        1 for decision in engine_directions.values()
        if decision == "SELL"
    )

    wait_count = sum(
        1 for decision in engine_directions.values()
        if decision == "WAIT"
    )

    directional_count = buy_count + sell_count

    if buy_count > sell_count:
        dominant_direction = "BUY"
        dominant_count = buy_count
    elif sell_count > buy_count:
        dominant_direction = "SELL"
        dominant_count = sell_count
    else:
        dominant_direction = "WAIT"
        dominant_count = 0

    if directional_count > 0:
        direction_alignment_percentage = round(
            (dominant_count / directional_count) * 100,
            2,
        )
    else:
        direction_alignment_percentage = 0.0

    buy_sell_conflict = buy_count > 0 and sell_count > 0

    return {
        "buy_count": buy_count,
        "sell_count": sell_count,
        "wait_count": wait_count,
        "directional_engine_count": directional_count,
        "dominant_direction": dominant_direction,
        "dominant_count": dominant_count,
        "direction_alignment_percentage": (
            direction_alignment_percentage
        ),
        "buy_sell_conflict": buy_sell_conflict,
    }


def evaluate_master_signal_pipeline(
    *,
    signal_id: str,
    symbol: str,
    timeframe: str,
    market_context: Dict[str, Any],
    institutional_smc: Dict[str, Any],
    ai_confluence: Dict[str, Any],
    multi_timeframe: Dict[str, Any],
    dynamic_confidence: Dict[str, Any],
    risk_management: Dict[str, Any],
    market_structure: Optional[Dict[str, Any]] = None,
    momentum_analysis: Optional[Dict[str, Any]] = None,
    pattern_analysis: Optional[Dict[str, Any]] = None,
    market_regime: Optional[Dict[str, Any]] = None,
    symbol_winrate: Optional[Dict[str, Any]] = None,
    learning_intelligence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Evaluate all engine results through one master pipeline.

    Every engine must already have completed its own analysis.

    The master pipeline:
    1. Collects engine decisions.
    2. Checks mandatory approvals.
    3. Checks direction alignment.
    4. Checks confidence and ranking thresholds.
    5. Checks confirmation count and risk-reward ratio.
    6. Applies Version 25 Market Regime approval and confidence rules.
    7. Applies Version 26 Symbol Win Rate confidence learning.
    8. Applies bounded Version 27 Learning Intelligence adjustment.
    9. Applies the Version 30 completed-trade confidence guardrail.
    10. Enforces the final 80% minimum-confidence requirement.
    11. Returns the final signal decision.
    """

    signal_id = str(signal_id or "").strip()[:MAXIMUM_SIGNAL_ID_LENGTH]
    symbol = str(symbol or "").strip().upper()[:MAXIMUM_SYMBOL_LENGTH]
    timeframe = str(timeframe or "").strip().upper()[:MAXIMUM_TIMEFRAME_LENGTH]

    blocking_reasons: List[str] = []
    warnings: List[str] = []
    confirmation_reasons: List[str] = []

    if not signal_id:
        blocking_reasons.append("Signal ID is required.")

    if not symbol:
        blocking_reasons.append("Symbol is required.")

    if not timeframe:
        blocking_reasons.append("Timeframe is required.")

    engine_results: Dict[str, Dict[str, Any]] = {
        "market_context": market_context if isinstance(market_context, dict) else {},
        "institutional_smc": institutional_smc if isinstance(institutional_smc, dict) else {},
        "ai_confluence": ai_confluence if isinstance(ai_confluence, dict) else {},
        "multi_timeframe": multi_timeframe if isinstance(multi_timeframe, dict) else {},
        "dynamic_confidence": dynamic_confidence if isinstance(dynamic_confidence, dict) else {},
        "risk_management": risk_management if isinstance(risk_management, dict) else {},
    }

    if isinstance(market_structure, dict):
        engine_results["market_structure"] = market_structure

    if isinstance(momentum_analysis, dict):
        engine_results["momentum_analysis"] = momentum_analysis

    if isinstance(pattern_analysis, dict):
        engine_results["pattern_analysis"] = pattern_analysis

    if isinstance(market_regime, dict):
        engine_results["market_regime"] = market_regime

    if isinstance(symbol_winrate, dict):
        engine_results["symbol_winrate"] = symbol_winrate

    engine_directions = _collect_engine_directions(engine_results)

    direction_summary = _calculate_direction_summary(
        engine_directions
    )

    dominant_direction = direction_summary["dominant_direction"]
    direction_alignment_percentage = direction_summary[
        "direction_alignment_percentage"
    ]

    context_approved = _extract_approval(
        market_context,
        default=False,
    )

    institutional_approved = _extract_approval(
        institutional_smc,
        default=False,
    )

    ai_confluence_approved = _extract_approval(
        ai_confluence,
        default=False,
    )

    multi_timeframe_approved = _extract_approval(
        multi_timeframe,
        default=False,
    )

    dynamic_confidence_approved = _extract_approval(
        dynamic_confidence,
        default=False,
    )

    risk_management_approved = _extract_approval(
        risk_management,
        default=False,
    )

    market_regime_approved = _extract_approval(
        market_regime,
        default=True if market_regime is None else False,
    )

    dynamic_confidence_score = _extract_score(
        dynamic_confidence,
        (
            "dynamic_confidence",
            "final_confidence",
            "confidence",
            "confidence_score",
        ),
    )


    symbol_winrate_adjustment = 0.0
    symbol_winrate_stats = {}
    if isinstance(symbol_winrate, dict):
        symbol_winrate_adjustment = max(
            -MAXIMUM_LEARNING_CONFIDENCE_ADJUSTMENT,
            min(
                MAXIMUM_LEARNING_CONFIDENCE_ADJUSTMENT,
                _safe_float(
                    symbol_winrate.get(
                        "confidence_adjustment",
                        0.0,
                    )
                ),
            ),
        )
        symbol_winrate_stats = symbol_winrate
    dynamic_confidence_score = min(
        100.0,
        max(0.0, dynamic_confidence_score + symbol_winrate_adjustment),
    )

    # Version 27 bounded self-learning confidence adjustment.
    learning_confidence_adjustment = 0.0
    learning_intelligence_stats: Dict[str, Any] = {}
    learning_recommend_wait = False
    learning_stronger_confirmation = False

    if isinstance(learning_intelligence, dict):
        learning_intelligence_stats = learning_intelligence
        learning_confidence_adjustment = _safe_float(
            learning_intelligence.get(
                "confidence_adjustment",
                learning_intelligence.get(
                    "recommendation", {}
                ).get(
                    "confidence_adjustment",
                    0.0,
                )
                if isinstance(
                    learning_intelligence.get("recommendation"),
                    dict,
                )
                else 0.0,
            )
        )

        learning_confidence_adjustment = max(
            -MAXIMUM_LEARNING_CONFIDENCE_ADJUSTMENT,
            min(
                MAXIMUM_LEARNING_CONFIDENCE_ADJUSTMENT,
                learning_confidence_adjustment,
            ),
        )

        recommendation = learning_intelligence.get(
            "recommendation", {}
        )
        if isinstance(recommendation, dict):
            learning_recommend_wait = _safe_bool(
                recommendation.get("recommend_wait", False)
            )
            learning_stronger_confirmation = _safe_bool(
                recommendation.get("stronger_confirmation", False)
            )

    dynamic_confidence_score = min(
        100.0,
        max(
            0.0,
            dynamic_confidence_score
            + learning_confidence_adjustment,
        ),
    )

    # Version 30 completed-trade confidence guardrail.
    market_session_name = "unknown"
    if isinstance(market_context, dict):
        market_session_name = str(
            market_context.get(
                "market_session",
                market_context.get("session", "unknown"),
            )
            or "unknown"
        )

    if (
        market_session_name == "unknown"
        and isinstance(dynamic_confidence, dict)
    ):
        market_session_name = str(
            dynamic_confidence.get(
                "market_session",
                dynamic_confidence.get("session", "unknown"),
            )
            or "unknown"
        )

    market_condition_name = "unknown"
    if isinstance(market_regime, dict):
        market_condition_name = str(
            market_regime.get(
                "market_condition",
                market_regime.get(
                    "regime",
                    market_regime.get(
                        "market_regime",
                        market_regime.get("regime_type", "unknown"),
                    ),
                ),
            )
            or "unknown"
        )

    confidence_guardrail = integrate_confidence_guardrail(
        {
            "symbol": symbol,
            "confidence": dynamic_confidence_score,
            "direction": dominant_direction,
            "market_session": market_session_name,
            "market_condition": market_condition_name,
        }
    )

    if not isinstance(confidence_guardrail, dict):
        confidence_guardrail = {
            "trade_allowed": False,
            "base_confidence": dynamic_confidence_score,
            "confidence": dynamic_confidence_score,
            "learning_confidence_adjustment": 0.0,
            "error": "Invalid confidence guardrail response.",
        }

    guardrail_base_confidence = _safe_float(
        confidence_guardrail.get(
            "base_confidence",
            dynamic_confidence_score,
        )
    )
    guardrail_adjustment = max(
        -MAXIMUM_LEARNING_CONFIDENCE_ADJUSTMENT,
        min(
            MAXIMUM_LEARNING_CONFIDENCE_ADJUSTMENT,
            _safe_float(
                confidence_guardrail.get(
                    "learning_confidence_adjustment",
                    0.0,
                )
            ),
        ),
    )
    dynamic_confidence_score = min(
        100.0,
        max(
            0.0,
            _safe_float(
                confidence_guardrail.get(
                    "confidence",
                    dynamic_confidence_score,
                )
            ),
        ),
    )
    confidence_guardrail_passed = _safe_bool(
        confidence_guardrail.get("trade_allowed", False)
    )

    ranking_score = _extract_score(
        dynamic_confidence,
        (
            "ranking_score",
            "signal_ranking_score",
            "score",
        ),
    )

    ai_confluence_score = _extract_score(
        ai_confluence,
        (
            "ai_confluence_score",
            "confluence_score",
            "score",
        ),
    )

    multi_timeframe_score = _extract_score(
        multi_timeframe,
        (
            "alignment_score",
            "multi_timeframe_score",
            "weighted_alignment",
            "score",
        ),
    )

    institutional_score = _extract_score(
        institutional_smc,
        (
            "institutional_score",
            "smart_money_score",
            "smc_score",
            "score",
        ),
    )

    context_score = _extract_score(
        market_context,
        (
            "context_score",
            "market_context_score",
            "score",
        ),
    )

    market_regime_score = _extract_score(
        market_regime,
        (
            "regime_score",
            "market_regime_score",
            "confidence",
            "confidence_score",
            "score",
        ),
    )

    market_regime_direction = _extract_decision(market_regime)

    regime_direction_aligned = (
        market_regime is None
        or market_regime_direction == "WAIT"
        or dominant_direction == "WAIT"
        or market_regime_direction == dominant_direction
    )

    fake_breakout_detected = _safe_bool(
        market_regime.get("fake_breakout_detected", False)
        if isinstance(market_regime, dict)
        else False
    )

    regime_blocks_signal = _safe_bool(
        market_regime.get("blocks_signal", False)
        if isinstance(market_regime, dict)
        else False
    )

    confirmation_count = _safe_int(
        dynamic_confidence.get(
            "confirmation_count",
            dynamic_confidence.get("confirmations", 0),
        )
        if isinstance(dynamic_confidence, dict)
        else 0
    )

    risk_reward_ratio = _extract_score(
        risk_management,
        (
            "risk_reward_ratio",
            "rr_ratio",
            "risk_reward",
        ),
    )

    if risk_reward_ratio <= 0:
        risk_reward_ratio = _extract_score(
            dynamic_confidence,
            (
                "risk_reward_ratio",
                "rr_ratio",
                "risk_reward",
            ),
        )

    hierarchy_conflict = _safe_bool(
        multi_timeframe.get("hierarchy_conflict", False)
        if isinstance(multi_timeframe, dict)
        else False
    )

    high_risk_environment = _safe_bool(
        market_context.get("high_risk_environment", False)
        if isinstance(market_context, dict)
        else False
    )

    weak_signal_quality = _safe_bool(
        dynamic_confidence.get("weak_signal_quality", False)
        if isinstance(dynamic_confidence, dict)
        else False
    )

    if not context_approved:
        blocking_reasons.append(
            "Market Context Engine approval is required."
        )
    else:
        confirmation_reasons.append(
            "Market context supports the setup."
        )

    if not institutional_approved:
        blocking_reasons.append(
            "Institutional Smart Money approval is required."
        )
    else:
        confirmation_reasons.append(
            "Institutional Smart Money analysis supports the setup."
        )

    if not ai_confluence_approved:
        blocking_reasons.append(
            "AI Confluence Engine approval is required."
        )
    else:
        confirmation_reasons.append(
            "AI Confluence Engine supports the setup."
        )

    if not multi_timeframe_approved:
        blocking_reasons.append(
            "Multi-Timeframe Engine approval is required."
        )
    else:
        confirmation_reasons.append(
            "Multi-timeframe analysis supports the setup."
        )

    if not dynamic_confidence_approved:
        blocking_reasons.append(
            "Dynamic Confidence Engine approval is required."
        )

    if not risk_management_approved:
        blocking_reasons.append(
            "Risk Management approval is required."
        )
    else:
        confirmation_reasons.append(
            "Risk management requirements are satisfied."
        )

    if market_regime is not None:
        if not market_regime_approved:
            blocking_reasons.append(
                "Market Regime Intelligence approval is required."
            )
        else:
            confirmation_reasons.append(
                "Market Regime Intelligence supports the setup."
            )

        if not regime_direction_aligned:
            blocking_reasons.append(
                "Market regime direction conflicts with the dominant signal direction."
            )

        if fake_breakout_detected:
            blocking_reasons.append(
                "Market Regime Intelligence detected a possible fake breakout."
            )

        if regime_blocks_signal:
            blocking_reasons.append(
                "The current market regime blocks signal approval."
            )

    if learning_recommend_wait:
        blocking_reasons.append(
            "Version 27 Learning Intelligence recommends WAIT based "
            "on completed-trade performance."
        )

    if learning_stronger_confirmation:
        warnings.append(
            "Version 27 Learning Intelligence recommends stronger "
            "confirmation for this setup."
        )

    if learning_confidence_adjustment > 0:
        confirmation_reasons.append(
            "Version 27 completed-trade learning supports a bounded "
            "confidence increase."
        )
    elif learning_confidence_adjustment < 0:
        warnings.append(
            "Version 27 completed-trade learning reduced confidence."
        )

    if dominant_direction == "WAIT":
        blocking_reasons.append(
            "The analysis engines did not establish a dominant direction."
        )

    if direction_summary["buy_sell_conflict"]:
        blocking_reasons.append(
            "BUY and SELL engine directions are conflicting."
        )

    if direction_alignment_percentage < MINIMUM_DIRECTION_ALIGNMENT:
        blocking_reasons.append(
            "Engine direction alignment is below 75%."
        )

    if hierarchy_conflict:
        blocking_reasons.append(
            "A multi-timeframe hierarchy conflict was detected."
        )

    if high_risk_environment:
        blocking_reasons.append(
            "The current market environment is classified as high risk."
        )

    if weak_signal_quality:
        blocking_reasons.append(
            "The Dynamic Confidence Engine classified the signal "
            "quality as weak."
        )

    if dynamic_confidence_score < MINIMUM_FINAL_CONFIDENCE:
        blocking_reasons.append(
            f"Dynamic confidence must be at least "
            f"{MINIMUM_FINAL_CONFIDENCE}."
        )

    if not confidence_guardrail_passed:
        blocking_reasons.append(
            "Version 30 Confidence Guardrail rejected the signal "
            "because the guarded confidence is below 80%."
        )
    elif guardrail_adjustment > 0:
        confirmation_reasons.append(
            "Version 30 completed-trade analytics support a "
            "bounded confidence increase."
        )
    elif guardrail_adjustment < 0:
        warnings.append(
            "Version 30 completed-trade analytics reduced the "
            "final confidence."
        )

    if ranking_score < MINIMUM_RANKING_SCORE:
        blocking_reasons.append(
            f"Signal ranking score must be at least "
            f"{MINIMUM_RANKING_SCORE}."
        )

    if confirmation_count < MINIMUM_CONFIRMATIONS:
        blocking_reasons.append(
            f"At least {MINIMUM_CONFIRMATIONS} confirmations "
            f"are required."
        )

    if risk_reward_ratio < MINIMUM_RISK_REWARD_RATIO:
        blocking_reasons.append(
            f"Risk-reward ratio must be at least "
            f"{MINIMUM_RISK_REWARD_RATIO}."
        )

    if dynamic_confidence_score >= 95:
        confirmation_reasons.append(
            "Dynamic confidence is at an elite level."
        )
    elif dynamic_confidence_score >= 90:
        confirmation_reasons.append(
            "Dynamic confidence is very strong."
        )
    elif dynamic_confidence_score >= 80:
        confirmation_reasons.append(
            "Dynamic confidence meets the approval threshold."
        )

    if ranking_score >= 90:
        confirmation_reasons.append(
            "Signal ranking score is very strong."
        )
    elif ranking_score >= 75:
        confirmation_reasons.append(
            "Signal ranking score meets the approval threshold."
        )

    if direction_alignment_percentage == 100:
        confirmation_reasons.append(
            "All directional engines are fully aligned."
        )
    elif direction_alignment_percentage >= MINIMUM_DIRECTION_ALIGNMENT:
        confirmation_reasons.append(
            "Directional engines have sufficient alignment."
        )

    if risk_reward_ratio >= 2.0:
        confirmation_reasons.append(
            "Risk-reward ratio is strong."
        )

    blocking_reasons = list(
        dict.fromkeys(blocking_reasons)
    )
    warnings = list(
        dict.fromkeys(warnings)
    )
    confirmation_reasons = list(
        dict.fromkeys(confirmation_reasons)
    )

    signal_approved = len(blocking_reasons) == 0

    final_decision = (
        dominant_direction
        if signal_approved
        else "WAIT"
    )

    if not signal_approved:
        warnings.append(
            "The pipeline changed the final decision to WAIT "
            "because one or more mandatory safety rules failed."
        )

    if market_regime is not None:
        final_quality_score = round(
            max(
                0.0,
                min(
                    (
                        dynamic_confidence_score * 0.27
                        + ranking_score * 0.18
                        + ai_confluence_score * 0.14
                        + multi_timeframe_score * 0.14
                        + institutional_score * 0.09
                        + context_score * 0.09
                        + market_regime_score * 0.09
                    ),
                    100.0,
                ),
            ),
            2,
        )
    else:
        final_quality_score = round(
            max(
                0.0,
                min(
                    (
                        dynamic_confidence_score * 0.30
                        + ranking_score * 0.20
                        + ai_confluence_score * 0.15
                        + multi_timeframe_score * 0.15
                        + institutional_score * 0.10
                        + context_score * 0.10
                    ),
                    100.0,
                ),
            ),
            2,
        )

    return {
        "status": "success",
        "project": PROJECT_NAME,
        "module": "Master Signal Pipeline Engine",
        "safety_version": SAFETY_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "signal_id": signal_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "final_decision": final_decision,
        "signal_approved": signal_approved,
        "final_quality_score": final_quality_score,
        "dynamic_confidence": round(
            dynamic_confidence_score,
            2,
        ),
        "ranking_score": round(ranking_score, 2),
        "confirmation_count": confirmation_count,
        "risk_reward_ratio": round(risk_reward_ratio, 2),
        "dominant_direction": dominant_direction,
        "direction_alignment_percentage": (
            direction_alignment_percentage
        ),
        "engine_direction_summary": direction_summary,
        "engine_directions": engine_directions,
        "symbol_winrate": symbol_winrate_stats,
        "learning_intelligence": learning_intelligence_stats,
        "confidence_adjustments": {
            "symbol_winrate": round(
                symbol_winrate_adjustment,
                2,
            ),
            "learning_intelligence": round(
                learning_confidence_adjustment,
                2,
            ),
            "confidence_guardrail_v30": round(
                guardrail_adjustment,
                2,
            ),
        },
        "engine_scores": {
            "market_context": round(context_score, 2),
            "institutional_smc": round(
                institutional_score,
                2,
            ),
            "ai_confluence": round(
                ai_confluence_score,
                2,
            ),
            "multi_timeframe": round(
                multi_timeframe_score,
                2,
            ),
            "dynamic_confidence": round(
                dynamic_confidence_score,
                2,
            ),
            "signal_ranking": round(ranking_score, 2),
            "market_regime": round(market_regime_score, 2),
        },
        "mandatory_approvals": {
            "market_context_approved": context_approved,
            "institutional_smc_approved": (
                institutional_approved
            ),
            "ai_confluence_approved": (
                ai_confluence_approved
            ),
            "multi_timeframe_approved": (
                multi_timeframe_approved
            ),
            "dynamic_confidence_approved": (
                dynamic_confidence_approved
            ),
            "risk_management_approved": (
                risk_management_approved
            ),
            "market_regime_approved": market_regime_approved,
        },
        "safety_checks": {
            "hierarchy_conflict": hierarchy_conflict,
            "high_risk_environment": high_risk_environment,
            "weak_signal_quality": weak_signal_quality,
            "minimum_confidence_passed": (
                dynamic_confidence_score
                >= MINIMUM_FINAL_CONFIDENCE
            ),
            "minimum_ranking_score_passed": (
                ranking_score >= MINIMUM_RANKING_SCORE
            ),
            "minimum_confirmations_passed": (
                confirmation_count >= MINIMUM_CONFIRMATIONS
            ),
            "minimum_risk_reward_passed": (
                risk_reward_ratio
                >= MINIMUM_RISK_REWARD_RATIO
            ),
            "direction_alignment_passed": (
                direction_alignment_percentage
                >= MINIMUM_DIRECTION_ALIGNMENT
            ),
            "market_regime_direction_aligned": (
                regime_direction_aligned
            ),
            "fake_breakout_detected": fake_breakout_detected,
            "market_regime_blocks_signal": regime_blocks_signal,
            "learning_recommend_wait": learning_recommend_wait,
            "learning_stronger_confirmation": (
                learning_stronger_confirmation
            ),
            "learning_adjustment_within_limit": (
                abs(learning_confidence_adjustment)
                <= MAXIMUM_LEARNING_CONFIDENCE_ADJUSTMENT
            ),
            "confidence_guardrail_passed": (
                confidence_guardrail_passed
            ),
            "confidence_guardrail_adjustment_within_limit": (
                abs(guardrail_adjustment)
                <= MAXIMUM_LEARNING_CONFIDENCE_ADJUSTMENT
            ),
        },
        "confirmation_reasons": confirmation_reasons,
        "blocking_reasons": blocking_reasons,
        "warnings": warnings,
        "safety_rules": {
            "minimum_final_confidence": (
                MINIMUM_FINAL_CONFIDENCE
            ),
            "minimum_ranking_score": MINIMUM_RANKING_SCORE,
            "minimum_confirmations": MINIMUM_CONFIRMATIONS,
            "minimum_risk_reward_ratio": (
                MINIMUM_RISK_REWARD_RATIO
            ),
            "all_mandatory_engines_must_approve": True,
            "direction_alignment_required": MINIMUM_DIRECTION_ALIGNMENT,
            "hierarchy_conflict_blocks_signal": True,
            "high_risk_environment_blocks_signal": True,
            "weak_signal_quality_blocks_signal": True,
            "market_regime_approval_required_when_provided": True,
            "market_regime_direction_alignment_required": True,
            "fake_breakout_blocks_signal": True,
            "maximum_learning_confidence_adjustment": (
                MAXIMUM_LEARNING_CONFIDENCE_ADJUSTMENT
            ),
            "maximum_confidence_guardrail_adjustment": (
                MAXIMUM_LEARNING_CONFIDENCE_ADJUSTMENT
            ),
            "confidence_guardrail_minimum_completed_trades": 20,
            "confidence_guardrail_minimum_confidence": 80.0,
            "learning_recommend_wait_blocks_signal": True,
            "timeframe_performance_learning_enabled": False,
            "session_performance_learning_enabled": True,
            "broker_connection_enabled": (
                BROKER_CONNECTION_ENABLED
            ),
            "trade_execution_enabled": (
                TRADE_EXECUTION_ENABLED
            ),
        },
        "engine_results": {
            **engine_results,
            "learning_intelligence": (
                learning_intelligence_stats
            ),
            "confidence_guardrail_v30": confidence_guardrail,
        },
        "confidence_guardrail_v30": confidence_guardrail,
        "guardrail_base_confidence": round(
            guardrail_base_confidence,
            2,
        ),
        "guardrail_adjustment": round(
            guardrail_adjustment,
            2,
        ),
        "guardrail_final_confidence": round(
            dynamic_confidence_score,
            2,
        ),
        "guardrail_passed": confidence_guardrail_passed,
        "analysis_only": True,

        "important_notice": (
            "Blue-Trading-AI provides market analysis and signal "
            "recommendations only. It does not connect to brokers "
            "or execute trades."
        ),
    }

__all__ = [
    "BROKER_CONNECTION_ENABLED",
    "MAXIMUM_CONFIRMATIONS",
    "MAXIMUM_LEARNING_CONFIDENCE_ADJUSTMENT",
    "MINIMUM_CONFIRMATIONS",
    "MINIMUM_DIRECTION_ALIGNMENT",
    "MINIMUM_FINAL_CONFIDENCE",
    "MINIMUM_RANKING_SCORE",
    "MINIMUM_RISK_REWARD_RATIO",
    "PROJECT_NAME",
    "SAFETY_VERSION",
    "SUPPORTED_DECISIONS",
    "TRADE_EXECUTION_ENABLED",
    "evaluate_master_signal_pipeline",
]