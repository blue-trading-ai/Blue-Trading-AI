"""
Blue-Trading-AI
Version 27
learning_intelligence_service.py
Updated implementation (core logic)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Final


SUPPORTED_RESULTS: Final = frozenset(
    {
        "WIN",
        "LOSS",
        "BREAKEVEN",
    }
)
SUPPORTED_DIRECTIONS: Final = frozenset(
    {
        "BUY",
        "SELL",
    }
)
SUPPORTED_SESSIONS: Final = frozenset(
    {
        "asian",
        "european",
        "us",
    }
)

MAXIMUM_SYMBOL_LENGTH: Final = 30
MAXIMUM_MARKET_CONDITION_LENGTH: Final = 80


def _safe_float(
    value: object,
    default: float = 0.0,
) -> float:
    """Convert a value into a finite float."""

    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default

    if not math.isfinite(number):
        return default

    return number


def _normalize_datetime(
    value: datetime,
    field_name: str,
) -> datetime:
    if not isinstance(
        value,
        datetime,
    ):
        raise ValueError(
            f"{field_name} must be a datetime."
        )

    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


def _normalize_symbol(
    value: object,
) -> str:
    normalized = (
        str(value or "")
        .strip()
        .upper()
        .replace("/", "")
        .replace("-", "")
        .replace("_", "")
        .replace(" ", "")
    )

    if not normalized:
        raise ValueError(
            "symbol is required."
        )

    if len(normalized) > MAXIMUM_SYMBOL_LENGTH:
        raise ValueError(
            "symbol is too long."
        )

    if not normalized.isalnum():
        raise ValueError(
            "symbol contains unsupported characters."
        )

    return normalized


def _normalize_session(
    value: object,
) -> str:
    normalized = str(
        value or ""
    ).strip().lower()

    if normalized not in SUPPORTED_SESSIONS:
        raise ValueError(
            "session must be asian, european, or us."
        )

    return normalized


def _normalize_market_condition(
    value: object,
) -> str:
    normalized = (
        str(value or "")
        .strip()
        .lower()
        .replace(" ", "_")
    )

    if not normalized:
        normalized = "unknown"

    if len(
        normalized
    ) > MAXIMUM_MARKET_CONDITION_LENGTH:
        raise ValueError(
            "market_condition is too long."
        )

    allowed_characters = set(
        "abcdefghijklmnopqrstuvwxyz0123456789_-"
    )

    if any(
        character not in allowed_characters
        for character in normalized
    ):
        raise ValueError(
            "market_condition contains unsupported characters."
        )

    return normalized


def _normalize_direction(
    value: object,
) -> str:
    normalized = str(
        value or ""
    ).strip().upper()

    if normalized not in SUPPORTED_DIRECTIONS:
        raise ValueError(
            "direction must be BUY or SELL."
        )

    return normalized


def _normalize_result(
    value: object,
) -> str:
    normalized = str(
        value or ""
    ).strip().upper()

    if normalized not in SUPPORTED_RESULTS:
        raise ValueError(
            "result must be WIN, LOSS, or BREAKEVEN."
        )

    return normalized


@dataclass
class LearningTrade:
    symbol: str
    session: str
    market_condition: str
    direction: str
    confidence: float
    risk_reward: float
    result: str
    entry_price: float
    stop_loss: float
    take_profit: float
    opened_at: datetime
    closed_at: datetime


@dataclass
class LearningStatistics:
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakeven: int = 0
    win_rate: float = 0.0
    average_confidence: float = 0.0
    average_rr: float = 0.0
    current_win_streak: int = 0
    current_loss_streak: int = 0
    highest_win_streak: int = 0
    highest_loss_streak: int = 0


@dataclass
class LearningRecommendation:
    confidence_adjustment: int = 0
    increase_confidence: bool = False
    reduce_confidence: bool = False
    stronger_confirmation: bool = False
    recommend_wait: bool = False
    reason: str = ""


class LearningIntelligenceService:
    MINIMUM_TRADES: Final = 20
    MAX_ADJUSTMENT: Final = 4

    def __init__(self) -> None:
        self.trade_history: list[LearningTrade] = []
        self.symbol_statistics: dict[
            str,
            LearningStatistics,
        ] = {}
        self.session_statistics: dict[
            str,
            LearningStatistics,
        ] = {}
        self.market_statistics: dict[
            str,
            LearningStatistics,
        ] = {}
        self._lock = RLock()

    def _stats(
        self,
        container: dict[str, LearningStatistics],
        key: str,
    ) -> LearningStatistics:
        stats = container.get(
            key
        )

        if stats is None:
            stats = LearningStatistics()
            container[key] = stats

        return stats

    def _update(
        self,
        stats: LearningStatistics,
        trade: LearningTrade,
    ) -> None:
        stats.total_trades += 1

        if trade.result == "WIN":
            stats.wins += 1
            stats.current_win_streak += 1
            stats.current_loss_streak = 0
            stats.highest_win_streak = max(
                stats.highest_win_streak,
                stats.current_win_streak,
            )

        elif trade.result == "LOSS":
            stats.losses += 1
            stats.current_loss_streak += 1
            stats.current_win_streak = 0
            stats.highest_loss_streak = max(
                stats.highest_loss_streak,
                stats.current_loss_streak,
            )

        else:
            stats.breakeven += 1
            stats.current_win_streak = 0
            stats.current_loss_streak = 0

        stats.win_rate = (
            stats.wins
            / stats.total_trades
            * 100.0
            if stats.total_trades > 0
            else 0.0
        )

        count = stats.total_trades

        stats.average_confidence = (
            (
                stats.average_confidence
                * (count - 1)
            )
            + trade.confidence
        ) / count

        stats.average_rr = (
            (
                stats.average_rr
                * (count - 1)
            )
            + trade.risk_reward
        ) / count

    def add_completed_trade(
        self,
        trade: LearningTrade,
    ) -> None:
        if not isinstance(
            trade,
            LearningTrade,
        ):
            raise TypeError(
                "trade must be a LearningTrade."
            )

        opened_at = _normalize_datetime(
            trade.opened_at,
            "opened_at",
        )
        closed_at = _normalize_datetime(
            trade.closed_at,
            "closed_at",
        )

        if closed_at < opened_at:
            raise ValueError(
                "closed_at cannot be earlier than opened_at."
            )

        confidence = _safe_float(
            trade.confidence,
            default=float("nan"),
        )
        risk_reward = _safe_float(
            trade.risk_reward,
            default=float("nan"),
        )
        entry_price = _safe_float(
            trade.entry_price,
            default=float("nan"),
        )
        stop_loss = _safe_float(
            trade.stop_loss,
            default=float("nan"),
        )
        take_profit = _safe_float(
            trade.take_profit,
            default=float("nan"),
        )

        if not all(
            math.isfinite(value)
            for value in (
                confidence,
                risk_reward,
                entry_price,
                stop_loss,
                take_profit,
            )
        ):
            raise ValueError(
                "Completed trade contains a non-finite numeric value."
            )

        if not 0.0 <= confidence <= 100.0:
            raise ValueError(
                "confidence must be between 0 and 100."
            )

        if risk_reward < 0.0:
            raise ValueError(
                "risk_reward cannot be negative."
            )

        if min(
            entry_price,
            stop_loss,
            take_profit,
        ) < 0.0:
            raise ValueError(
                "Trade prices cannot be negative."
            )

        normalized_trade = LearningTrade(
            symbol=_normalize_symbol(
                trade.symbol
            ),
            session=_normalize_session(
                trade.session
            ),
            market_condition=_normalize_market_condition(
                trade.market_condition
            ),
            direction=_normalize_direction(
                trade.direction
            ),
            confidence=confidence,
            risk_reward=risk_reward,
            result=_normalize_result(
                trade.result
            ),
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            opened_at=opened_at,
            closed_at=closed_at,
        )

        with self._lock:
            self.trade_history.append(
                normalized_trade
            )

            self._update(
                self._stats(
                    self.symbol_statistics,
                    normalized_trade.symbol,
                ),
                normalized_trade,
            )
            self._update(
                self._stats(
                    self.session_statistics,
                    normalized_trade.session,
                ),
                normalized_trade,
            )
            self._update(
                self._stats(
                    self.market_statistics,
                    normalized_trade.market_condition,
                ),
                normalized_trade,
            )

    def _adjustment(
        self,
        win_rate: float,
    ) -> int:
        normalized_win_rate = max(
            0.0,
            min(
                100.0,
                _safe_float(
                    win_rate,
                    0.0,
                ),
            ),
        )

        if normalized_win_rate >= 90.0:
            return 4
        if normalized_win_rate >= 85.0:
            return 3
        if normalized_win_rate >= 80.0:
            return 2
        if normalized_win_rate >= 75.0:
            return 1
        if normalized_win_rate >= 65.0:
            return 0
        if normalized_win_rate >= 55.0:
            return -1
        if normalized_win_rate >= 45.0:
            return -2

        return -4

    def evaluate_learning(
        self,
        symbol: str,
        session: str,
        market_condition: str,
        direction: str,
    ) -> LearningRecommendation:
        normalized_symbol = _normalize_symbol(
            symbol
        )

        # Validate all supplied dimensions even though Version 27's
        # recommendation remains symbol-performance based.
        _normalize_session(
            session
        )
        _normalize_market_condition(
            market_condition
        )
        _normalize_direction(
            direction
        )

        with self._lock:
            stats = self.symbol_statistics.get(
                normalized_symbol
            )

            if (
                stats is None
                or stats.total_trades
                < self.MINIMUM_TRADES
            ):
                return LearningRecommendation(
                    reason="Not enough completed trades."
                )

            win_rate = max(
                0.0,
                min(
                    100.0,
                    _safe_float(
                        stats.win_rate,
                        0.0,
                    ),
                ),
            )

        adjustment = self._adjustment(
            win_rate
        )
        bounded_adjustment = max(
            -self.MAX_ADJUSTMENT,
            min(
                self.MAX_ADJUSTMENT,
                adjustment,
            ),
        )

        return LearningRecommendation(
            confidence_adjustment=bounded_adjustment,
            increase_confidence=(
                bounded_adjustment > 0
            ),
            reduce_confidence=(
                bounded_adjustment < 0
            ),
            stronger_confirmation=(
                win_rate < 75.0
            ),
            recommend_wait=(
                win_rate < 45.0
            ),
            reason=(
                f"Historical win rate: "
                f"{win_rate:.2f}%"
            ),
        )


__all__ = [
    "LearningIntelligenceService",
    "LearningRecommendation",
    "LearningStatistics",
    "LearningTrade",
    "MAXIMUM_MARKET_CONDITION_LENGTH",
    "MAXIMUM_SYMBOL_LENGTH",
    "SUPPORTED_DIRECTIONS",
    "SUPPORTED_RESULTS",
    "SUPPORTED_SESSIONS",
]