"""Blue-Trading-AI Trade Quality Engine.

This module evaluates the quality of a completed signal decision without
overriding the Signal Engine's safety gates.

It does not create BUY or SELL signals. It only grades the setup already
produced by signal_engine.py.
"""

from __future__ import annotations

import math
from typing import Any, Final, Mapping


EXECUTABLE_SIGNALS: Final[frozenset[str]] = frozenset(
    {
        "BUY",
        "STRONG BUY",
        "SELL",
        "STRONG SELL",
    }
)

MAXIMUM_TEXT_LENGTH: Final[int] = 128
MAXIMUM_CONFIRMATIONS: Final[int] = 1_000
MAXIMUM_REASON_ITEMS: Final[int] = 50


def _safe_bool(
    value: Any,
    *,
    default: bool = False,
) -> bool:
    if isinstance(value, bool):
        return value

    if value is None:
        return default

    if isinstance(value, (int, float)):
        try:
            number = float(value)
        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            return default

        if not math.isfinite(number):
            return default

        if number == 1.0:
            return True

        if number == 0.0:
            return False

        return default

    if isinstance(value, str):
        text = value.strip().lower()

        if text in {
            "true",
            "1",
            "yes",
            "y",
            "on",
        }:
            return True

        if text in {
            "false",
            "0",
            "no",
            "n",
            "off",
            "",
            "none",
            "null",
        }:
            return False

    return default


def _safe_number(
    value: Any,
    *,
    default: float = 0.0,
) -> float:
    if isinstance(value, bool):
        return default

    try:
        resolved = float(value)
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return default

    if not math.isfinite(resolved):
        return default

    return resolved


def _safe_int(
    value: Any,
    *,
    default: int = 0,
    minimum: int = 0,
    maximum: int = MAXIMUM_CONFIRMATIONS,
) -> int:
    if isinstance(value, bool):
        return default

    try:
        resolved = int(value)
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return default

    return max(
        minimum,
        min(
            maximum,
            resolved,
        ),
    )


def _safe_mapping(
    value: Any,
) -> dict[str, Any]:
    if not isinstance(
        value,
        Mapping,
    ):
        return {}

    return dict(value)


def _safe_text(
    value: Any,
    *,
    default: str = "UNKNOWN",
) -> str:
    text = str(
        value
        if value is not None
        else default
    ).strip()

    if not text:
        text = default

    return text[
        :MAXIMUM_TEXT_LENGTH
    ]


def _clamp(
    value: int | float,
    minimum: int = 0,
    maximum: int = 100,
) -> int:
    number = _safe_number(
        value,
        default=float(minimum),
    )

    return max(
        minimum,
        min(
            maximum,
            int(
                round(number)
            ),
        ),
    )


def _deduplicate(
    items: list[str],
) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()

    for item in items:
        text = _safe_text(
            item,
            default="",
        )

        if (
            not text
            or text in seen
        ):
            continue

        seen.add(text)
        output.append(text)

        if len(output) >= MAXIMUM_REASON_ITEMS:
            break

    return output


def evaluate_trade_quality(
    *,
    signal: str,
    trade_allowed: bool,
    confidence: int | float,
    directional_confidence: int | float,
    confirmations: int,
    minimum_confirmations: int,
    alignment: dict[str, Any] | None,
    market_regime: dict[str, Any] | None,
    retest_confirmation: dict[str, Any] | None,
    entry_valid: bool,
    structure_confirmed: bool,
    atr_volatility: dict[str, Any] | None = None,
    session_analysis: dict[str, Any] | None = None,
    risk_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Grade a completed Blue-Trading-AI setup.

    The score is descriptive only. It cannot bypass:
    - minimum confidence
    - minimum confirmations
    - market alignment
    - entry validation
    - market structure confirmation
    - retest confirmation
    - Signal Engine trade permission
    """

    normalized_signal = str(
        signal or ""
    ).strip().upper()[
        :MAXIMUM_TEXT_LENGTH
    ]

    alignment = _safe_mapping(
        alignment
    )
    market_regime = _safe_mapping(
        market_regime
    )
    retest_confirmation = _safe_mapping(
        retest_confirmation
    )
    atr_volatility = _safe_mapping(
        atr_volatility
    )
    session_analysis = _safe_mapping(
        session_analysis
    )
    risk_plan = _safe_mapping(
        risk_plan
    )

    resolved_confirmations = _safe_int(
        confirmations,
        minimum=0,
        maximum=MAXIMUM_CONFIRMATIONS,
    )
    resolved_minimum_confirmations = _safe_int(
        minimum_confirmations,
        default=1,
        minimum=1,
        maximum=MAXIMUM_CONFIRMATIONS,
    )

    resolved_confidence = _clamp(
        confidence
    )
    resolved_directional_confidence = _clamp(
        directional_confidence
    )

    executable = (
        normalized_signal
        in EXECUTABLE_SIGNALS
        and trade_allowed is True
    )

    aligned = _safe_bool(
        alignment.get(
            "aligned",
            False,
        )
    )
    regime_allowed = _safe_bool(
        market_regime.get(
            "trade_allowed",
            False,
        )
    )
    retest_confirmed = _safe_bool(
        retest_confirmation.get(
            "confirmed",
            False,
        )
    )
    risk_calculated = _safe_bool(
        risk_plan.get(
            "calculated",
            False,
        )
    )
    resolved_entry_valid = (
        entry_valid is True
    )
    resolved_structure_confirmed = (
        structure_confirmed is True
    )

    strengths: list[str] = []
    weaknesses: list[str] = []

    score = _clamp(
        resolved_confidence
        if executable
        else resolved_directional_confidence
    )

    if (
        resolved_confirmations
        >= resolved_minimum_confirmations
    ):
        strengths.append(
            (
                f"{resolved_confirmations} confirmations meet "
                "the minimum requirement"
            )
        )

        score += min(
            10,
            (
                resolved_confirmations
                - resolved_minimum_confirmations
                + 1
            )
            * 2,
        )
    else:
        weaknesses.append(
            (
                f"Only {resolved_confirmations} confirmations; "
                f"{resolved_minimum_confirmations} are required"
            )
        )
        score -= 20

    if aligned:
        strengths.append(
            "Major market modules are aligned"
        )
        score += 8
    else:
        weaknesses.append(
            "Major market modules are not sufficiently aligned"
        )
        score -= 20

    regime_name = _safe_text(
        market_regime.get(
            "regime",
            "UNKNOWN",
        )
    )

    if regime_allowed:
        strengths.append(
            (
                "Market regime permits execution: "
                f"{regime_name}"
            )
        )
        score += 5
    else:
        weaknesses.append(
            (
                "Market regime does not permit execution: "
                f"{regime_name}"
            )
        )
        score -= 15

    if resolved_entry_valid:
        strengths.append(
            "Entry location passed validation"
        )
        score += 8
    else:
        weaknesses.append(
            "Entry location did not pass validation"
        )
        score -= 20

    if resolved_structure_confirmed:
        strengths.append(
            "Market structure confirms the proposed direction"
        )
        score += 8
    else:
        weaknesses.append(
            "Market structure does not confirm the direction"
        )
        score -= 20

    retest_status = _safe_text(
        retest_confirmation.get(
            "status",
            "UNKNOWN",
        )
    ).upper()

    if retest_confirmed:
        strengths.append(
            "Retest and rejection are confirmed"
        )
        score += 8
    elif retest_status == "WAITING_FOR_RETEST":
        weaknesses.append(
            "Waiting for a valid retest and rejection"
        )
        score -= 10

    atr_environment = _safe_text(
        atr_volatility.get(
            "trade_environment",
            "UNKNOWN",
        )
    ).upper()

    if atr_environment == "FAVORABLE":
        strengths.append(
            "ATR volatility environment is favorable"
        )
        score += 4
    elif atr_environment in {
        "UNFAVORABLE",
        "UNSAFE",
    }:
        weaknesses.append(
            "ATR volatility environment is unfavorable"
        )
        score -= 8

    if _safe_bool(
        session_analysis.get(
            "actionable",
            False,
        )
    ):
        current_session = _safe_text(
            session_analysis.get(
                "primary_session",
                session_analysis.get(
                    "current_session",
                    "ACTIVE",
                ),
            )
        )

        strengths.append(
            (
                f"{current_session} session is actionable"
            )
        )
        score += 3
    else:
        weaknesses.append(
            "Current trading session is not actionable"
        )
        score -= 5

    if (
        executable
        and risk_calculated
    ):
        strengths.append(
            "SL and take-profit levels were calculated"
        )
        score += 5
    elif (
        executable
        and not risk_calculated
    ):
        weaknesses.append(
            "Executable trade has no calculated risk plan"
        )
        score -= 25

    # A blocked setup must never receive an execution-grade score.
    if not executable:
        score = min(
            score,
            69,
        )

    score = _clamp(
        score
    )

    if executable:
        if score >= 90:
            grade = "A+"
            status = "ELITE"
            risk_level = "LOW"

        elif score >= 85:
            grade = "A"
            status = "HIGH_QUALITY"
            risk_level = "LOW"

        elif score >= 80:
            grade = "B+"
            status = "GOOD"
            risk_level = "MODERATE"

        elif score >= 75:
            grade = "B"
            status = "ACCEPTABLE"
            risk_level = "MODERATE"

        else:
            grade = "C"
            status = "WEAK_EXECUTABLE_SETUP"
            risk_level = "HIGH"

        recommendation = (
            "TRADE_ALLOWED_WITH_DEFINED_RISK"
        )

    else:
        if (
            normalized_signal
            == "WAIT FOR RETEST"
            or retest_status
            == "WAITING_FOR_RETEST"
        ):
            grade = "WAIT"
            status = "WAITING_FOR_RETEST"
            recommendation = (
                "WAIT_FOR_RETEST_CONFIRMATION"
            )

        else:
            grade = "N/A"
            status = "NO_TRADE"
            recommendation = (
                "WAIT_FOR_VALID_SETUP"
            )

        risk_level = "NOT_APPLICABLE"

    return {
        "score": score,
        "grade": grade,
        "status": status,
        "risk_level": risk_level,
        "trade_allowed": executable,
        "strengths": _deduplicate(
            strengths
        ),
        "weaknesses": _deduplicate(
            weaknesses
        ),
        "recommendation": recommendation,
        "rules": {
            "descriptive_only": True,
            "can_override_signal_engine": False,
            "minimum_confirmations": (
                resolved_minimum_confirmations
            ),
        },
    }


__all__ = [
    "EXECUTABLE_SIGNALS",
    "MAXIMUM_CONFIRMATIONS",
    "evaluate_trade_quality",
]