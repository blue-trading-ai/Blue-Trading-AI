"""Blue-Trading-AI fixed-distance SL/TP engine.

The project calls this a Dynamic SL/TP Engine because it calculates levels
from the live entry price and trade direction. The configured distances are
currently global for every symbol:

Stop loss: 15.00 price units
TP1:       10.00 price units
TP2:       30.00 price units

Levels are returned only for executable BUY/SELL signals.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Final


FIXED_STOP_LOSS_DISTANCE: Final[Decimal] = Decimal("15.00")
FIXED_TAKE_PROFIT_1_DISTANCE: Final[Decimal] = Decimal("10.00")
FIXED_TAKE_PROFIT_2_DISTANCE: Final[Decimal] = Decimal("30.00")

PRICE_DECIMALS: Final[int] = 2
MAXIMUM_SIGNAL_LENGTH: Final[int] = 64
MAXIMUM_PRICE: Final[Decimal] = Decimal("1000000000")
MAXIMUM_DISTANCE: Final[Decimal] = Decimal("100000000")

BUY_SIGNALS: Final[frozenset[str]] = frozenset(
    {
        "BUY",
        "STRONG BUY",
    }
)

SELL_SIGNALS: Final[frozenset[str]] = frozenset(
    {
        "SELL",
        "STRONG SELL",
    }
)

EXECUTABLE_SIGNALS: Final[frozenset[str]] = (
    BUY_SIGNALS
    | SELL_SIGNALS
)


def _to_decimal(
    value: Any,
    field_name: str,
) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(
            f"{field_name} must be a valid number"
        )

    try:
        result = Decimal(
            str(value)
        )
    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            f"{field_name} must be a valid number"
        ) from exc

    if not result.is_finite():
        raise ValueError(
            f"{field_name} must be finite"
        )

    return result


def _validate_positive_decimal(
    value: Any,
    field_name: str,
    *,
    maximum: Decimal,
) -> Decimal:
    result = _to_decimal(
        value,
        field_name,
    )

    if result <= 0:
        raise ValueError(
            f"{field_name} must be greater than zero"
        )

    if result > maximum:
        raise ValueError(
            f"{field_name} exceeds the maximum allowed value"
        )

    return result


def _normalise_signal(
    value: Any,
) -> str:
    if not isinstance(value, str):
        return ""

    resolved = value.strip().upper()

    if (
        not resolved
        or len(resolved) > MAXIMUM_SIGNAL_LENGTH
    ):
        return ""

    return resolved


def _approved_trade(
    value: Any,
) -> bool:
    return value is True


def _round_price(
    value: Decimal,
) -> float:
    if not isinstance(value, Decimal):
        value = _to_decimal(
            value,
            "price",
        )

    if not value.is_finite():
        raise ValueError(
            "price must be finite"
        )

    quantum = Decimal("1").scaleb(
        -PRICE_DECIMALS
    )

    try:
        rounded = value.quantize(
            quantum,
            rounding=ROUND_HALF_UP,
        )
    except InvalidOperation as exc:
        raise ValueError(
            "price cannot be rounded safely"
        ) from exc

    if not rounded.is_finite():
        raise ValueError(
            "rounded price must be finite"
        )

    return float(
        rounded
    )


@dataclass(frozen=True)
class RiskDistances:
    stop_loss: Decimal = FIXED_STOP_LOSS_DISTANCE
    take_profit_1: Decimal = FIXED_TAKE_PROFIT_1_DISTANCE
    take_profit_2: Decimal = FIXED_TAKE_PROFIT_2_DISTANCE

    def validate(self) -> None:
        stop_loss = _validate_positive_decimal(
            self.stop_loss,
            "stop_loss",
            maximum=MAXIMUM_DISTANCE,
        )
        take_profit_1 = _validate_positive_decimal(
            self.take_profit_1,
            "take_profit_1",
            maximum=MAXIMUM_DISTANCE,
        )
        take_profit_2 = _validate_positive_decimal(
            self.take_profit_2,
            "take_profit_2",
            maximum=MAXIMUM_DISTANCE,
        )

        if take_profit_2 <= take_profit_1:
            raise ValueError(
                "TP2 distance must be greater than TP1 distance"
            )

        object.__setattr__(
            self,
            "stop_loss",
            stop_loss,
        )
        object.__setattr__(
            self,
            "take_profit_1",
            take_profit_1,
        )
        object.__setattr__(
            self,
            "take_profit_2",
            take_profit_2,
        )


def _blocked_result(
    selected: RiskDistances,
) -> dict[str, Any]:
    return {
        "calculated": False,
        "trade_allowed": False,
        "direction": None,
        "entry_price": None,
        "stop_loss": None,
        "take_profit_1": None,
        "take_profit_2": None,
        "stop_loss_distance": float(
            selected.stop_loss
        ),
        "take_profit_1_distance": float(
            selected.take_profit_1
        ),
        "take_profit_2_distance": float(
            selected.take_profit_2
        ),
        "risk_reward_tp1": None,
        "risk_reward_tp2": None,
        "model": "GLOBAL_FIXED_PRICE_DISTANCE",
        "reason": (
            "Risk levels are generated only for an approved BUY or SELL trade"
        ),
    }


def calculate_fixed_sl_tp(
    *,
    entry_price: float,
    signal: str,
    trade_allowed: bool,
    distances: RiskDistances | None = None,
) -> dict[str, Any]:
    """Calculate the complete Blue-Trading-AI risk plan.

    BUY:
        SL  = entry - 15.00
        TP1 = entry + 10.00
        TP2 = entry + 30.00

    SELL:
        SL  = entry + 15.00
        TP1 = entry - 10.00
        TP2 = entry - 30.00

    For WAIT FOR RETEST, NO TRADE, or any blocked setup, all price levels remain
    ``None``.
    """

    normalized_signal = _normalise_signal(
        signal
    )

    if distances is None:
        selected = RiskDistances()
    elif isinstance(
        distances,
        RiskDistances,
    ):
        selected = distances
    else:
        raise ValueError(
            "distances must be a RiskDistances instance"
        )

    selected.validate()

    blocked_result = _blocked_result(
        selected
    )

    if (
        not _approved_trade(
            trade_allowed
        )
        or normalized_signal
        not in EXECUTABLE_SIGNALS
    ):
        return blocked_result

    entry = _validate_positive_decimal(
        entry_price,
        "entry_price",
        maximum=MAXIMUM_PRICE,
    )

    if normalized_signal in BUY_SIGNALS:
        direction = "BUY"
        stop_loss = (
            entry
            - selected.stop_loss
        )
        take_profit_1 = (
            entry
            + selected.take_profit_1
        )
        take_profit_2 = (
            entry
            + selected.take_profit_2
        )

    else:
        direction = "SELL"
        stop_loss = (
            entry
            + selected.stop_loss
        )
        take_profit_1 = (
            entry
            - selected.take_profit_1
        )
        take_profit_2 = (
            entry
            - selected.take_profit_2
        )

    for field_name, level in (
        (
            "stop_loss",
            stop_loss,
        ),
        (
            "take_profit_1",
            take_profit_1,
        ),
        (
            "take_profit_2",
            take_profit_2,
        ),
    ):
        if (
            not level.is_finite()
            or level <= 0
            or level > MAXIMUM_PRICE
        ):
            raise ValueError(
                f"Calculated {field_name} is not a valid positive price"
            )

    risk_reward_tp1 = (
        selected.take_profit_1
        / selected.stop_loss
    )
    risk_reward_tp2 = (
        selected.take_profit_2
        / selected.stop_loss
    )

    if (
        not risk_reward_tp1.is_finite()
        or not risk_reward_tp2.is_finite()
        or risk_reward_tp1 < 0
        or risk_reward_tp2 < 0
    ):
        raise ValueError(
            "Calculated risk-reward ratio is invalid"
        )

    return {
        "calculated": True,
        "trade_allowed": True,
        "direction": direction,
        "entry_price": _round_price(
            entry
        ),
        "stop_loss": _round_price(
            stop_loss
        ),
        "take_profit_1": _round_price(
            take_profit_1
        ),
        "take_profit_2": _round_price(
            take_profit_2
        ),
        "stop_loss_distance": float(
            selected.stop_loss
        ),
        "take_profit_1_distance": float(
            selected.take_profit_1
        ),
        "take_profit_2_distance": float(
            selected.take_profit_2
        ),
        "risk_reward_tp1": round(
            float(
                risk_reward_tp1
            ),
            2,
        ),
        "risk_reward_tp2": round(
            float(
                risk_reward_tp2
            ),
            2,
        ),
        "model": "GLOBAL_FIXED_PRICE_DISTANCE",
        "reason": (
            "Approved trade: global fixed price-distance risk model applied"
        ),
    }


__all__ = [
    "BUY_SIGNALS",
    "EXECUTABLE_SIGNALS",
    "FIXED_STOP_LOSS_DISTANCE",
    "FIXED_TAKE_PROFIT_1_DISTANCE",
    "FIXED_TAKE_PROFIT_2_DISTANCE",
    "PRICE_DECIMALS",
    "RiskDistances",
    "SELL_SIGNALS",
    "calculate_fixed_sl_tp",
]