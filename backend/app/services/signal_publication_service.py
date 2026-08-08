from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Final

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.trading_signal import TradingSignal


DAILY_SIGNAL_LIMIT: Final[int] = 10
PREFERRED_DAILY_SIGNAL_TARGET: Final[int] = 5
DUPLICATE_SIGNAL_COOLDOWN_HOURS: Final[int] = 4

MINIMUM_SIGNAL_CONFIDENCE: Final[Decimal] = Decimal("80")
MINIMUM_SIGNAL_CONFIRMATIONS: Final[int] = 3
MINIMUM_SIGNAL_RISK_REWARD: Final[Decimal] = Decimal("1.5")

MAXIMUM_SIGNAL_CONFIDENCE: Final[Decimal] = Decimal("100")
MAXIMUM_SIGNAL_CONFIRMATIONS: Final[int] = 100
MAXIMUM_SIGNAL_RISK_REWARD: Final[Decimal] = Decimal("100")
MAXIMUM_SYMBOL_LENGTH: Final[int] = 40
MAXIMUM_TIMEFRAME_LENGTH: Final[int] = 20
MAXIMUM_CANDIDATES: Final[int] = 1000

PUBLISHABLE_DIRECTIONS: Final[set[str]] = {
    "BUY",
    "SELL",
}

ACTIVE_SIGNAL_STATUSES: Final[set[str]] = {
    "PENDING",
    "ACTIVE",
}


class SignalPublicationError(Exception):
    """
    Base exception for Version 49 publication control.
    """


class SignalPublicationRejected(
    SignalPublicationError
):
    """
    Raised when a signal does not satisfy publication rules.
    """


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def start_of_utc_day(
    value: datetime | None = None,
) -> datetime:
    current = value or utc_now()

    if current.tzinfo is None:
        current = current.replace(
            tzinfo=timezone.utc
        )
    else:
        current = current.astimezone(
            timezone.utc
        )

    return current.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


def _decimal(
    value: Any,
    default: Decimal = Decimal("0"),
) -> Decimal:
    if value is None:
        return default

    try:
        resolved = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default

    if not resolved.is_finite():
        return default

    return resolved



def _safe_bool(value: Any, default: bool = False) -> bool:
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

        if normalized in {
            "true",
            "1",
            "yes",
            "approved",
            "confirmed",
            "pass",
            "passed",
        }:
            return True

        if normalized in {
            "false",
            "0",
            "no",
            "rejected",
            "unconfirmed",
            "fail",
            "failed",
        }:
            return False

    return default


def _safe_non_negative_int(
    value: Any,
    default: int = 0,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool):
        return default

    try:
        resolved = int(value)
    except (TypeError, ValueError, OverflowError):
        return default

    resolved = max(0, resolved)

    if maximum is not None:
        resolved = min(resolved, maximum)

    return resolved


def _normalize_symbol(symbol: Any) -> str:
    resolved = str(symbol or "").strip().upper()

    if len(resolved) > MAXIMUM_SYMBOL_LENGTH:
        return ""

    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/")

    if any(character not in allowed for character in resolved):
        return ""

    return resolved


def _normalize_timeframe(timeframe: Any) -> str:
    resolved = str(timeframe or "").strip().upper()

    if len(resolved) > MAXIMUM_TIMEFRAME_LENGTH:
        return ""

    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")

    if any(character not in allowed for character in resolved):
        return ""

    return resolved


def _normalize_direction(direction: Any) -> str:
    resolved = str(direction or "").strip().upper()

    aliases = {
        "LONG": "BUY",
        "BULLISH": "BUY",
        "SHORT": "SELL",
        "BEARISH": "SELL",
    }

    return aliases.get(resolved, resolved)

def get_published_signal_count_today(
    db: Session,
    *,
    now: datetime | None = None,
) -> int:
    """
    Count today's published BUY and SELL signals.
    """

    day_start = start_of_utc_day(now)
    day_end = day_start + timedelta(days=1)

    return _safe_non_negative_int(
        db.query(
            func.count(TradingSignal.id)
        )
        .filter(
            TradingSignal.created_at
            >= day_start,
            TradingSignal.created_at
            < day_end,
            TradingSignal.direction.in_(
                PUBLISHABLE_DIRECTIONS
            ),
            TradingSignal.is_trade_allowed.is_(
                True
            ),
        )
        .scalar()
        or 0
    )


def get_remaining_signal_slots(
    db: Session,
    *,
    now: datetime | None = None,
) -> int:
    published = get_published_signal_count_today(
        db,
        now=now,
    )

    return max(
        0,
        DAILY_SIGNAL_LIMIT - published,
    )


def find_duplicate_active_signal(
    db: Session,
    *,
    symbol: str,
    timeframe: str,
    direction: str,
    now: datetime | None = None,
) -> TradingSignal | None:
    """
    Find a matching recent active signal.

    Only one recent active signal is allowed for the same
    symbol, timeframe and direction.
    """

    current = now if isinstance(now, datetime) else utc_now()

    if current.tzinfo is None:
        current = current.replace(
            tzinfo=timezone.utc
        )
    else:
        current = current.astimezone(timezone.utc)

    resolved_symbol = _normalize_symbol(symbol)
    resolved_timeframe = _normalize_timeframe(timeframe)
    resolved_direction = _normalize_direction(direction)

    if (
        not resolved_symbol
        or not resolved_timeframe
        or resolved_direction not in PUBLISHABLE_DIRECTIONS
    ):
        return None

    cooldown_start = current - timedelta(
        hours=DUPLICATE_SIGNAL_COOLDOWN_HOURS
    )

    return (
        db.query(TradingSignal)
        .filter(
            TradingSignal.symbol == resolved_symbol,
            TradingSignal.timeframe == resolved_timeframe,
            TradingSignal.direction == resolved_direction,
            TradingSignal.status.in_(
                ACTIVE_SIGNAL_STATUSES
            ),
            TradingSignal.created_at
            >= cooldown_start,
        )
        .order_by(
            TradingSignal.created_at.desc(),
            TradingSignal.id.desc(),
        )
        .first()
    )


def calculate_signal_quality_score(
    *,
    confidence: Any,
    confirmations_count: int,
    risk_reward_ratio: Any,
    multi_timeframe_agreement: bool = False,
    market_structure_confirmed: bool = False,
    fundamental_conflict: bool = False,
    high_impact_news_risk: bool = False,
) -> Decimal:
    """
    Calculate a deterministic quality score from 0 to 100.

    Confidence remains the strongest factor. Confirmations,
    risk-reward, multi-timeframe agreement and market structure
    improve the score. Fundamental conflict and news risk reduce it.
    """

    resolved_confidence = min(
        MAXIMUM_SIGNAL_CONFIDENCE,
        max(
            Decimal("0"),
            _decimal(confidence),
        ),
    )

    resolved_confirmations = _safe_non_negative_int(
        confirmations_count,
        maximum=MAXIMUM_SIGNAL_CONFIRMATIONS,
    )

    resolved_rr = min(
        MAXIMUM_SIGNAL_RISK_REWARD,
        max(
            Decimal("0"),
            _decimal(risk_reward_ratio),
        ),
    )

    multi_timeframe_agreement = _safe_bool(multi_timeframe_agreement)
    market_structure_confirmed = _safe_bool(market_structure_confirmed)
    fundamental_conflict = _safe_bool(fundamental_conflict)
    high_impact_news_risk = _safe_bool(high_impact_news_risk)

    confidence_score = (
        resolved_confidence
        * Decimal("0.60")
    )

    confirmation_score = min(
        Decimal("15"),
        Decimal(resolved_confirmations)
        * Decimal("3"),
    )

    rr_score = min(
        Decimal("10"),
        resolved_rr
        * Decimal("4"),
    )

    timeframe_score = (
        Decimal("7")
        if multi_timeframe_agreement
        else Decimal("0")
    )

    structure_score = (
        Decimal("8")
        if market_structure_confirmed
        else Decimal("0")
    )

    penalty = Decimal("0")

    if resolved_fundamental_conflict:
        penalty += Decimal("15")

    if resolved_high_impact_news_risk:
        penalty += Decimal("20")

    score = (
        confidence_score
        + confirmation_score
        + rr_score
        + timeframe_score
        + structure_score
        - penalty
    )

    return min(
        Decimal("100"),
        max(
            Decimal("0"),
            score,
        ),
    ).quantize(Decimal("0.01"))


def evaluate_signal_for_publication(
    db: Session,
    *,
    symbol: str,
    timeframe: str,
    direction: str,
    confidence: Any,
    confirmations_count: int,
    risk_reward_ratio: Any,
    multi_timeframe_agreement: bool = False,
    market_structure_confirmed: bool = False,
    fundamental_conflict: bool = False,
    high_impact_news_risk: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """
    Evaluate one setup before public signal storage.

    The signal is publishable only when every mandatory rule
    passes and the daily publication limit has not been reached.
    """

    resolved_symbol = _normalize_symbol(symbol)
    resolved_timeframe = _normalize_timeframe(timeframe)
    resolved_direction = _normalize_direction(direction)

    resolved_confidence = _decimal(confidence)
    resolved_confirmations = _safe_non_negative_int(
        confirmations_count,
        maximum=MAXIMUM_SIGNAL_CONFIRMATIONS,
    )
    resolved_rr = _decimal(risk_reward_ratio)

    resolved_multi_timeframe_agreement = _safe_bool(
        multi_timeframe_agreement
    )
    resolved_market_structure_confirmed = _safe_bool(
        market_structure_confirmed
    )
    resolved_fundamental_conflict = _safe_bool(
        fundamental_conflict
    )
    resolved_high_impact_news_risk = _safe_bool(
        high_impact_news_risk
    )

    rejection_reasons: list[str] = []

    if not resolved_symbol:
        rejection_reasons.append(
            "Symbol is required."
        )

    if not resolved_timeframe:
        rejection_reasons.append(
            "Timeframe is required."
        )

    if (
        resolved_direction
        not in PUBLISHABLE_DIRECTIONS
    ):
        rejection_reasons.append(
            "Only BUY or SELL signals can be published."
        )

    if (
        resolved_confidence < MINIMUM_SIGNAL_CONFIDENCE
        or resolved_confidence > MAXIMUM_SIGNAL_CONFIDENCE
    ):
        rejection_reasons.append(
            "Confidence is below 80%."
        )

    if (
        resolved_confirmations
        < MINIMUM_SIGNAL_CONFIRMATIONS
    ):
        rejection_reasons.append(
            "Fewer than 3 confirmations."
        )

    if (
        resolved_rr < MINIMUM_SIGNAL_RISK_REWARD
        or resolved_rr > MAXIMUM_SIGNAL_RISK_REWARD
    ):
        rejection_reasons.append(
            "Risk-reward is below 1.5."
        )

    if not resolved_multi_timeframe_agreement:
        rejection_reasons.append(
            "Multi-timeframe agreement is missing."
        )

    if not resolved_market_structure_confirmed:
        rejection_reasons.append(
            "Market structure is not confirmed."
        )

    if fundamental_conflict:
        rejection_reasons.append(
            "Fundamental analysis conflicts with the setup."
        )

    if high_impact_news_risk:
        rejection_reasons.append(
            "High-impact news risk is too high."
        )

    published_today = (
        get_published_signal_count_today(
            db,
            now=now,
        )
    )

    if published_today >= DAILY_SIGNAL_LIMIT:
        rejection_reasons.append(
            "Daily high-quality signal limit reached."
        )

    duplicate = None

    if (
        resolved_symbol
        and resolved_timeframe
        and resolved_direction
        in PUBLISHABLE_DIRECTIONS
    ):
        duplicate = find_duplicate_active_signal(
            db,
            symbol=resolved_symbol,
            timeframe=resolved_timeframe,
            direction=resolved_direction,
            now=now,
        )

    if duplicate is not None:
        rejection_reasons.append(
            "Duplicate active signal exists within cooldown."
        )

    quality_score = (
        calculate_signal_quality_score(
            confidence=resolved_confidence,
            confirmations_count=(
                resolved_confirmations
            ),
            risk_reward_ratio=resolved_rr,
            multi_timeframe_agreement=(
                resolved_multi_timeframe_agreement
            ),
            market_structure_confirmed=(
                resolved_market_structure_confirmed
            ),
            fundamental_conflict=(
                resolved_fundamental_conflict
            ),
            high_impact_news_risk=(
                resolved_high_impact_news_risk
            ),
        )
    )

    rejection_reasons = list(dict.fromkeys(rejection_reasons))

    publishable = len(rejection_reasons) == 0

    return {
        "publishable": publishable,
        "quality_score": quality_score,
        "symbol": resolved_symbol,
        "timeframe": resolved_timeframe,
        "direction": resolved_direction,
        "confidence": resolved_confidence,
        "confirmations_count": (
            resolved_confirmations
        ),
        "risk_reward_ratio": resolved_rr,
        "published_today": published_today,
        "daily_signal_limit": (
            DAILY_SIGNAL_LIMIT
        ),
        "preferred_daily_target": (
            PREFERRED_DAILY_SIGNAL_TARGET
        ),
        "remaining_signal_slots": max(
            0,
            DAILY_SIGNAL_LIMIT
            - published_today,
        ),
        "duplicate_signal_uid": (
            duplicate.signal_uid
            if duplicate is not None
            else None
        ),
        "rejection_reasons": (
            rejection_reasons
        ),
    }


def require_signal_publication_approval(
    db: Session,
    **evaluation_fields: Any,
) -> dict[str, Any]:
    """
    Return the evaluation or raise when publication is blocked.
    """

    evaluation = (
        evaluate_signal_for_publication(
            db,
            **evaluation_fields,
        )
    )

    if not isinstance(evaluation, dict):
        raise SignalPublicationError(
            "Publication evaluation returned an invalid response."
        )

    if not _safe_bool(evaluation.get("publishable", False)):
        raw_reasons = evaluation.get("rejection_reasons", [])

        reasons = "; ".join(
            str(reason).strip()
            for reason in (
                raw_reasons if isinstance(raw_reasons, list) else []
            )
            if str(reason).strip()
        )

        raise SignalPublicationRejected(
            reasons
            or "Signal publication was rejected."
        )

    return evaluation


def rank_signal_candidates(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Rank approved candidates from strongest to weakest.

    The best five are preferred. No more than ten should be
    published in one UTC day.
    """

    if not isinstance(candidates, list):
        return []

    ranked: list[dict[str, Any]] = []

    for candidate in candidates[:MAXIMUM_CANDIDATES]:
        if not isinstance(candidate, dict):
            continue

        item = dict(candidate)

        item["quality_score"] = calculate_signal_quality_score(
            confidence=item.get("confidence", 0),
            confirmations_count=_safe_non_negative_int(
                item.get("confirmations_count", 0),
                maximum=MAXIMUM_SIGNAL_CONFIRMATIONS,
            ),
            risk_reward_ratio=item.get("risk_reward_ratio", 0),
            multi_timeframe_agreement=_safe_bool(
                item.get("multi_timeframe_agreement", False)
            ),
            market_structure_confirmed=_safe_bool(
                item.get("market_structure_confirmed", False)
            ),
            fundamental_conflict=_safe_bool(
                item.get("fundamental_conflict", False)
            ),
            high_impact_news_risk=_safe_bool(
                item.get("high_impact_news_risk", False)
            ),
        )

        ranked.append(item)

    ranked.sort(
        key=lambda item: (
            _decimal(item.get("quality_score", 0)),
            _decimal(item.get("confidence", 0)),
            _safe_non_negative_int(
                item.get("confirmations_count", 0),
                maximum=MAXIMUM_SIGNAL_CONFIRMATIONS,
            ),
        ),
        reverse=True,
    )

    return ranked[:DAILY_SIGNAL_LIMIT]


__all__ = [
    "DAILY_SIGNAL_LIMIT",
    "MAXIMUM_CANDIDATES",
    "MAXIMUM_SIGNAL_CONFIDENCE",
    "MAXIMUM_SIGNAL_CONFIRMATIONS",
    "MAXIMUM_SIGNAL_RISK_REWARD",
    "DUPLICATE_SIGNAL_COOLDOWN_HOURS",
    "MINIMUM_SIGNAL_CONFIDENCE",
    "MINIMUM_SIGNAL_CONFIRMATIONS",
    "MINIMUM_SIGNAL_RISK_REWARD",
    "PREFERRED_DAILY_SIGNAL_TARGET",
    "SignalPublicationError",
    "SignalPublicationRejected",
    "calculate_signal_quality_score",
    "evaluate_signal_for_publication",
    "find_duplicate_active_signal",
    "get_published_signal_count_today",
    "get_remaining_signal_slots",
    "rank_signal_candidates",
    "require_signal_publication_approval",
    "start_of_utc_day",
    "utc_now",
]