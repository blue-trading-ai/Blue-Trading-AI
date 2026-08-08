"""Risk calculation helpers for Blue-Trading-AI."""

from __future__ import annotations

import math
from typing import Any, Final


MAXIMUM_SYMBOL_LENGTH: Final[int] = 32
MAXIMUM_PRICE: Final[float] = 1_000_000_000.0
MAXIMUM_PIPS: Final[float] = 1_000_000.0

GOLD_PIP_SIZE: Final[float] = 0.10
JPY_PIP_SIZE: Final[float] = 0.01
FOREX_PIP_SIZE: Final[float] = 0.0001


def _normalise_symbol(
    symbol: Any = "",
) -> str:
    if symbol is None:
        return ""

    text = str(symbol).strip().upper()

    if len(text) > MAXIMUM_SYMBOL_LENGTH:
        return text[:MAXIMUM_SYMBOL_LENGTH]

    return text


def _finite_positive_float(
    value: Any,
    *,
    allow_zero: bool = False,
) -> float | None:
    if isinstance(value, bool):
        return None

    try:
        resolved = float(value)
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None

    if not math.isfinite(resolved):
        return None

    if allow_zero:
        if resolved < 0.0:
            return None
    elif resolved <= 0.0:
        return None

    if resolved > MAXIMUM_PRICE:
        return None

    return resolved


def _normalise_pips(
    value: Any,
) -> float | None:
    if isinstance(value, bool):
        return None

    try:
        resolved = float(value)
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None

    if (
        not math.isfinite(resolved)
        or resolved <= 0.0
        or resolved > MAXIMUM_PIPS
    ):
        return None

    return resolved


def _normalise_signal(
    signal: Any,
) -> str:
    if not isinstance(signal, str):
        return "NONE"

    resolved = signal.strip().upper()

    if resolved in {
        "BUY",
        "SELL",
    }:
        return resolved

    return "NONE"


def format_price(
    price,
    symbol="",
):
    """Format a positive finite price using the symbol's common precision."""

    resolved_price = _finite_positive_float(
        price
    )

    if resolved_price is None:
        return None

    resolved_symbol = _normalise_symbol(
        symbol
    )

    if "XAU" in resolved_symbol:
        digits = 2

    elif "JPY" in resolved_symbol:
        digits = 3

    else:
        digits = 5

    formatted = round(
        resolved_price,
        digits,
    )

    if (
        not math.isfinite(formatted)
        or formatted <= 0.0
    ):
        return None

    return formatted


def get_pip_size(
    symbol="",
):
    """Return the configured pip size for gold, JPY pairs, or standard forex."""

    resolved_symbol = _normalise_symbol(
        symbol
    )

    if "XAU" in resolved_symbol:
        return GOLD_PIP_SIZE

    if "JPY" in resolved_symbol:
        return JPY_PIP_SIZE

    return FOREX_PIP_SIZE


def _calculate_level(
    entry: Any,
    signal: Any,
    pips: Any,
    symbol: Any,
    *,
    buy_adds: bool,
) -> float | None:
    resolved_entry = _finite_positive_float(
        entry
    )
    resolved_signal = _normalise_signal(
        signal
    )
    resolved_pips = _normalise_pips(
        pips
    )

    if (
        resolved_entry is None
        or resolved_signal == "NONE"
        or resolved_pips is None
    ):
        return None

    pip_size = get_pip_size(
        symbol
    )

    distance = (
        resolved_pips
        * pip_size
    )

    if (
        not math.isfinite(distance)
        or distance <= 0.0
    ):
        return None

    if resolved_signal == "BUY":
        level = (
            resolved_entry + distance
            if buy_adds
            else resolved_entry - distance
        )

    else:
        level = (
            resolved_entry - distance
            if buy_adds
            else resolved_entry + distance
        )

    if (
        not math.isfinite(level)
        or level <= 0.0
    ):
        return None

    return format_price(
        level,
        symbol,
    )


def calculate_stop_loss(
    entry,
    signal,
    pips=150,
    symbol="",
):
    """Calculate stop-loss distance from entry using the configured pip size."""

    return _calculate_level(
        entry,
        signal,
        pips,
        symbol,
        buy_adds=False,
    )


def calculate_take_profit_1(
    entry,
    signal,
    pips=100,
    symbol="",
):
    """Calculate first take-profit distance from entry."""

    return _calculate_level(
        entry,
        signal,
        pips,
        symbol,
        buy_adds=True,
    )


def calculate_take_profit_2(
    entry,
    signal,
    pips=300,
    symbol="",
):
    """Calculate second take-profit distance from entry."""

    return _calculate_level(
        entry,
        signal,
        pips,
        symbol,
        buy_adds=True,
    )


def calculate_risk_reward(
    entry,
    stop_loss,
    take_profit,
    symbol="",
):
    """Return absolute risk, reward, and reward-to-risk ratio."""

    resolved_entry = _finite_positive_float(
        entry
    )
    resolved_stop = _finite_positive_float(
        stop_loss
    )
    resolved_take_profit = (
        _finite_positive_float(
            take_profit
        )
    )

    if (
        resolved_entry is None
        or resolved_stop is None
        or resolved_take_profit is None
    ):
        return {
            "risk": None,
            "reward": None,
            "risk_reward": None,
        }

    risk = abs(
        resolved_entry
        - resolved_stop
    )

    reward = abs(
        resolved_take_profit
        - resolved_entry
    )

    if (
        not math.isfinite(risk)
        or not math.isfinite(reward)
        or risk <= 0.0
    ):
        return {
            "risk": (
                format_price(
                    risk,
                    symbol,
                )
                if risk > 0.0
                else None
            ),
            "reward": (
                format_price(
                    reward,
                    symbol,
                )
                if reward > 0.0
                else None
            ),
            "risk_reward": None,
        }

    ratio = (
        reward
        / risk
    )

    if (
        not math.isfinite(ratio)
        or ratio < 0.0
    ):
        return {
            "risk": format_price(
                risk,
                symbol,
            ),
            "reward": format_price(
                reward,
                symbol,
            ),
            "risk_reward": None,
        }

    return {
        "risk": format_price(
            risk,
            symbol,
        ),
        "reward": format_price(
            reward,
            symbol,
        ),
        "risk_reward": round(
            ratio,
            2,
        ),
    }


__all__ = [
    "FOREX_PIP_SIZE",
    "GOLD_PIP_SIZE",
    "JPY_PIP_SIZE",
    "calculate_risk_reward",
    "calculate_stop_loss",
    "calculate_take_profit_1",
    "calculate_take_profit_2",
    "format_price",
    "get_pip_size",
]