"""
Market Alignment Engine for Blue-Trading-AI.

This module compares the major directional modules and applies a penalty
when the final BUY or SELL setup conflicts with important market evidence.
"""

from __future__ import annotations

import math
from typing import Any, Final, Mapping


MAXIMUM_DIRECTION_LENGTH: Final[int] = 64
MAXIMUM_SCORE: Final[float] = 100.0

MODULE_WEIGHTS: Final[dict[str, int]] = {
    "trend": 10,
    "market_structure": 20,
    "bos": 10,
    "choch": 10,
    "trendline": 10,
    "fair_value_gap": 5,
    "candlestick": 5,
    "multi_timeframe": 15,
}

MAXIMUM_ALIGNMENT_PENALTY: Final[int] = sum(
    MODULE_WEIGHTS.values()
)


def _normalise_direction(
    value: object,
) -> str:
    if not isinstance(value, str):
        return "NEUTRAL"

    resolved = value.strip().upper()

    if (
        not resolved
        or len(resolved) > MAXIMUM_DIRECTION_LENGTH
    ):
        return "NEUTRAL"

    bullish_values = {
        "BUY",
        "BULLISH",
        "UPTREND",
        "HH-HL",
        "BULLISH_BOS",
        "BULLISH_CHOCH",
        "BULLISH_FVG",
        "BULLISH_ORDER_BLOCK",
        "BULLISH_LIQUIDITY_SWEEP",
        "BULLISH_BREAK",
        "BULLISH_OTE",
        "DISCOUNT",
    }

    bearish_values = {
        "SELL",
        "BEARISH",
        "DOWNTREND",
        "LH-LL",
        "BEARISH_BOS",
        "BEARISH_CHOCH",
        "BEARISH_FVG",
        "BEARISH_ORDER_BLOCK",
        "BEARISH_LIQUIDITY_SWEEP",
        "BEARISH_BREAK",
        "BEARISH_OTE",
        "PREMIUM",
    }

    if resolved in bullish_values:
        return "BULLISH"

    if resolved in bearish_values:
        return "BEARISH"

    return "NEUTRAL"


def evaluate_market_alignment(
    *,
    proposed_direction: str,
    trend: str = "NONE",
    market_structure: str = "NONE",
    bos: str = "NONE",
    choch: str = "NONE",
    trendline: str = "NONE",
    fair_value_gap: str = "NONE",
    candlestick: str = "NONE",
    multi_timeframe: str = "NONE",
) -> dict:
    """
    Evaluate whether major directional modules agree with a proposed trade.

    Penalty weights:
    - Market structure conflict: 20
    - Multi-timeframe conflict: 15
    - Current trend conflict: 10
    - BOS conflict: 10
    - CHoCH conflict: 10
    - Trendline conflict: 10
    - FVG conflict: 5
    - Candlestick conflict: 5
    """

    target = _normalise_direction(
        proposed_direction
    )

    if target == "NEUTRAL":
        return {
            "proposed_direction": "NONE",
            "aligned": False,
            "status": "NO_DIRECTION",
            "alignment_score": 0.0,
            "penalty": 0,
            "supporting_modules": [],
            "conflicting_modules": [],
            "neutral_modules": [],
            "module_directions": {},
        }

    raw_directions = {
        "trend": trend,
        "market_structure": market_structure,
        "bos": bos,
        "choch": choch,
        "trendline": trendline,
        "fair_value_gap": fair_value_gap,
        "candlestick": candlestick,
        "multi_timeframe": multi_timeframe,
    }

    supporting: list[str] = []
    conflicting: list[str] = []
    neutral: list[str] = []
    module_directions: dict[str, str] = {}

    available_weight = 0
    supporting_weight = 0
    penalty = 0

    for module_name, weight in MODULE_WEIGHTS.items():
        raw_direction = raw_directions.get(
            module_name,
            "NONE",
        )

        direction = _normalise_direction(
            raw_direction
        )

        module_directions[
            module_name
        ] = direction

        if direction == "NEUTRAL":
            neutral.append(
                module_name
            )
            continue

        available_weight += weight

        if direction == target:
            supporting.append(
                module_name
            )
            supporting_weight += weight
        else:
            conflicting.append(
                module_name
            )
            penalty += weight

    penalty = max(
        0,
        min(
            MAXIMUM_ALIGNMENT_PENALTY,
            int(penalty),
        ),
    )

    if available_weight <= 0:
        alignment_score = 0.0
    else:
        calculated_score = (
            supporting_weight
            / available_weight
            * 100.0
        )

        if not math.isfinite(
            calculated_score
        ):
            alignment_score = 0.0
        else:
            alignment_score = round(
                max(
                    0.0,
                    min(
                        100.0,
                        calculated_score,
                    ),
                ),
                2,
            )

    if (
        not conflicting
        and supporting
    ):
        status = "FULLY_ALIGNED"
    elif alignment_score >= 75.0:
        status = "STRONGLY_ALIGNED"
    elif alignment_score >= 60.0:
        status = "MODERATELY_ALIGNED"
    elif alignment_score >= 40.0:
        status = "MIXED"
    else:
        status = "CONFLICTED"

    return {
        "proposed_direction": target,
        "aligned": (
            alignment_score >= 60.0
        ),
        "status": status,
        "alignment_score": (
            alignment_score
        ),
        "penalty": penalty,
        "supporting_modules": list(
            supporting
        ),
        "conflicting_modules": list(
            conflicting
        ),
        "neutral_modules": list(
            neutral
        ),
        "module_directions": dict(
            module_directions
        ),
    }


def apply_alignment_penalty(
    score: int | float,
    alignment_result: dict,
) -> int:
    """
    Apply the calculated alignment penalty without allowing a negative score.

    Invalid or malformed inputs fail closed to a score of zero.
    """

    if isinstance(score, bool):
        return 0

    try:
        resolved_score = float(
            score
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return 0

    if (
        not math.isfinite(
            resolved_score
        )
        or resolved_score < 0.0
    ):
        return 0

    resolved_score = min(
        MAXIMUM_SCORE,
        resolved_score,
    )

    if not isinstance(
        alignment_result,
        Mapping,
    ):
        return 0

    raw_penalty = alignment_result.get(
        "penalty",
        0,
    )

    if isinstance(raw_penalty, bool):
        return 0

    try:
        penalty = float(
            raw_penalty
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return 0

    if (
        not math.isfinite(penalty)
        or penalty < 0.0
        or penalty
        > MAXIMUM_ALIGNMENT_PENALTY
    ):
        return 0

    adjusted = (
        resolved_score
        - penalty
    )

    if not math.isfinite(
        adjusted
    ):
        return 0

    return max(
        0,
        min(
            100,
            int(
                round(
                    adjusted
                )
            ),
        ),
    )


__all__ = [
    "MAXIMUM_ALIGNMENT_PENALTY",
    "MODULE_WEIGHTS",
    "apply_alignment_penalty",
    "evaluate_market_alignment",
]