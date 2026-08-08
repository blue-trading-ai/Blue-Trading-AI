"""
Blue-Trading-AI
Version 24 - Fundamental Analysis Intelligence

This module evaluates macroeconomic and currency fundamentals without
connecting to a broker or executing trades.

Initial Version 24 design:
- Manual and API-ready fundamental data registration
- Currency-specific macroeconomic scoring
- Interest-rate and central-bank bias
- Inflation, GDP, employment and PMI analysis
- Currency strength comparison
- Fundamental directional bias
- Confidence adjustment
- WAIT / NO_TRADE safety decisions
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import math
from threading import RLock
from typing import Any, Dict, Final, Iterable, List, Optional, Tuple


SUPPORTED_CURRENCIES: Tuple[str, ...] = (
    "AUD",
    "CAD",
    "CHF",
    "EUR",
    "GBP",
    "JPY",
    "NZD",
    "USD",
)

SUPPORTED_BIASES: Tuple[str, ...] = (
    "STRONGLY_BEARISH",
    "BEARISH",
    "NEUTRAL",
    "BULLISH",
    "STRONGLY_BULLISH",
)

MINIMUM_FUNDAMENTAL_CONFIDENCE: Final = 60.0
MINIMUM_SIGNAL_CONFIDENCE: Final = 80.0
MINIMUM_CONFIRMATIONS: Final = 3
MAXIMUM_CONFIRMATIONS: Final = 100
MAXIMUM_CONFIDENCE_BOOST: Final = 8.0
MAXIMUM_CONFIDENCE_REDUCTION: Final = -15.0
DEFAULT_DATA_STALE_HOURS: Final = 168
MAXIMUM_BATCH_REGISTRATION: Final = 100
MAXIMUM_SOURCE_LENGTH: Final = 128
MAXIMUM_NOTES_LENGTH: Final = 1000
MAXIMUM_SYMBOL_LENGTH: Final = 32


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return float(default)

    if not math.isfinite(number):
        return float(default)

    return number


def _safe_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default

    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return default

    return min(
        max(number, 0),
        MAXIMUM_CONFIRMATIONS,
    )


def _clamp(value: Any, minimum: float, maximum: float) -> float:
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


def _normalize_currency(currency: str) -> str:
    normalized = str(currency or "").strip().upper()
    if normalized not in SUPPORTED_CURRENCIES:
        raise ValueError(
            f"Unsupported currency '{currency}'. "
            f"Supported currencies: {', '.join(SUPPORTED_CURRENCIES)}"
        )
    return normalized


def _normalize_datetime(value: Optional[datetime]) -> datetime:
    if value is None:
        return _utc_now()

    if not isinstance(
        value,
        datetime,
    ):
        raise ValueError(
            "updated_at must be a datetime value."
        )

    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


def _extract_symbol_currencies(symbol: str) -> Tuple[Optional[str], Optional[str]]:
    normalized = (
        str(symbol or "")
        .strip()
        .upper()
        .replace("/", "")
        .replace("-", "")
        .replace("_", "")
        .replace(" ", "")
    )

    if not normalized:
        return None, None

    if len(normalized) > MAXIMUM_SYMBOL_LENGTH:
        return None, None

    if not all(
        character.isalnum()
        or character == "."
        for character in normalized
    ):
        return None, None

    aliases = {
        "XAUUSD": ("XAU", "USD"),
        "GOLD": ("XAU", "USD"),
        "BTCUSD": ("BTC", "USD"),
        "ETHUSD": ("ETH", "USD"),
    }

    if normalized in aliases:
        return aliases[normalized]

    if len(normalized) >= 6:
        base = normalized[:3]
        quote = normalized[3:6]
        return base, quote

    return None, None


def _score_to_bias(score: float) -> str:
    if score >= 75.0:
        return "STRONGLY_BULLISH"
    if score >= 58.0:
        return "BULLISH"
    if score <= 25.0:
        return "STRONGLY_BEARISH"
    if score <= 42.0:
        return "BEARISH"
    return "NEUTRAL"


def _direction_from_difference(difference: float) -> str:
    if difference >= 12.0:
        return "BUY"
    if difference <= -12.0:
        return "SELL"
    return "WAIT"


@dataclass
class FundamentalData:
    currency: str
    interest_rate: float = 0.0
    interest_rate_trend: float = 0.0
    central_bank_bias: float = 0.0
    inflation_rate: float = 0.0
    inflation_trend: float = 0.0
    gdp_growth: float = 0.0
    gdp_trend: float = 0.0
    unemployment_rate: float = 0.0
    unemployment_trend: float = 0.0
    employment_change: float = 0.0
    pmi: float = 50.0
    retail_sales_growth: float = 0.0
    consumer_confidence: float = 0.0
    trade_balance: float = 0.0
    political_risk: float = 0.0
    recession_risk: float = 0.0
    data_quality: float = 100.0
    source: str = "MANUAL"
    updated_at: datetime = field(default_factory=_utc_now)
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        self.currency = _normalize_currency(self.currency)
        self.interest_rate = _safe_float(self.interest_rate)
        self.interest_rate_trend = _clamp(
            _safe_float(self.interest_rate_trend), -1.0, 1.0
        )
        self.central_bank_bias = _clamp(
            _safe_float(self.central_bank_bias), -1.0, 1.0
        )
        self.inflation_rate = _safe_float(self.inflation_rate)
        self.inflation_trend = _clamp(
            _safe_float(self.inflation_trend), -1.0, 1.0
        )
        self.gdp_growth = _safe_float(self.gdp_growth)
        self.gdp_trend = _clamp(
            _safe_float(self.gdp_trend), -1.0, 1.0
        )
        self.unemployment_rate = max(
            0.0, _safe_float(self.unemployment_rate)
        )
        self.unemployment_trend = _clamp(
            _safe_float(self.unemployment_trend), -1.0, 1.0
        )
        self.employment_change = _safe_float(self.employment_change)
        self.pmi = _clamp(_safe_float(self.pmi, 50.0), 0.0, 100.0)
        self.retail_sales_growth = _safe_float(
            self.retail_sales_growth
        )
        self.consumer_confidence = _safe_float(
            self.consumer_confidence
        )
        self.trade_balance = _safe_float(self.trade_balance)
        self.political_risk = _clamp(
            _safe_float(self.political_risk), 0.0, 100.0
        )
        self.recession_risk = _clamp(
            _safe_float(self.recession_risk), 0.0, 100.0
        )
        self.data_quality = _clamp(
            _safe_float(self.data_quality, 100.0), 0.0, 100.0
        )
        self.updated_at = _normalize_datetime(
            self.updated_at
        )
        self.source = (
            str(
                self.source or "MANUAL"
            )
            .strip()
            .upper()[
                :MAXIMUM_SOURCE_LENGTH
            ]
            or "MANUAL"
        )
        self.notes = (
            str(
                self.notes
            ).strip()[
                :MAXIMUM_NOTES_LENGTH
            ]
            if self.notes is not None
            else None
        )

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["updated_at"] = self.updated_at.isoformat()
        return result


class FundamentalAnalysisIntelligence:
    def __init__(self) -> None:
        self._data: Dict[str, FundamentalData] = {}
        self._lock = RLock()

    def register_data(
        self,
        data: FundamentalData | Dict[str, Any],
    ) -> Dict[str, Any]:
        if isinstance(data, dict):
            data = FundamentalData(**data)

        if not isinstance(data, FundamentalData):
            raise TypeError(
                "data must be FundamentalData or a dictionary"
            )

        with self._lock:
            self._data[data.currency] = data

        return {
            "registered": True,
            "currency": data.currency,
            "data": data.to_dict(),
        }

    def register_many(
        self,
        records: Iterable[FundamentalData | Dict[str, Any]],
    ) -> Dict[str, Any]:
        if isinstance(
            records,
            (
                str,
                bytes,
                dict,
            ),
        ):
            raise ValueError(
                "Fundamental records must be an iterable of records."
            )

        registered: List[str] = []

        for position, record in enumerate(
            records,
            start=1,
        ):
            if position > MAXIMUM_BATCH_REGISTRATION:
                raise ValueError(
                    "Too many fundamental-data records were provided."
                )

            result = self.register_data(
                record
            )
            registered.append(
                result["currency"]
            )

        return {
            "registered": True,
            "count": len(registered),
            "currencies": registered,
        }

    def remove_data(self, currency: str) -> Dict[str, Any]:
        normalized = _normalize_currency(currency)

        with self._lock:
            removed = self._data.pop(normalized, None)

        return {
            "removed": removed is not None,
            "currency": normalized,
        }

    def clear_data(self) -> Dict[str, Any]:
        with self._lock:
            removed_count = len(self._data)
            self._data.clear()

        return {
            "cleared": True,
            "removed_count": removed_count,
        }

    def get_data(
        self,
        currency: str,
    ) -> Optional[Dict[str, Any]]:
        normalized = _normalize_currency(currency)

        with self._lock:
            data = self._data.get(normalized)

        return data.to_dict() if data else None

    def list_data(self) -> List[Dict[str, Any]]:
        with self._lock:
            records = list(self._data.values())

        records.sort(key=lambda item: item.currency)
        return [record.to_dict() for record in records]

    def _data_age_hours(
        self,
        data: FundamentalData,
        current_datetime: datetime,
    ) -> float:
        delta = current_datetime - data.updated_at
        return max(0.0, delta.total_seconds() / 3600.0)

    def _interest_rate_score(
        self,
        data: FundamentalData,
    ) -> Tuple[float, List[str]]:
        reasons: List[str] = []

        normalized_rate = _clamp(
            50.0 + (data.interest_rate * 5.0),
            0.0,
            100.0,
        )
        trend_component = data.interest_rate_trend * 20.0
        central_bank_component = data.central_bank_bias * 25.0

        score = _clamp(
            normalized_rate
            + trend_component
            + central_bank_component,
            0.0,
            100.0,
        )

        if data.central_bank_bias >= 0.35:
            reasons.append("Central bank policy is hawkish.")
        elif data.central_bank_bias <= -0.35:
            reasons.append("Central bank policy is dovish.")
        else:
            reasons.append("Central bank policy is neutral.")

        if data.interest_rate_trend > 0.2:
            reasons.append("Interest-rate trend supports the currency.")
        elif data.interest_rate_trend < -0.2:
            reasons.append("Interest-rate trend weakens the currency.")

        return score, reasons

    def _inflation_score(
        self,
        data: FundamentalData,
    ) -> Tuple[float, List[str]]:
        reasons: List[str] = []

        if 1.5 <= data.inflation_rate <= 3.5:
            base_score = 62.0
            reasons.append("Inflation is within a manageable range.")
        elif 0.0 <= data.inflation_rate < 1.5:
            base_score = 45.0
            reasons.append("Inflation is low and may limit rate support.")
        elif 3.5 < data.inflation_rate <= 6.0:
            base_score = 55.0
            reasons.append(
                "Inflation is elevated and may support tighter policy."
            )
        elif data.inflation_rate > 6.0:
            base_score = 35.0
            reasons.append(
                "Inflation is excessively high and increases instability."
            )
        else:
            base_score = 30.0
            reasons.append("Deflation risk weakens the outlook.")

        score = _clamp(
            base_score + (data.inflation_trend * 10.0),
            0.0,
            100.0,
        )

        return score, reasons

    def _growth_score(
        self,
        data: FundamentalData,
    ) -> Tuple[float, List[str]]:
        reasons: List[str] = []

        gdp_component = _clamp(
            50.0 + (data.gdp_growth * 10.0),
            0.0,
            100.0,
        )
        pmi_component = _clamp(data.pmi, 0.0, 100.0)
        retail_component = _clamp(
            50.0 + (data.retail_sales_growth * 5.0),
            0.0,
            100.0,
        )

        score = _clamp(
            (gdp_component * 0.50)
            + (pmi_component * 0.30)
            + (retail_component * 0.20)
            + (data.gdp_trend * 8.0),
            0.0,
            100.0,
        )

        if data.gdp_growth > 1.5:
            reasons.append("GDP growth supports economic strength.")
        elif data.gdp_growth < 0.0:
            reasons.append("Negative GDP growth increases recession risk.")
        else:
            reasons.append("GDP growth is moderate.")

        if data.pmi >= 52.0:
            reasons.append("PMI indicates economic expansion.")
        elif data.pmi < 48.0:
            reasons.append("PMI indicates economic contraction.")

        return score, reasons

    def _employment_score(
        self,
        data: FundamentalData,
    ) -> Tuple[float, List[str]]:
        reasons: List[str] = []

        unemployment_component = _clamp(
            85.0 - (data.unemployment_rate * 7.0),
            0.0,
            100.0,
        )
        employment_change_component = _clamp(
            50.0 + (data.employment_change / 20.0),
            0.0,
            100.0,
        )
        trend_component = -(data.unemployment_trend * 15.0)

        score = _clamp(
            (unemployment_component * 0.65)
            + (employment_change_component * 0.35)
            + trend_component,
            0.0,
            100.0,
        )

        if data.unemployment_trend < -0.15:
            reasons.append("Falling unemployment supports the currency.")
        elif data.unemployment_trend > 0.15:
            reasons.append("Rising unemployment weakens the outlook.")

        if data.employment_change > 0.0:
            reasons.append("Employment growth is positive.")
        elif data.employment_change < 0.0:
            reasons.append("Employment growth is negative.")

        return score, reasons

    def _sentiment_score(
        self,
        data: FundamentalData,
    ) -> Tuple[float, List[str]]:
        reasons: List[str] = []

        confidence_component = _clamp(
            50.0 + (data.consumer_confidence * 0.5),
            0.0,
            100.0,
        )
        trade_component = _clamp(
            50.0 + (data.trade_balance * 0.2),
            0.0,
            100.0,
        )

        score = _clamp(
            (confidence_component * 0.60)
            + (trade_component * 0.40),
            0.0,
            100.0,
        )

        if data.consumer_confidence > 5.0:
            reasons.append("Consumer confidence is positive.")
        elif data.consumer_confidence < -5.0:
            reasons.append("Consumer confidence is weak.")

        if data.trade_balance > 0.0:
            reasons.append("Trade balance supports the currency.")
        elif data.trade_balance < 0.0:
            reasons.append("Trade deficit pressures the currency.")

        return score, reasons

    def analyze_currency(
        self,
        currency: str,
        current_datetime: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        normalized = _normalize_currency(currency)
        current_datetime = _normalize_datetime(current_datetime)

        with self._lock:
            data = self._data.get(normalized)

        if data is None:
            return {
                "currency": normalized,
                "status": "NO_DATA",
                "approved": False,
                "decision": "WAIT",
                "fundamental_score": 50.0,
                "fundamental_confidence": 0.0,
                "bias": "NEUTRAL",
                "blocking_reasons": [
                    f"No fundamental data registered for {normalized}."
                ],
                "analysis_only": True,
            }

        interest_rate_score, interest_reasons = (
            self._interest_rate_score(data)
        )
        inflation_score, inflation_reasons = (
            self._inflation_score(data)
        )
        growth_score, growth_reasons = self._growth_score(data)
        employment_score, employment_reasons = (
            self._employment_score(data)
        )
        sentiment_score, sentiment_reasons = (
            self._sentiment_score(data)
        )

        risk_penalty = (
            (data.political_risk * 0.12)
            + (data.recession_risk * 0.18)
        )

        fundamental_score = _clamp(
            (interest_rate_score * 0.28)
            + (inflation_score * 0.15)
            + (growth_score * 0.25)
            + (employment_score * 0.20)
            + (sentiment_score * 0.12)
            - risk_penalty,
            0.0,
            100.0,
        )

        age_hours = self._data_age_hours(data, current_datetime)
        freshness_score = _clamp(
            100.0
            - ((age_hours / DEFAULT_DATA_STALE_HOURS) * 100.0),
            0.0,
            100.0,
        )

        fundamental_confidence = _clamp(
            (data.data_quality * 0.70)
            + (freshness_score * 0.30),
            0.0,
            100.0,
        )

        bias = _score_to_bias(fundamental_score)
        approved = (
            fundamental_confidence
            >= MINIMUM_FUNDAMENTAL_CONFIDENCE
        )

        blocking_reasons: List[str] = []

        if data.data_quality < 50.0:
            blocking_reasons.append(
                "Fundamental data quality is too low."
            )

        if age_hours > DEFAULT_DATA_STALE_HOURS:
            blocking_reasons.append(
                "Fundamental data is stale."
            )

        if data.recession_risk >= 80.0:
            blocking_reasons.append(
                "Recession risk is extremely high."
            )

        if data.political_risk >= 85.0:
            blocking_reasons.append(
                "Political risk is extremely high."
            )

        if blocking_reasons:
            approved = False

        decision = (
            "APPROVED"
            if approved
            else "WAIT"
        )

        reasons = (
            interest_reasons
            + inflation_reasons
            + growth_reasons
            + employment_reasons
            + sentiment_reasons
        )

        return {
            "currency": normalized,
            "status": "ANALYZED",
            "approved": approved,
            "decision": decision,
            "fundamental_score": round(
                fundamental_score, 2
            ),
            "fundamental_confidence": round(
                fundamental_confidence, 2
            ),
            "bias": bias,
            "component_scores": {
                "interest_rate_score": round(
                    interest_rate_score, 2
                ),
                "inflation_score": round(
                    inflation_score, 2
                ),
                "growth_score": round(growth_score, 2),
                "employment_score": round(
                    employment_score, 2
                ),
                "sentiment_score": round(
                    sentiment_score, 2
                ),
                "risk_penalty": round(risk_penalty, 2),
                "freshness_score": round(
                    freshness_score, 2
                ),
            },
            "reasons": reasons,
            "blocking_reasons": blocking_reasons,
            "data_age_hours": round(age_hours, 2),
            "data": data.to_dict(),
            "analysis_only": True,
        }

    def compare_currencies(
        self,
        base_currency: str,
        quote_currency: str,
        current_datetime: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        base = _normalize_currency(base_currency)
        quote = _normalize_currency(quote_currency)

        base_analysis = self.analyze_currency(
            base,
            current_datetime=current_datetime,
        )
        quote_analysis = self.analyze_currency(
            quote,
            current_datetime=current_datetime,
        )

        base_score = _safe_float(
            base_analysis.get("fundamental_score"),
            50.0,
        )
        quote_score = _safe_float(
            quote_analysis.get("fundamental_score"),
            50.0,
        )
        score_difference = base_score - quote_score
        direction = _direction_from_difference(score_difference)

        confidence = _clamp(
            abs(score_difference) * 2.0,
            0.0,
            100.0,
        )

        approved = (
            base_analysis.get("approved") is True
            and quote_analysis.get("approved") is True
            and direction in {"BUY", "SELL"}
        )

        blocking_reasons: List[str] = []

        if not base_analysis.get("approved"):
            blocking_reasons.append(
                f"{base} fundamental analysis is not approved."
            )

        if not quote_analysis.get("approved"):
            blocking_reasons.append(
                f"{quote} fundamental analysis is not approved."
            )

        if direction == "WAIT":
            blocking_reasons.append(
                "Fundamental strength difference is insufficient."
            )

        return {
            "base_currency": base,
            "quote_currency": quote,
            "approved": approved,
            "decision": direction if approved else "WAIT",
            "direction": direction,
            "score_difference": round(
                score_difference, 2
            ),
            "comparison_confidence": round(
                confidence, 2
            ),
            "base_analysis": base_analysis,
            "quote_analysis": quote_analysis,
            "blocking_reasons": blocking_reasons,
            "analysis_only": True,
        }

    def analyze_symbol(
        self,
        symbol: str,
        current_datetime: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        normalized_symbol = (
            str(symbol or "")
            .upper()
            .replace("/", "")
            .replace("-", "")
            .replace("_", "")
            .replace(" ", "")
        )

        base, quote = _extract_symbol_currencies(
            normalized_symbol
        )

        if not base or not quote:
            return {
                "symbol": normalized_symbol,
                "approved": False,
                "decision": "WAIT",
                "direction": "WAIT",
                "blocking_reasons": [
                    "Unable to identify base and quote currencies."
                ],
                "analysis_only": True,
            }

        if base == "XAU":
            quote_analysis = self.analyze_currency(
                quote,
                current_datetime=current_datetime,
            )
            quote_score = _safe_float(
                quote_analysis.get("fundamental_score"),
                50.0,
            )
            gold_score = _clamp(
                100.0 - quote_score,
                0.0,
                100.0,
            )
            difference = gold_score - quote_score
            direction = _direction_from_difference(difference)

            approved = (
                quote_analysis.get("approved") is True
                and direction in {"BUY", "SELL"}
            )

            return {
                "symbol": normalized_symbol,
                "asset_type": "GOLD",
                "approved": approved,
                "decision": direction if approved else "WAIT",
                "direction": direction,
                "base_fundamental_score": round(
                    gold_score, 2
                ),
                "quote_fundamental_score": round(
                    quote_score, 2
                ),
                "score_difference": round(
                    difference, 2
                ),
                "quote_analysis": quote_analysis,
                "blocking_reasons": (
                    []
                    if approved
                    else [
                        "Gold fundamental direction is not approved."
                    ]
                ),
                "analysis_only": True,
            }

        if base not in SUPPORTED_CURRENCIES:
            return {
                "symbol": normalized_symbol,
                "approved": False,
                "decision": "WAIT",
                "direction": "WAIT",
                "blocking_reasons": [
                    f"Base asset {base} is not supported by the "
                    "currency fundamental engine."
                ],
                "analysis_only": True,
            }

        if quote not in SUPPORTED_CURRENCIES:
            return {
                "symbol": normalized_symbol,
                "approved": False,
                "decision": "WAIT",
                "direction": "WAIT",
                "blocking_reasons": [
                    f"Quote asset {quote} is not supported by the "
                    "currency fundamental engine."
                ],
                "analysis_only": True,
            }

        comparison = self.compare_currencies(
            base,
            quote,
            current_datetime=current_datetime,
        )
        comparison["symbol"] = normalized_symbol
        comparison["asset_type"] = "FOREX"
        return comparison

    def apply_confidence(
        self,
        confidence: float,
        symbol: str,
        signal_direction: Optional[str] = None,
        confirmations: int = 0,
        current_datetime: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        original_confidence = _clamp(
            confidence,
            0.0,
            100.0,
        )
        confirmation_count = _safe_int(
            confirmations
        )
        normalized_direction = str(
            signal_direction or ""
        ).strip().upper()

        analysis = self.analyze_symbol(
            symbol,
            current_datetime=current_datetime,
        )

        fundamental_direction = str(
            analysis.get("direction", "WAIT")
        ).upper()

        score_difference = abs(
            _safe_float(
                analysis.get("score_difference"),
                0.0,
            )
        )

        adjustment = 0.0
        reasons: List[str] = []
        blocking_reasons = list(
            analysis.get("blocking_reasons") or []
        )

        if analysis.get("approved") is not True:
            adjustment = MAXIMUM_CONFIDENCE_REDUCTION
            reasons.append(
                "Fundamental analysis is not approved."
            )
        elif normalized_direction in {"BUY", "SELL"}:
            if normalized_direction == fundamental_direction:
                adjustment = _clamp(
                    score_difference / 5.0,
                    0.0,
                    MAXIMUM_CONFIDENCE_BOOST,
                )
                reasons.append(
                    "Signal direction aligns with fundamentals."
                )
            elif fundamental_direction in {"BUY", "SELL"}:
                adjustment = _clamp(
                    -(score_difference / 3.0),
                    MAXIMUM_CONFIDENCE_REDUCTION,
                    0.0,
                )
                reasons.append(
                    "Signal direction conflicts with fundamentals."
                )
                blocking_reasons.append(
                    "Fundamental direction mismatch."
                )
            else:
                adjustment = -5.0
                reasons.append(
                    "Fundamental direction is neutral."
                )
        else:
            adjustment = -3.0
            reasons.append(
                "Signal direction was not supplied."
            )

        adjusted_confidence = _clamp(
            original_confidence + adjustment,
            0.0,
            100.0,
        )

        approved = (
            analysis.get("approved") is True
            and adjusted_confidence
            >= MINIMUM_SIGNAL_CONFIDENCE
            and confirmation_count
            >= MINIMUM_CONFIRMATIONS
            and (
                normalized_direction
                == fundamental_direction
            )
        )

        decision = (
            normalized_direction
            if approved
            and normalized_direction in {"BUY", "SELL"}
            else "WAIT"
        )

        if adjusted_confidence < MINIMUM_SIGNAL_CONFIDENCE:
            blocking_reasons.append(
                "Fundamental-adjusted confidence is below 80%."
            )

        if confirmation_count < MINIMUM_CONFIRMATIONS:
            blocking_reasons.append(
                "At least 3 confirmations are required."
            )

        return {
            "symbol": (
                str(
                    symbol or ""
                )
                .strip()
                .upper()
            ),
            "approved": approved,
            "decision": decision,
            "signal_direction": (
                normalized_direction or "UNKNOWN"
            ),
            "fundamental_direction": fundamental_direction,
            "original_confidence": round(
                original_confidence, 2
            ),
            "confidence_adjustment": round(
                adjustment, 2
            ),
            "adjusted_confidence": round(
                adjusted_confidence, 2
            ),
            "confirmations": confirmation_count,
            "minimum_confidence_required": (
                MINIMUM_SIGNAL_CONFIDENCE
            ),
            "minimum_confirmations_required": (
                MINIMUM_CONFIRMATIONS
            ),
            "reasons": reasons,
            "blocking_reasons": list(
                dict.fromkeys(blocking_reasons)
            ),
            "fundamental_analysis": analysis,
            "analysis_only": True,
            "trade_execution_enabled": False,
        }

    def get_configuration(self) -> Dict[str, Any]:
        return {
            "service": "Fundamental Analysis Intelligence",
            "version": "24.0.0",
            "supported_currencies": list(
                SUPPORTED_CURRENCIES
            ),
            "supported_biases": list(SUPPORTED_BIASES),
            "minimum_fundamental_confidence": (
                MINIMUM_FUNDAMENTAL_CONFIDENCE
            ),
            "minimum_signal_confidence": (
                MINIMUM_SIGNAL_CONFIDENCE
            ),
            "minimum_confirmations": MINIMUM_CONFIRMATIONS,
            "maximum_confidence_boost": (
                MAXIMUM_CONFIDENCE_BOOST
            ),
            "maximum_confidence_reduction": (
                MAXIMUM_CONFIDENCE_REDUCTION
            ),
            "default_data_stale_hours": (
                DEFAULT_DATA_STALE_HOURS
            ),
            "manual_data_registration_enabled": True,
            "external_provider_connected": False,
            "analysis_only": True,
            "trade_execution_enabled": False,
        }


fundamental_analysis_intelligence = (
    FundamentalAnalysisIntelligence()
)


def register_fundamental_data(
    data: FundamentalData | Dict[str, Any],
) -> Dict[str, Any]:
    return fundamental_analysis_intelligence.register_data(data)


def register_fundamental_data_many(
    records: Iterable[FundamentalData | Dict[str, Any]],
) -> Dict[str, Any]:
    return fundamental_analysis_intelligence.register_many(records)


def remove_fundamental_data(
    currency: str,
) -> Dict[str, Any]:
    return fundamental_analysis_intelligence.remove_data(currency)


def clear_fundamental_data() -> Dict[str, Any]:
    return fundamental_analysis_intelligence.clear_data()


def get_fundamental_data(
    currency: str,
) -> Optional[Dict[str, Any]]:
    return fundamental_analysis_intelligence.get_data(currency)


def list_fundamental_data() -> List[Dict[str, Any]]:
    return fundamental_analysis_intelligence.list_data()


def analyze_currency_fundamentals(
    currency: str,
    current_datetime: Optional[datetime] = None,
) -> Dict[str, Any]:
    return fundamental_analysis_intelligence.analyze_currency(
        currency,
        current_datetime=current_datetime,
    )


def compare_currency_fundamentals(
    base_currency: str,
    quote_currency: str,
    current_datetime: Optional[datetime] = None,
) -> Dict[str, Any]:
    return fundamental_analysis_intelligence.compare_currencies(
        base_currency,
        quote_currency,
        current_datetime=current_datetime,
    )


def analyze_symbol_fundamentals(
    symbol: str,
    current_datetime: Optional[datetime] = None,
) -> Dict[str, Any]:
    return fundamental_analysis_intelligence.analyze_symbol(
        symbol,
        current_datetime=current_datetime,
    )


def apply_fundamental_confidence(
    confidence: float,
    symbol: str,
    signal_direction: Optional[str] = None,
    confirmations: int = 0,
    current_datetime: Optional[datetime] = None,
) -> Dict[str, Any]:
    return fundamental_analysis_intelligence.apply_confidence(
        confidence=confidence,
        symbol=symbol,
        signal_direction=signal_direction,
        confirmations=confirmations,
        current_datetime=current_datetime,
    )


def get_fundamental_analysis_configuration() -> Dict[str, Any]:
    return fundamental_analysis_intelligence.get_configuration()

__all__ = [
    "DEFAULT_DATA_STALE_HOURS",
    "FundamentalAnalysisIntelligence",
    "FundamentalData",
    "MAXIMUM_BATCH_REGISTRATION",
    "MAXIMUM_CONFIDENCE_BOOST",
    "MAXIMUM_CONFIDENCE_REDUCTION",
    "MAXIMUM_CONFIRMATIONS",
    "MINIMUM_CONFIRMATIONS",
    "MINIMUM_FUNDAMENTAL_CONFIDENCE",
    "MINIMUM_SIGNAL_CONFIDENCE",
    "SUPPORTED_BIASES",
    "SUPPORTED_CURRENCIES",
    "analyze_currency_fundamentals",
    "analyze_symbol_fundamentals",
    "apply_fundamental_confidence",
    "clear_fundamental_data",
    "compare_currency_fundamentals",
    "fundamental_analysis_intelligence",
    "get_fundamental_analysis_configuration",
    "get_fundamental_data",
    "list_fundamental_data",
    "register_fundamental_data",
    "register_fundamental_data_many",
    "remove_fundamental_data",
]