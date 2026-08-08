"""
Blue-Trading-AI
Version 26 - Symbol Win Rate Intelligence Service

Purpose:
- Track closed-trade performance separately for every symbol.
- Support Forex, metals, crypto, indices, and future instruments.
- Calculate symbol-level win rate and related statistics.
- Produce a small, safety-capped confidence adjustment.
- Remain analysis-only. This module does not connect to brokers or execute trades.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from typing import Any, Final, Iterable, Mapping, Optional, Sequence


SAFETY_VERSION: Final[int] = 26
MINIMUM_CLOSED_TRADES: Final[int] = 20
MAX_POSITIVE_ADJUSTMENT: Final[float] = 3.0
MAX_NEGATIVE_ADJUSTMENT: Final[float] = -2.0

MAXIMUM_SYMBOL_LENGTH: Final[int] = 30
MAXIMUM_RECORDS: Final[int] = 100_000
MAXIMUM_METADATA_KEYS: Final[int] = 100
MAXIMUM_CONFIDENCE_VALUE: Final[float] = 100.0
MAXIMUM_RISK_REWARD_VALUE: Final[float] = 100.0


class TradeOutcome(str, Enum):
    """Supported final outcomes for a closed trade."""

    WIN = "WIN"
    LOSS = "LOSS"
    BREAKEVEN = "BREAKEVEN"


@dataclass(frozen=True)
class SymbolWinRateStats:
    """Calculated statistics for one trading symbol."""

    symbol: str
    total_closed_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    win_rate: float
    decisive_win_rate: float
    average_confidence: float
    average_risk_reward: float
    current_win_streak: int
    current_loss_streak: int
    highest_win_streak: int
    highest_loss_streak: int
    last_trade_time: Optional[str]
    sample_size_sufficient: bool
    confidence_adjustment: float
    safety_version: int = SAFETY_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SymbolWinRateDecision:
    """Result returned when symbol statistics are applied to a signal."""

    symbol: str
    original_confidence: float
    confidence_adjustment: float
    adjusted_confidence: float
    applied: bool
    reason: str
    statistics: SymbolWinRateStats
    safety_version: int = SAFETY_VERSION

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["statistics"] = self.statistics.to_dict()
        return data


@dataclass
class _NormalizedTrade:
    symbol: str
    outcome: TradeOutcome
    confidence: Optional[float]
    risk_reward: Optional[float]
    closed_at: Optional[datetime]


def normalize_symbol(symbol: Any) -> str:
    """
    Convert a symbol into a consistent internal format.

    Examples:
    - "EUR/USD" -> "EURUSD"
    - "xau-usd" -> "XAUUSD"
    - "BTC_USD" -> "BTCUSD"
    """

    if symbol is None:
        return ""

    normalized = str(symbol).strip().upper()

    for character in (
        "/",
        "-",
        "_",
        " ",
        ".",
    ):
        normalized = normalized.replace(
            character,
            "",
        )

    if not normalized:
        return ""

    if len(normalized) > MAXIMUM_SYMBOL_LENGTH:
        return ""

    if not normalized.isalnum():
        return ""

    return normalized


def normalize_outcome(value: Any) -> Optional[TradeOutcome]:
    """Convert common trade-result labels into TradeOutcome values."""

    if value is None:
        return None

    normalized = str(value).strip().upper().replace(" ", "_").replace("-", "_")

    winning_values = {
        "WIN",
        "WON",
        "PROFIT",
        "PROFITABLE",
        "TP",
        "TP1",
        "TP2",
        "TAKE_PROFIT",
        "TAKEPROFIT",
        "TARGET_HIT",
    }
    losing_values = {
        "LOSS",
        "LOST",
        "SL",
        "STOP_LOSS",
        "STOPLOSS",
        "STOPPED_OUT",
    }
    breakeven_values = {
        "BREAKEVEN",
        "BREAK_EVEN",
        "BE",
        "B/E",
        "FLAT",
        "NO_PROFIT_NO_LOSS",
    }

    if normalized in winning_values:
        return TradeOutcome.WIN
    if normalized in losing_values:
        return TradeOutcome.LOSS
    if normalized in breakeven_values:
        return TradeOutcome.BREAKEVEN

    return None


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if result != result:
        return None

    if result in {
        float("inf"),
        float("-inf"),
    }:
        return None

    return result


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(
                text
            )
        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _get_field(record: Any, names: Sequence[str]) -> Any:
    """Read the first available field from a mapping or object."""

    if isinstance(record, Mapping):
        for name in names:
            if name in record:
                return record[name]
        return None

    for name in names:
        if hasattr(record, name):
            return getattr(record, name)
    return None


def _normalize_trade(record: Any) -> Optional[_NormalizedTrade]:
    symbol = normalize_symbol(
        _get_field(
            record,
            (
                "symbol",
                "pair",
                "instrument",
                "ticker",
                "market_symbol",
            ),
        )
    )
    if not symbol:
        return None

    outcome = normalize_outcome(
        _get_field(
            record,
            (
                "outcome",
                "result",
                "status",
                "trade_result",
                "final_result",
                "close_reason",
            ),
        )
    )
    if outcome is None:
        return None

    confidence = _safe_float(
        _get_field(
            record,
            (
                "confidence",
                "confidence_score",
                "signal_confidence",
                "final_confidence",
            ),
        )
    )

    if confidence is not None:
        confidence = max(
            0.0,
            min(
                MAXIMUM_CONFIDENCE_VALUE,
                confidence,
            ),
        )

    risk_reward = _safe_float(
        _get_field(
            record,
            (
                "risk_reward",
                "risk_reward_ratio",
                "rr",
                "rr_ratio",
            ),
        )
    )

    if risk_reward is not None:
        risk_reward = max(
            0.0,
            min(
                MAXIMUM_RISK_REWARD_VALUE,
                risk_reward,
            ),
        )

    closed_at = _parse_datetime(
        _get_field(
            record,
            (
                "closed_at",
                "close_time",
                "completed_at",
                "updated_at",
                "timestamp",
                "created_at",
            ),
        )
    )

    return _NormalizedTrade(
        symbol=symbol,
        outcome=outcome,
        confidence=confidence,
        risk_reward=risk_reward,
        closed_at=closed_at,
    )


def calculate_confidence_adjustment(
    win_rate: float,
    total_closed_trades: int,
    *,
    minimum_closed_trades: int = MINIMUM_CLOSED_TRADES,
) -> float:
    """
    Return a conservative confidence adjustment.

    Rules:
    - Fewer than 20 closed trades: 0
    - 85% and above: +3
    - 75% to 84.99%: +2
    - 65% to 74.99%: +1
    - 45% to 64.99%: 0
    - Below 45%: -2
    """

    try:
        resolved_total = max(
            0,
            int(total_closed_trades),
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        resolved_total = 0

    try:
        resolved_minimum = max(
            1,
            int(minimum_closed_trades),
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        resolved_minimum = MINIMUM_CLOSED_TRADES

    if resolved_total < resolved_minimum:
        return 0.0

    resolved_rate = _safe_float(
        win_rate
    )

    if resolved_rate is None:
        resolved_rate = 0.0

    rate = max(
        0.0,
        min(
            100.0,
            resolved_rate,
        ),
    )

    if rate >= 85.0:
        return MAX_POSITIVE_ADJUSTMENT
    if rate >= 75.0:
        return 2.0
    if rate >= 65.0:
        return 1.0
    if rate >= 45.0:
        return 0.0
    return MAX_NEGATIVE_ADJUSTMENT


def _calculate_streaks(
    trades: Sequence[_NormalizedTrade],
) -> tuple[int, int, int, int]:
    """
    Return:
    current_win_streak,
    current_loss_streak,
    highest_win_streak,
    highest_loss_streak.
    """

    ordered = sorted(
        trades,
        key=lambda trade: trade.closed_at or datetime.min.replace(tzinfo=timezone.utc),
    )

    current_win = 0
    current_loss = 0
    highest_win = 0
    highest_loss = 0

    for trade in ordered:
        if trade.outcome == TradeOutcome.WIN:
            current_win += 1
            current_loss = 0
            highest_win = max(highest_win, current_win)
        elif trade.outcome == TradeOutcome.LOSS:
            current_loss += 1
            current_win = 0
            highest_loss = max(highest_loss, current_loss)
        else:
            current_win = 0
            current_loss = 0

    return current_win, current_loss, highest_win, highest_loss


def calculate_symbol_statistics(
    symbol: str,
    trade_records: Iterable[Any],
    *,
    minimum_closed_trades: int = MINIMUM_CLOSED_TRADES,
) -> SymbolWinRateStats:
    """Calculate complete closed-trade statistics for one symbol."""

    normalized_symbol = normalize_symbol(
        symbol
    )

    if not normalized_symbol:
        normalized_symbol = ""

    matching_trades: list[
        _NormalizedTrade
    ] = []

    try:
        iterator = iter(
            trade_records
        )
    except TypeError:
        iterator = iter(
            ()
        )

    for index, record in enumerate(
        iterator
    ):
        if index >= MAXIMUM_RECORDS:
            break
        normalized_trade = _normalize_trade(record)
        if normalized_trade is None:
            continue
        if normalized_trade.symbol == normalized_symbol:
            matching_trades.append(normalized_trade)

    wins = sum(1 for trade in matching_trades if trade.outcome == TradeOutcome.WIN)
    losses = sum(1 for trade in matching_trades if trade.outcome == TradeOutcome.LOSS)
    breakevens = sum(
        1 for trade in matching_trades if trade.outcome == TradeOutcome.BREAKEVEN
    )
    total_closed = len(matching_trades)
    decisive_trades = wins + losses

    win_rate = round((wins / total_closed) * 100.0, 2) if total_closed else 0.0
    decisive_win_rate = (
        round((wins / decisive_trades) * 100.0, 2) if decisive_trades else 0.0
    )

    confidence_values = [
        trade.confidence
        for trade in matching_trades
        if trade.confidence is not None
    ]
    rr_values = [
        trade.risk_reward
        for trade in matching_trades
        if trade.risk_reward is not None
    ]

    average_confidence = (
        round(sum(confidence_values) / len(confidence_values), 2)
        if confidence_values
        else 0.0
    )
    average_risk_reward = (
        round(sum(rr_values) / len(rr_values), 2) if rr_values else 0.0
    )

    current_win, current_loss, highest_win, highest_loss = _calculate_streaks(
        matching_trades
    )

    closed_times = [
        trade.closed_at for trade in matching_trades if trade.closed_at is not None
    ]
    latest_time = max(closed_times).isoformat() if closed_times else None

    try:
        resolved_minimum_closed_trades = max(
            1,
            int(
                minimum_closed_trades
            ),
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        resolved_minimum_closed_trades = (
            MINIMUM_CLOSED_TRADES
        )

    sample_size_sufficient = (
        total_closed
        >= resolved_minimum_closed_trades
    )
    adjustment = calculate_confidence_adjustment(
        win_rate=win_rate,
        total_closed_trades=total_closed,
        minimum_closed_trades=resolved_minimum_closed_trades,
    )

    return SymbolWinRateStats(
        symbol=normalized_symbol,
        total_closed_trades=total_closed,
        winning_trades=wins,
        losing_trades=losses,
        breakeven_trades=breakevens,
        win_rate=win_rate,
        decisive_win_rate=decisive_win_rate,
        average_confidence=average_confidence,
        average_risk_reward=average_risk_reward,
        current_win_streak=current_win,
        current_loss_streak=current_loss,
        highest_win_streak=highest_win,
        highest_loss_streak=highest_loss,
        last_trade_time=latest_time,
        sample_size_sufficient=sample_size_sufficient,
        confidence_adjustment=adjustment,
    )


def calculate_all_symbol_statistics(
    trade_records: Iterable[Any],
    *,
    minimum_closed_trades: int = MINIMUM_CLOSED_TRADES,
) -> dict[str, SymbolWinRateStats]:
    """Calculate statistics for every symbol found in the supplied trade history."""

    try:
        iterator = iter(
            trade_records
        )
    except TypeError:
        iterator = iter(
            ()
        )

    records: list[Any] = []

    for index, record in enumerate(
        iterator
    ):
        if index >= MAXIMUM_RECORDS:
            break
        records.append(
            record
        )

    symbols: set[str] = set()

    for record in records:
        normalized_trade = _normalize_trade(record)
        if normalized_trade is not None:
            symbols.add(normalized_trade.symbol)

    return {
        symbol: calculate_symbol_statistics(
            symbol,
            records,
            minimum_closed_trades=minimum_closed_trades,
        )
        for symbol in sorted(symbols)
    }


def apply_symbol_winrate_confidence(
    *,
    symbol: str,
    original_confidence: float,
    trade_records: Iterable[Any],
    minimum_closed_trades: int = MINIMUM_CLOSED_TRADES,
    minimum_confidence: float = 0.0,
    maximum_confidence: float = 100.0,
) -> SymbolWinRateDecision:
    """Apply the safe symbol-level adjustment to a signal confidence score."""

    stats = calculate_symbol_statistics(
        symbol=symbol,
        trade_records=trade_records,
        minimum_closed_trades=minimum_closed_trades,
    )

    base_confidence = _safe_float(original_confidence)
    if base_confidence is None:
        base_confidence = 0.0

    lower_bound = _safe_float(
        minimum_confidence
    )
    upper_bound = _safe_float(
        maximum_confidence
    )

    if lower_bound is None:
        lower_bound = 0.0

    if upper_bound is None:
        upper_bound = 100.0

    lower_bound = max(
        0.0,
        min(
            100.0,
            lower_bound,
        ),
    )
    upper_bound = max(
        0.0,
        min(
            100.0,
            upper_bound,
        ),
    )

    if lower_bound > upper_bound:
        lower_bound, upper_bound = (
            upper_bound,
            lower_bound,
        )

    applied = stats.sample_size_sufficient and stats.confidence_adjustment != 0.0
    adjusted = base_confidence + stats.confidence_adjustment
    adjusted = max(lower_bound, min(upper_bound, adjusted))
    adjusted = round(adjusted, 2)

    if not stats.sample_size_sufficient:
        reason = (
            f"No symbol adjustment applied. {stats.symbol} has "
            f"{stats.total_closed_trades} closed trades; "
            f"{minimum_closed_trades} are required."
        )
    elif stats.confidence_adjustment > 0:
        reason = (
            f"{stats.symbol} historical win rate is {stats.win_rate}%. "
            f"Confidence increased by {stats.confidence_adjustment} points."
        )
    elif stats.confidence_adjustment < 0:
        reason = (
            f"{stats.symbol} historical win rate is {stats.win_rate}%. "
            f"Confidence reduced by {abs(stats.confidence_adjustment)} points."
        )
    else:
        reason = (
            f"{stats.symbol} historical win rate is {stats.win_rate}%. "
            "No confidence adjustment is required."
        )

    return SymbolWinRateDecision(
        symbol=stats.symbol,
        original_confidence=round(base_confidence, 2),
        confidence_adjustment=stats.confidence_adjustment,
        adjusted_confidence=adjusted,
        applied=applied,
        reason=reason,
        statistics=stats,
    )


class SymbolWinRateIntelligence:
    """
    Thread-safe in-memory helper.

    Existing database or trade-history records can still be passed directly to
    calculate_symbol_statistics(). This store is useful when the application
    wants to register closed trades during runtime.
    """

    def __init__(
        self,
        *,
        minimum_closed_trades: int = MINIMUM_CLOSED_TRADES,
    ) -> None:
        try:
            resolved_minimum = max(
                1,
                int(
                    minimum_closed_trades
                ),
            )
        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            resolved_minimum = (
                MINIMUM_CLOSED_TRADES
            )

        self.minimum_closed_trades = (
            resolved_minimum
        )
        self._records: list[
            dict[str, Any]
        ] = []
        self._lock = RLock()

    def register_closed_trade(
        self,
        *,
        symbol: str,
        outcome: TradeOutcome | str,
        confidence: Optional[float] = None,
        risk_reward: Optional[float] = None,
        closed_at: Optional[datetime | str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> bool:
        normalized_symbol = normalize_symbol(symbol)
        normalized_outcome = normalize_outcome(outcome)

        if not normalized_symbol or normalized_outcome is None:
            return False

        parsed_closed_at = _parse_datetime(closed_at) or datetime.now(timezone.utc)

        record: dict[str, Any] = {
            "symbol": normalized_symbol,
            "outcome": normalized_outcome.value,
            "confidence": _safe_float(confidence),
            "risk_reward": _safe_float(risk_reward),
            "closed_at": parsed_closed_at.isoformat(),
        }

        if isinstance(
            metadata,
            Mapping,
        ):
            metadata_items = list(
                metadata.items()
            )[:MAXIMUM_METADATA_KEYS]

            record[
                "metadata"
            ] = {
                str(key)[:100]: value
                for key, value in metadata_items
            }

        with self._lock:
            self._records.append(
                record
            )

            if (
                len(
                    self._records
                )
                > MAXIMUM_RECORDS
            ):
                overflow = (
                    len(
                        self._records
                    )
                    - MAXIMUM_RECORDS
                )

                del self._records[
                    :overflow
                ]

        return True

    def replace_records(self, trade_records: Iterable[Any]) -> int:
        normalized_records: list[
            dict[str, Any]
        ] = []

        try:
            iterator = iter(
                trade_records
            )
        except TypeError:
            iterator = iter(
                ()
            )

        for index, record in enumerate(
            iterator
        ):
            if index >= MAXIMUM_RECORDS:
                break
            trade = _normalize_trade(record)
            if trade is None:
                continue
            normalized_records.append(
                {
                    "symbol": trade.symbol,
                    "outcome": trade.outcome.value,
                    "confidence": trade.confidence,
                    "risk_reward": trade.risk_reward,
                    "closed_at": (
                        trade.closed_at.isoformat() if trade.closed_at else None
                    ),
                }
            )

        with self._lock:
            self._records = normalized_records

        return len(normalized_records)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()

    def get_records(self) -> list[dict[str, Any]]:
        with self._lock:
            records = list(
                self._records
            )

        result: list[
            dict[str, Any]
        ] = []

        for record in records:
            copied = dict(
                record
            )

            if isinstance(
                copied.get(
                    "metadata"
                ),
                dict,
            ):
                copied[
                    "metadata"
                ] = dict(
                    copied[
                        "metadata"
                    ]
                )

            result.append(
                copied
            )

        return result

    def get_symbol_statistics(self, symbol: str) -> SymbolWinRateStats:
        records = self.get_records()

        return calculate_symbol_statistics(
            symbol=symbol,
            trade_records=records,
            minimum_closed_trades=self.minimum_closed_trades,
        )

    def get_all_statistics(self) -> dict[str, SymbolWinRateStats]:
        records = self.get_records()

        return calculate_all_symbol_statistics(
            records,
            minimum_closed_trades=self.minimum_closed_trades,
        )

    def apply_confidence(
        self,
        *,
        symbol: str,
        original_confidence: float,
        minimum_confidence: float = 0.0,
        maximum_confidence: float = 100.0,
    ) -> SymbolWinRateDecision:
        records = self.get_records()

        return apply_symbol_winrate_confidence(
            symbol=symbol,
            original_confidence=original_confidence,
            trade_records=records,
            minimum_closed_trades=self.minimum_closed_trades,
            minimum_confidence=minimum_confidence,
            maximum_confidence=maximum_confidence,
        )


symbol_winrate_intelligence = SymbolWinRateIntelligence()


def get_symbol_winrate_configuration() -> dict[str, Any]:
    """Return public Version 26 safety configuration."""

    return {
        "version": "26.0.0",
        "safety_version": SAFETY_VERSION,
        "analysis_only": True,
        "broker_connection": False,
        "automatic_trade_execution": False,
        "minimum_closed_trades": MINIMUM_CLOSED_TRADES,
        "maximum_positive_adjustment": MAX_POSITIVE_ADJUSTMENT,
        "maximum_negative_adjustment": MAX_NEGATIVE_ADJUSTMENT,
        "supported_markets": [
            "FOREX",
            "METALS",
            "CRYPTO",
            "INDICES",
            "FUTURE_SYMBOLS",
        ],
        "supported_examples": [
            "EURUSD",
            "GBPUSD",
            "USDJPY",
            "XAUUSD",
            "XAGUSD",
            "BTCUSD",
            "ETHUSD",
            "NAS100",
            "US30",
        ],
    }

__all__ = [
    "MAXIMUM_RECORDS",
    "MAX_NEGATIVE_ADJUSTMENT",
    "MAX_POSITIVE_ADJUSTMENT",
    "MINIMUM_CLOSED_TRADES",
    "SAFETY_VERSION",
    "SymbolWinRateDecision",
    "SymbolWinRateIntelligence",
    "SymbolWinRateStats",
    "TradeOutcome",
    "apply_symbol_winrate_confidence",
    "calculate_all_symbol_statistics",
    "calculate_confidence_adjustment",
    "calculate_symbol_statistics",
    "get_symbol_winrate_configuration",
    "normalize_outcome",
    "normalize_symbol",
    "symbol_winrate_intelligence",
]