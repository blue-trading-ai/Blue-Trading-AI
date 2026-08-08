"""
Blue-Trading-AI
Version 25 - AI Market Regime Intelligence

Purpose:
- Classify current market conditions before signal approval
- Detect trend, range, breakout, volatility, acceleration and exhaustion
- Detect basic accumulation and distribution behaviour
- Adjust confidence and signal approval based on regime alignment
- Preserve analysis-only safety
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import mean, pstdev
from typing import Any, Dict, Final, Iterable, List, Optional, Sequence, Tuple


SUPPORTED_REGIMES: Tuple[str, ...] = (
    "STRONG_BULL_TREND",
    "BULL_TREND",
    "STRONG_BEAR_TREND",
    "BEAR_TREND",
    "SIDEWAYS_RANGE",
    "BREAKOUT",
    "FAKE_BREAKOUT",
    "HIGH_VOLATILITY",
    "LOW_VOLATILITY",
    "TREND_ACCELERATION",
    "TREND_EXHAUSTION",
    "ACCUMULATION",
    "DISTRIBUTION",
    "UNDEFINED",
)

MINIMUM_CANDLES: Final = 30
MINIMUM_SIGNAL_CONFIDENCE: Final = 80.0
MINIMUM_CONFIRMATIONS: Final = 3
MAXIMUM_CONFIRMATIONS: Final = 100
MAXIMUM_CANDLES: Final = 5000
MAXIMUM_REGIME_CONFIDENCE_BOOST: Final = 8.0
MAXIMUM_REGIME_CONFIDENCE_REDUCTION: Final = -15.0


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
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


def _clamp(
    value: Any,
    minimum: float,
    maximum: float,
) -> float:
    number = _safe_float(
        value,
        default=minimum,
    )

    return max(
        minimum,
        min(
            maximum,
            number,
        ),
    )


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
    }

    resolved = aliases.get(
        normalized,
        normalized or "WAIT",
    )

    if resolved not in {
        "BUY",
        "SELL",
        "WAIT",
    }:
        return "WAIT"

    return resolved


def _extract_series(
    candles: Sequence[Dict[str, Any]],
    key: str,
) -> List[float]:
    values: List[float] = []

    for candle in candles:
        if not isinstance(
            candle,
            dict,
        ):
            continue

        value = candle.get(key)

        if value is None and key == "open":
            value = candle.get("o")
        elif value is None and key == "high":
            value = candle.get("h")
        elif value is None and key == "low":
            value = candle.get("l")
        elif value is None and key == "close":
            value = candle.get("c")
        elif value is None and key == "volume":
            value = candle.get("v")

        values.append(_safe_float(value))

    return values


def _simple_moving_average(
    values: Sequence[float],
    period: int,
) -> float:
    if not values:
        return 0.0

    if isinstance(
        period,
        bool,
    ):
        period = 1

    try:
        normalized_period = int(
            period
        )
    except (TypeError, ValueError, OverflowError):
        normalized_period = 1

    actual_period = min(
        max(
            1,
            normalized_period,
        ),
        len(values),
    )
    return mean(values[-actual_period:])


def _average_true_range(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> float:
    if not highs or not lows or not closes:
        return 0.0

    usable_length = min(
        len(highs),
        len(lows),
        len(closes),
    )

    if usable_length <= 0:
        return 0.0

    ranges: List[float] = []

    for index in range(
        usable_length
    ):
        current_high = highs[index]
        current_low = lows[index]

        if index == 0:
            true_range = current_high - current_low
        else:
            previous_close = closes[index - 1]
            true_range = max(
                current_high - current_low,
                abs(current_high - previous_close),
                abs(current_low - previous_close),
            )

        ranges.append(max(0.0, true_range))

    if isinstance(
        period,
        bool,
    ):
        period = 1

    try:
        normalized_period = int(
            period
        )
    except (TypeError, ValueError, OverflowError):
        normalized_period = 1

    actual_period = min(
        max(
            1,
            normalized_period,
        ),
        len(ranges),
    )
    return mean(ranges[-actual_period:])


def _percentage_change(start: float, end: float) -> float:
    if start == 0.0:
        return 0.0

    return ((end - start) / abs(start)) * 100.0


def _slope(values: Sequence[float], period: int) -> float:
    if len(values) < 2:
        return 0.0

    if isinstance(
        period,
        bool,
    ):
        period = 2

    try:
        normalized_period = int(
            period
        )
    except (TypeError, ValueError, OverflowError):
        normalized_period = 2

    actual_period = min(
        max(
            2,
            normalized_period,
        ),
        len(values),
    )
    selected = values[-actual_period:]
    return _percentage_change(selected[0], selected[-1])


@dataclass
class MarketRegimeResult:
    primary_regime: str
    secondary_regimes: List[str]
    direction: str
    regime_score: float
    confidence: float
    approved: bool
    reasons: List[str]
    blocking_reasons: List[str]
    metrics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_regime": self.primary_regime,
            "secondary_regimes": self.secondary_regimes,
            "direction": self.direction,
            "regime_score": round(self.regime_score, 2),
            "confidence": round(self.confidence, 2),
            "approved": self.approved,
            "reasons": self.reasons,
            "blocking_reasons": self.blocking_reasons,
            "metrics": self.metrics,
            "analysis_only": True,
            "trade_execution_enabled": False,
        }


class MarketRegimeIntelligence:
    def validate_candles(
        self,
        candles: Iterable[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        valid: List[Dict[str, Any]] = []

        for index, candle in enumerate(
            candles or []
        ):
            if index >= MAXIMUM_CANDLES:
                break
            if not isinstance(candle, dict):
                continue

            open_price = _safe_float(
                candle.get("open", candle.get("o"))
            )
            high_price = _safe_float(
                candle.get("high", candle.get("h"))
            )
            low_price = _safe_float(
                candle.get("low", candle.get("l"))
            )
            close_price = _safe_float(
                candle.get("close", candle.get("c"))
            )
            volume = _safe_float(
                candle.get("volume", candle.get("v")),
                0.0,
            )

            if not all(
                math.isfinite(value)
                for value in (
                    open_price,
                    high_price,
                    low_price,
                    close_price,
                    volume,
                )
            ):
                continue

            if min(
                open_price,
                high_price,
                low_price,
                close_price,
            ) <= 0.0:
                continue

            if high_price < low_price:
                continue

            if high_price < max(
                open_price,
                close_price,
            ):
                continue

            if low_price > min(open_price, close_price):
                continue

            valid.append(
                {
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": max(0.0, volume),
                }
            )

        return valid

    def analyze(
        self,
        candles: Iterable[Dict[str, Any]],
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
    ) -> Dict[str, Any]:
        valid_candles = self.validate_candles(candles)

        if len(valid_candles) < MINIMUM_CANDLES:
            return MarketRegimeResult(
                primary_regime="UNDEFINED",
                secondary_regimes=[],
                direction="WAIT",
                regime_score=0.0,
                confidence=0.0,
                approved=False,
                reasons=[],
                blocking_reasons=[
                    (
                        f"At least {MINIMUM_CANDLES} valid candles "
                        "are required."
                    )
                ],
                metrics={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "valid_candles": len(valid_candles),
                },
            ).to_dict()

        opens = _extract_series(valid_candles, "open")
        highs = _extract_series(valid_candles, "high")
        lows = _extract_series(valid_candles, "low")
        closes = _extract_series(valid_candles, "close")
        volumes = _extract_series(valid_candles, "volume")

        current_close = closes[-1]
        previous_close = closes[-2]

        sma_10 = _simple_moving_average(closes, 10)
        sma_20 = _simple_moving_average(closes, 20)
        sma_50 = _simple_moving_average(closes, 50)

        short_slope = _slope(closes, 8)
        medium_slope = _slope(closes, 20)
        long_slope = _slope(closes, 30)

        atr_14 = _average_true_range(highs, lows, closes, 14)
        atr_percentage = (
            (atr_14 / current_close) * 100.0
            if current_close > 0
            else 0.0
        )

        returns = [
            _percentage_change(closes[index - 1], closes[index])
            for index in range(1, len(closes))
        ]

        volatility = pstdev(returns[-20:]) if len(returns) >= 2 else 0.0
        average_volume = mean(volumes[-20:]) if volumes else 0.0
        current_volume = volumes[-1] if volumes else 0.0
        volume_ratio = (
            current_volume / average_volume
            if average_volume > 0
            else 1.0
        )

        recent_high = max(highs[-20:-1])
        recent_low = min(lows[-20:-1])
        range_width = recent_high - recent_low
        range_percentage = (
            (range_width / current_close) * 100.0
            if current_close > 0
            else 0.0
        )

        bullish_structure = (
            current_close > sma_10 > sma_20
            and short_slope > 0
            and medium_slope > 0
        )

        bearish_structure = (
            current_close < sma_10 < sma_20
            and short_slope < 0
            and medium_slope < 0
        )

        strong_bullish_structure = (
            bullish_structure
            and sma_20 > sma_50
            and long_slope > 0.5
        )

        strong_bearish_structure = (
            bearish_structure
            and sma_20 < sma_50
            and long_slope < -0.5
        )

        bullish_breakout = (
            current_close > recent_high
            and current_volume >= average_volume * 1.2
        )

        bearish_breakout = (
            current_close < recent_low
            and current_volume >= average_volume * 1.2
        )

        weak_breakout = (
            (
                current_close > recent_high
                or current_close < recent_low
            )
            and current_volume < average_volume
        )

        sideways = (
            abs(medium_slope) < 0.35
            and range_percentage < max(atr_percentage * 5.0, 3.0)
        )

        high_volatility = (
            volatility >= 1.2
            or atr_percentage >= 1.5
        )

        low_volatility = (
            volatility <= 0.35
            and atr_percentage <= 0.6
        )

        trend_acceleration = (
            abs(short_slope) > abs(medium_slope) * 1.35
            and abs(short_slope) > 0.5
            and volume_ratio >= 1.1
        )

        candle_body = abs(current_close - opens[-1])
        candle_range = max(highs[-1] - lows[-1], 0.0000001)
        body_ratio = candle_body / candle_range

        trend_exhaustion = (
            abs(medium_slope) > 1.0
            and body_ratio < 0.30
            and volume_ratio > 1.4
            and (
                (medium_slope > 0 and current_close < previous_close)
                or (medium_slope < 0 and current_close > previous_close)
            )
        )

        accumulation = (
            sideways
            and low_volatility
            and volume_ratio >= 1.15
            and closes[-1] >= sma_20
        )

        distribution = (
            sideways
            and volume_ratio >= 1.15
            and closes[-1] < sma_20
        )

        primary_regime = "UNDEFINED"
        direction = "WAIT"
        score = 50.0
        reasons: List[str] = []
        secondary: List[str] = []

        if bullish_breakout:
            primary_regime = "BREAKOUT"
            direction = "BUY"
            score = 88.0
            reasons.append(
                "Price closed above the recent range with volume support."
            )
        elif bearish_breakout:
            primary_regime = "BREAKOUT"
            direction = "SELL"
            score = 88.0
            reasons.append(
                "Price closed below the recent range with volume support."
            )
        elif weak_breakout:
            primary_regime = "FAKE_BREAKOUT"
            direction = "WAIT"
            score = 35.0
            reasons.append(
                "Price moved outside the range without volume confirmation."
            )
        elif trend_exhaustion:
            primary_regime = "TREND_EXHAUSTION"
            direction = "WAIT"
            score = 45.0
            reasons.append(
                "The active trend shows possible exhaustion behaviour."
            )
        elif strong_bullish_structure:
            primary_regime = "STRONG_BULL_TREND"
            direction = "BUY"
            score = 90.0
            reasons.append(
                "Price, moving averages and slopes confirm a strong bull trend."
            )
        elif strong_bearish_structure:
            primary_regime = "STRONG_BEAR_TREND"
            direction = "SELL"
            score = 90.0
            reasons.append(
                "Price, moving averages and slopes confirm a strong bear trend."
            )
        elif bullish_structure:
            primary_regime = "BULL_TREND"
            direction = "BUY"
            score = 78.0
            reasons.append(
                "Short- and medium-term structure is bullish."
            )
        elif bearish_structure:
            primary_regime = "BEAR_TREND"
            direction = "SELL"
            score = 78.0
            reasons.append(
                "Short- and medium-term structure is bearish."
            )
        elif accumulation:
            primary_regime = "ACCUMULATION"
            direction = "WAIT"
            score = 68.0
            reasons.append(
                "Compressed price action with supportive volume suggests accumulation."
            )
        elif distribution:
            primary_regime = "DISTRIBUTION"
            direction = "WAIT"
            score = 68.0
            reasons.append(
                "Compressed price action with selling pressure suggests distribution."
            )
        elif sideways:
            primary_regime = "SIDEWAYS_RANGE"
            direction = "WAIT"
            score = 60.0
            reasons.append(
                "Price is moving within a narrow range without clear trend."
            )

        if high_volatility:
            secondary.append("HIGH_VOLATILITY")
            reasons.append("Market volatility is elevated.")

        if low_volatility:
            secondary.append("LOW_VOLATILITY")
            reasons.append("Market volatility is compressed.")

        if trend_acceleration:
            secondary.append("TREND_ACCELERATION")
            reasons.append("Short-term trend momentum is accelerating.")

        if trend_exhaustion and primary_regime != "TREND_EXHAUSTION":
            secondary.append("TREND_EXHAUSTION")

        if accumulation and primary_regime != "ACCUMULATION":
            secondary.append("ACCUMULATION")

        if distribution and primary_regime != "DISTRIBUTION":
            secondary.append("DISTRIBUTION")

        score = _clamp(
            score,
            0.0,
            100.0,
        )

        confidence = _clamp(
            score
            + min(
                abs(
                    medium_slope
                )
                * 4.0,
                8.0,
            )
            + min(
                max(
                    volume_ratio - 1.0,
                    0.0,
                )
                * 10.0,
                7.0,
            ),
            0.0,
            98.0,
        )

        blocking_reasons: List[str] = []

        if primary_regime in {
            "UNDEFINED",
            "FAKE_BREAKOUT",
            "TREND_EXHAUSTION",
        }:
            blocking_reasons.append(
                f"{primary_regime} does not support signal approval."
            )

        if high_volatility and primary_regime not in {
            "BREAKOUT",
            "STRONG_BULL_TREND",
            "STRONG_BEAR_TREND",
        }:
            blocking_reasons.append(
                "High volatility creates an unstable signal environment."
            )

        approved = (
            direction in {"BUY", "SELL"}
            and confidence >= 70.0
            and not blocking_reasons
        )

        return MarketRegimeResult(
            primary_regime=primary_regime,
            secondary_regimes=list(dict.fromkeys(secondary)),
            direction=direction,
            regime_score=score,
            confidence=confidence,
            approved=approved,
            reasons=reasons,
            blocking_reasons=blocking_reasons,
            metrics={
                "symbol": symbol,
                "timeframe": timeframe,
                "valid_candles": len(valid_candles),
                "current_close": round(current_close, 8),
                "sma_10": round(sma_10, 8),
                "sma_20": round(sma_20, 8),
                "sma_50": round(sma_50, 8),
                "short_slope_percent": round(short_slope, 4),
                "medium_slope_percent": round(medium_slope, 4),
                "long_slope_percent": round(long_slope, 4),
                "atr_14": round(atr_14, 8),
                "atr_percentage": round(atr_percentage, 4),
                "return_volatility": round(volatility, 4),
                "recent_high": round(recent_high, 8),
                "recent_low": round(recent_low, 8),
                "range_percentage": round(range_percentage, 4),
                "average_volume": round(average_volume, 4),
                "current_volume": round(current_volume, 4),
                "volume_ratio": round(volume_ratio, 4),
                "body_ratio": round(body_ratio, 4),
            },
        ).to_dict()

    def apply_confidence(
        self,
        confidence: float,
        candles: Iterable[Dict[str, Any]],
        signal_direction: Optional[str],
        confirmations: int,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
    ) -> Dict[str, Any]:
        original_confidence = _clamp(
            _safe_float(confidence),
            0.0,
            100.0,
        )

        normalized_direction = _normalize_direction(signal_direction)

        regime = self.analyze(
            candles=candles,
            symbol=symbol,
            timeframe=timeframe,
        )

        regime_direction = _normalize_direction(
            regime.get("direction")
        )

        adjustment = 0.0
        reasons: List[str] = []
        blocking_reasons = list(
            regime.get("blocking_reasons") or []
        )

        if regime.get("approved") is not True:
            adjustment = MAXIMUM_REGIME_CONFIDENCE_REDUCTION
            reasons.append(
                "Market regime is not approved for signal execution."
            )
        elif normalized_direction == regime_direction:
            adjustment = _clamp(
                (
                    _safe_float(regime.get("confidence"), 0.0)
                    - 70.0
                )
                / 3.0,
                0.0,
                MAXIMUM_REGIME_CONFIDENCE_BOOST,
            )
            reasons.append(
                "Signal direction aligns with the detected market regime."
            )
        elif regime_direction in {"BUY", "SELL"}:
            adjustment = MAXIMUM_REGIME_CONFIDENCE_REDUCTION
            reasons.append(
                "Signal direction conflicts with the detected market regime."
            )
            blocking_reasons.append(
                "Market regime direction mismatch."
            )
        else:
            adjustment = -7.0
            reasons.append(
                "Market regime has no directional approval."
            )

        if "TREND_ACCELERATION" in regime.get(
            "secondary_regimes", []
        ):
            if normalized_direction == regime_direction:
                adjustment = _clamp(
                    adjustment + 2.0,
                    MAXIMUM_REGIME_CONFIDENCE_REDUCTION,
                    MAXIMUM_REGIME_CONFIDENCE_BOOST,
                )
                reasons.append(
                    "Trend acceleration provides additional confirmation."
                )

        if "HIGH_VOLATILITY" in regime.get(
            "secondary_regimes", []
        ):
            adjustment = max(
                MAXIMUM_REGIME_CONFIDENCE_REDUCTION,
                adjustment - 3.0,
            )
            reasons.append(
                "High volatility reduced regime confidence."
            )

        adjusted_confidence = _clamp(
            original_confidence + adjustment,
            0.0,
            100.0,
        )

        confirmation_count = _safe_int(
            confirmations,
            0,
        )

        approved = (
            regime.get("approved") is True
            and normalized_direction == regime_direction
            and adjusted_confidence >= MINIMUM_SIGNAL_CONFIDENCE
            and confirmation_count >= MINIMUM_CONFIRMATIONS
        )

        if adjusted_confidence < MINIMUM_SIGNAL_CONFIDENCE:
            blocking_reasons.append(
                "Regime-adjusted confidence is below 80%."
            )

        if confirmation_count < MINIMUM_CONFIRMATIONS:
            blocking_reasons.append(
                "At least 3 confirmations are required."
            )

        decision = (
            normalized_direction
            if approved
            and normalized_direction in {"BUY", "SELL"}
            else "WAIT"
        )

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "approved": approved,
            "decision": decision,
            "signal_direction": normalized_direction,
            "regime_direction": regime_direction,
            "original_confidence": round(
                original_confidence,
                2,
            ),
            "confidence_adjustment": round(
                adjustment,
                2,
            ),
            "adjusted_confidence": round(
                adjusted_confidence,
                2,
            ),
            "confirmations": confirmation_count,
            "minimum_confidence_required": (
                MINIMUM_SIGNAL_CONFIDENCE
            ),
            "minimum_confirmations_required": (
                MINIMUM_CONFIRMATIONS
            ),
            "reasons": list(
                dict.fromkeys(
                    reasons
                )
            ),
            "blocking_reasons": list(
                dict.fromkeys(blocking_reasons)
            ),
            "market_regime": regime,
            "analysis_only": True,
            "trade_execution_enabled": False,
        }

    def get_configuration(self) -> Dict[str, Any]:
        return {
            "service": "AI Market Regime Intelligence",
            "version": "25.0.0",
            "supported_regimes": list(SUPPORTED_REGIMES),
            "minimum_candles": MINIMUM_CANDLES,
            "minimum_signal_confidence": (
                MINIMUM_SIGNAL_CONFIDENCE
            ),
            "minimum_confirmations": MINIMUM_CONFIRMATIONS,
            "maximum_regime_confidence_boost": (
                MAXIMUM_REGIME_CONFIDENCE_BOOST
            ),
            "maximum_regime_confidence_reduction": (
                MAXIMUM_REGIME_CONFIDENCE_REDUCTION
            ),
            "trend_detection_enabled": True,
            "range_detection_enabled": True,
            "breakout_detection_enabled": True,
            "fake_breakout_detection_enabled": True,
            "volatility_detection_enabled": True,
            "trend_acceleration_detection_enabled": True,
            "trend_exhaustion_detection_enabled": True,
            "accumulation_detection_enabled": True,
            "distribution_detection_enabled": True,
            "analysis_only": True,
            "broker_connection_enabled": False,
            "trade_execution_enabled": False,
        }


market_regime_intelligence = MarketRegimeIntelligence()


def analyze_market_regime(
    candles: Iterable[Dict[str, Any]],
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
) -> Dict[str, Any]:
    return market_regime_intelligence.analyze(
        candles=candles,
        symbol=symbol,
        timeframe=timeframe,
    )


def apply_market_regime_confidence(
    confidence: float,
    candles: Iterable[Dict[str, Any]],
    signal_direction: Optional[str],
    confirmations: int,
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
) -> Dict[str, Any]:
    return market_regime_intelligence.apply_confidence(
        confidence=confidence,
        candles=candles,
        signal_direction=signal_direction,
        confirmations=confirmations,
        symbol=symbol,
        timeframe=timeframe,
    )


def get_market_regime_configuration() -> Dict[str, Any]:
    return market_regime_intelligence.get_configuration()

__all__ = [
    "MAXIMUM_CANDLES",
    "MAXIMUM_CONFIRMATIONS",
    "MAXIMUM_REGIME_CONFIDENCE_BOOST",
    "MAXIMUM_REGIME_CONFIDENCE_REDUCTION",
    "MINIMUM_CANDLES",
    "MINIMUM_CONFIRMATIONS",
    "MINIMUM_SIGNAL_CONFIDENCE",
    "MarketRegimeIntelligence",
    "MarketRegimeResult",
    "SUPPORTED_REGIMES",
    "analyze_market_regime",
    "apply_market_regime_confidence",
    "get_market_regime_configuration",
    "market_regime_intelligence",
]