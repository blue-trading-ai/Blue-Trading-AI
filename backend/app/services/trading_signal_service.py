from __future__ import annotations

import secrets
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Final, Iterable

from sqlalchemy.orm import Session

from app.models.trading_signal import (
    TradingSignal,
    SIGNAL_DIRECTION_BUY,
    SIGNAL_DIRECTION_NO_TRADE,
    SIGNAL_DIRECTION_SELL,
    SIGNAL_RESULT_BREAKEVEN,
    SIGNAL_RESULT_LOSS,
    SIGNAL_RESULT_NONE,
    SIGNAL_RESULT_WIN,
    SIGNAL_STATUS_ACTIVE,
    SIGNAL_STATUS_CANCELLED,
    SIGNAL_STATUS_COMPLETED,
    SIGNAL_STATUS_EXPIRED,
    SIGNAL_STATUS_PENDING,
    VALID_SIGNAL_DIRECTIONS,
    VALID_SIGNAL_RESULTS,
    VALID_SIGNAL_STATUSES,
)


MINIMUM_CONFIDENCE: Final[Decimal] = Decimal("80.00")
MINIMUM_CONFIRMATIONS: Final[int] = 3
MINIMUM_RISK_REWARD: Final[Decimal] = Decimal("1.5000")

MAXIMUM_CONFIDENCE: Final[Decimal] = Decimal("100.00")
MAXIMUM_CONFIRMATIONS: Final[int] = 100
MAXIMUM_RISK_REWARD: Final[Decimal] = Decimal("100.0000")
MAXIMUM_LIST_LIMIT: Final[int] = 500
MAXIMUM_LIST_OFFSET: Final[int] = 1_000_000
MAXIMUM_SYMBOL_LENGTH: Final[int] = 40
MAXIMUM_TIMEFRAME_LENGTH: Final[int] = 20
MAXIMUM_SIGNAL_UID_LENGTH: Final[int] = 128
MAXIMUM_SOURCE_LENGTH: Final[int] = 50
MAXIMUM_STRATEGY_VERSION_LENGTH: Final[int] = 50
MAXIMUM_TEXT_LENGTH: Final[int] = 4000


class TradingSignalError(Exception):
    """
    Base exception for persisted trading-signal failures.
    """


class TradingSignalNotFoundError(
    TradingSignalError
):
    pass


class TradingSignalValidationError(
    TradingSignalError
):
    pass


class TradingSignalStateError(
    TradingSignalError
):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _decimal_or_none(
    value: Any,
    *,
    field_name: str,
) -> Decimal | None:
    if value is None or value == "":
        return None

    try:
        resolved = Decimal(
            str(value)
        )
    except (
        InvalidOperation,
        ValueError,
        TypeError,
    ) as exc:
        raise TradingSignalValidationError(
            f"{field_name} must be numeric."
        ) from exc

    if not resolved.is_finite():
        raise TradingSignalValidationError(
            f"{field_name} must be a finite number."
        )

    return resolved


def _safe_non_negative_int(
    value: Any,
    *,
    field_name: str,
    maximum: int | None = None,
) -> int:
    if isinstance(
        value,
        bool,
    ):
        raise TradingSignalValidationError(
            f"{field_name} must be an integer."
        )

    try:
        resolved = int(
            value
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ) as exc:
        raise TradingSignalValidationError(
            f"{field_name} must be an integer."
        ) from exc

    if resolved < 0:
        raise TradingSignalValidationError(
            f"{field_name} cannot be negative."
        )

    if (
        maximum is not None
        and resolved > maximum
    ):
        raise TradingSignalValidationError(
            f"{field_name} cannot exceed {maximum}."
        )

    return resolved


def _normalise_symbol(
    symbol: Any,
) -> str:
    resolved = str(
        symbol or ""
    ).strip().upper()

    if not resolved:
        raise TradingSignalValidationError(
            "Signal symbol cannot be empty."
        )

    if len(
        resolved
    ) > MAXIMUM_SYMBOL_LENGTH:
        raise TradingSignalValidationError(
            "Signal symbol is too long."
        )

    allowed = set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/"
    )

    if any(
        character not in allowed
        for character in resolved
    ):
        raise TradingSignalValidationError(
            "Signal symbol contains unsupported characters."
        )

    return resolved


def _normalise_timeframe(
    timeframe: Any,
) -> str:
    resolved = str(
        timeframe or ""
    ).strip().upper()

    if not resolved:
        raise TradingSignalValidationError(
            "Signal timeframe cannot be empty."
        )

    if len(
        resolved
    ) > MAXIMUM_TIMEFRAME_LENGTH:
        raise TradingSignalValidationError(
            "Signal timeframe is too long."
        )

    allowed = set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    )

    if any(
        character not in allowed
        for character in resolved
    ):
        raise TradingSignalValidationError(
            "Signal timeframe contains unsupported characters."
        )

    return resolved


def _normalise_optional_text(
    value: Any,
    *,
    maximum_length: int,
) -> str | None:
    if value is None:
        return None

    resolved = str(
        value
    ).strip()

    if not resolved:
        return None

    if len(
        resolved
    ) > maximum_length:
        raise TradingSignalValidationError(
            "Text value exceeds the allowed length."
        )

    return resolved


def _normalise_direction(
    direction: str,
) -> str:
    resolved = str(
        direction or ""
    ).strip().upper()

    if resolved not in VALID_SIGNAL_DIRECTIONS:
        raise TradingSignalValidationError(
            "Signal direction must be BUY, SELL, or NO_TRADE."
        )

    return resolved


def _normalise_status(
    status: str,
) -> str:
    resolved = str(
        status or SIGNAL_STATUS_PENDING
    ).strip().upper()

    if resolved not in VALID_SIGNAL_STATUSES:
        raise TradingSignalValidationError(
            "Signal status is invalid."
        )

    return resolved


def _normalise_result(
    result: str,
) -> str:
    resolved = str(
        result or SIGNAL_RESULT_NONE
    ).strip().upper()

    if resolved not in VALID_SIGNAL_RESULTS:
        raise TradingSignalValidationError(
            "Signal result is invalid."
        )

    return resolved


def generate_signal_uid() -> str:
    """
    Generate one unique public signal identifier.
    """

    return (
        "SIG-"
        + secrets.token_urlsafe(24)
        .replace("-", "")
        .replace("_", "")[:40]
        .upper()
    )


def evaluate_trade_eligibility(
    *,
    direction: str,
    confidence: Decimal | float | int | str,
    confirmations_count: int,
    risk_reward_ratio: Decimal | float | int | str | None,
    minimum_confidence: Decimal = MINIMUM_CONFIDENCE,
    minimum_confirmations: int = MINIMUM_CONFIRMATIONS,
    minimum_risk_reward: Decimal = MINIMUM_RISK_REWARD,
) -> tuple[bool, list[str]]:
    """
    Apply the Marketmind.AI signal-quality rules.
    """

    resolved_direction = _normalise_direction(
        direction
    )

    resolved_confidence = _decimal_or_none(
        confidence,
        field_name="confidence",
    )

    resolved_risk_reward = _decimal_or_none(
        risk_reward_ratio,
        field_name="risk_reward_ratio",
    )

    resolved_confirmations = _safe_non_negative_int(
        confirmations_count or 0,
        field_name="confirmations_count",
        maximum=MAXIMUM_CONFIRMATIONS,
    )

    resolved_minimum_confirmations = _safe_non_negative_int(
        minimum_confirmations,
        field_name="minimum_confirmations",
        maximum=MAXIMUM_CONFIRMATIONS,
    )

    if not minimum_confidence.is_finite():
        raise TradingSignalValidationError(
            "minimum_confidence must be finite."
        )

    if not minimum_risk_reward.is_finite():
        raise TradingSignalValidationError(
            "minimum_risk_reward must be finite."
        )

    rejection_reasons: list[str] = []

    if resolved_direction == SIGNAL_DIRECTION_NO_TRADE:
        rejection_reasons.append(
            "Signal direction is NO_TRADE."
        )

    if resolved_confidence is None:
        rejection_reasons.append(
            "Confidence is missing."
        )
    elif resolved_confidence < minimum_confidence:
        rejection_reasons.append(
            "Confidence is below the minimum requirement."
        )

    if resolved_confirmations < (
        resolved_minimum_confirmations
    ):
        rejection_reasons.append(
            "Confirmation count is below the minimum requirement."
        )

    if resolved_risk_reward is None:
        rejection_reasons.append(
            "Risk-reward ratio is missing."
        )
    elif resolved_risk_reward < minimum_risk_reward:
        rejection_reasons.append(
            "Risk-reward ratio is below the minimum requirement."
        )

    return (
        len(rejection_reasons) == 0,
        rejection_reasons,
    )


def create_signal(
    db: Session,
    *,
    symbol: str,
    timeframe: str,
    direction: str,
    confidence: Decimal | float | int | str,
    confirmations_count: int,
    risk_reward_ratio: Decimal | float | int | str | None,
    entry_price: Decimal | float | int | str | None = None,
    stop_loss: Decimal | float | int | str | None = None,
    take_profit_1: Decimal | float | int | str | None = None,
    take_profit_2: Decimal | float | int | str | None = None,
    take_profit_3: Decimal | float | int | str | None = None,
    created_by_user_id: int | None = None,
    strategy_version: str | None = None,
    market_structure: dict[str, Any] | None = None,
    confirmations: list[Any] | dict[str, Any] | None = None,
    analysis_details: dict[str, Any] | None = None,
    reasoning: str | None = None,
    rejection_reason: str | None = None,
    source: str = "MARKETMIND_AI",
    signal_uid: str | None = None,
    generated_at: datetime | None = None,
    commit: bool = True,
) -> TradingSignal:
    """
    Validate and persist one signal.

    Trade eligibility is calculated automatically.
    """

    resolved_symbol = _normalise_symbol(
        symbol
    )

    resolved_timeframe = _normalise_timeframe(
        timeframe
    )

    resolved_direction = _normalise_direction(
        direction
    )

    resolved_confidence = _decimal_or_none(
        confidence,
        field_name="confidence",
    )

    if resolved_confidence is None:
        raise TradingSignalValidationError(
            "Confidence is required."
        )

    if (
        resolved_confidence < Decimal("0")
        or resolved_confidence > MAXIMUM_CONFIDENCE
    ):
        raise TradingSignalValidationError(
            "Confidence must be between 0 and 100."
        )

    resolved_confirmations = _safe_non_negative_int(
        confirmations_count or 0,
        field_name="confirmations_count",
        maximum=MAXIMUM_CONFIRMATIONS,
    )

    resolved_risk_reward = _decimal_or_none(
        risk_reward_ratio,
        field_name="risk_reward_ratio",
    )

    if (
        resolved_risk_reward is not None
        and (
            resolved_risk_reward < Decimal("0")
            or resolved_risk_reward > MAXIMUM_RISK_REWARD
        )
    ):
        raise TradingSignalValidationError(
            "Risk-reward ratio must be between 0 and 100."
        )

    resolved_entry_price = _decimal_or_none(
        entry_price,
        field_name="entry_price",
    )
    resolved_stop_loss = _decimal_or_none(
        stop_loss,
        field_name="stop_loss",
    )
    resolved_take_profit_1 = _decimal_or_none(
        take_profit_1,
        field_name="take_profit_1",
    )
    resolved_take_profit_2 = _decimal_or_none(
        take_profit_2,
        field_name="take_profit_2",
    )
    resolved_take_profit_3 = _decimal_or_none(
        take_profit_3,
        field_name="take_profit_3",
    )

    for field_name, price in (
        ("entry_price", resolved_entry_price),
        ("stop_loss", resolved_stop_loss),
        ("take_profit_1", resolved_take_profit_1),
        ("take_profit_2", resolved_take_profit_2),
        ("take_profit_3", resolved_take_profit_3),
    ):
        if (
            price is not None
            and price < Decimal("0")
        ):
            raise TradingSignalValidationError(
                f"{field_name} cannot be negative."
            )

    is_trade_allowed, reasons = (
        evaluate_trade_eligibility(
            direction=resolved_direction,
            confidence=resolved_confidence,
            confirmations_count=resolved_confirmations,
            risk_reward_ratio=resolved_risk_reward,
        )
    )

    resolved_rejection_reason = (
        _normalise_optional_text(
            rejection_reason,
            maximum_length=MAXIMUM_TEXT_LENGTH,
        )
        or (
            "; ".join(
                reasons
            )
            or None
        )
    )

    resolved_uid = str(
        signal_uid
        or generate_signal_uid()
    ).strip()

    if not resolved_uid:
        raise TradingSignalValidationError(
            "Signal UID cannot be empty."
        )

    if len(
        resolved_uid
    ) > MAXIMUM_SIGNAL_UID_LENGTH:
        raise TradingSignalValidationError(
            "Signal UID is too long."
        )

    resolved_strategy_version = _normalise_optional_text(
        strategy_version,
        maximum_length=MAXIMUM_STRATEGY_VERSION_LENGTH,
    )
    resolved_reasoning = _normalise_optional_text(
        reasoning,
        maximum_length=MAXIMUM_TEXT_LENGTH,
    )
    resolved_source = (
        _normalise_optional_text(
            source or "MARKETMIND_AI",
            maximum_length=MAXIMUM_SOURCE_LENGTH,
        )
        or "MARKETMIND_AI"
    ).upper()

    resolved_generated_at = (
        generated_at
        if isinstance(
            generated_at,
            datetime,
        )
        else None
    )

    if resolved_generated_at is not None:
        if resolved_generated_at.tzinfo is None:
            resolved_generated_at = resolved_generated_at.replace(
                tzinfo=timezone.utc
            )
        else:
            resolved_generated_at = resolved_generated_at.astimezone(
                timezone.utc
            )

    existing = (
        db.query(TradingSignal)
        .filter(
            TradingSignal.signal_uid
            == resolved_uid
        )
        .first()
    )

    if existing is not None:
        raise TradingSignalValidationError(
            "Signal UID already exists."
        )

    record = TradingSignal(
        signal_uid=resolved_uid,
        created_by_user_id=(
            _safe_non_negative_int(
                created_by_user_id,
                field_name="created_by_user_id",
            )
            if created_by_user_id is not None
            else None
        ),
        symbol=resolved_symbol,
        timeframe=resolved_timeframe,
        direction=resolved_direction,
        status=(
            SIGNAL_STATUS_ACTIVE
            if is_trade_allowed
            else SIGNAL_STATUS_PENDING
        ),
        result=SIGNAL_RESULT_NONE,
        entry_price=resolved_entry_price,
        stop_loss=resolved_stop_loss,
        take_profit_1=resolved_take_profit_1,
        take_profit_2=resolved_take_profit_2,
        take_profit_3=resolved_take_profit_3,
        risk_reward_ratio=resolved_risk_reward,
        confidence=resolved_confidence,
        confirmations_count=resolved_confirmations,
        strategy_version=resolved_strategy_version,
        market_structure=market_structure,
        confirmations=confirmations,
        analysis_details=analysis_details,
        reasoning=resolved_reasoning,
        rejection_reason=resolved_rejection_reason,
        source=resolved_source,
        is_trade_allowed=is_trade_allowed,
        minimum_confidence_required=MINIMUM_CONFIDENCE,
        minimum_confirmations_required=MINIMUM_CONFIRMATIONS,
        minimum_risk_reward_required=MINIMUM_RISK_REWARD,
        generated_at=resolved_generated_at or utc_now(),
        activated_at=(
            utc_now()
            if is_trade_allowed
            else None
        ),
    )

    try:
        record.validate_state()
    except ValueError as exc:
        raise TradingSignalValidationError(
            str(exc)
        ) from exc

    db.add(record)

    if commit:
        try:
            db.commit()
            db.refresh(record)
        except Exception:
            db.rollback()
            raise
    else:
        db.flush()

    return record


def get_signal_by_id(
    db: Session,
    *,
    signal_id: int,
) -> TradingSignal | None:
    return (
        db.query(TradingSignal)
        .filter(
            TradingSignal.id
            == _safe_non_negative_int(
                signal_id,
                field_name="signal_id",
            )
        )
        .first()
    )


def get_signal_by_uid(
    db: Session,
    *,
    signal_uid: str,
) -> TradingSignal | None:
    return (
        db.query(TradingSignal)
        .filter(
            TradingSignal.signal_uid
            == str(
                signal_uid or ""
            ).strip()[:MAXIMUM_SIGNAL_UID_LENGTH]
        )
        .first()
    )


def require_signal(
    db: Session,
    *,
    signal_id: int | None = None,
    signal_uid: str | None = None,
) -> TradingSignal:
    if signal_id is not None:
        signal = get_signal_by_id(
            db,
            signal_id=int(signal_id),
        )
    elif signal_uid is not None:
        signal = get_signal_by_uid(
            db,
            signal_uid=signal_uid,
        )
    else:
        raise TradingSignalValidationError(
            "Signal ID or signal UID is required."
        )

    if signal is None:
        raise TradingSignalNotFoundError(
            "Trading signal does not exist."
        )

    return signal


def list_signals(
    db: Session,
    *,
    symbol: str | None = None,
    timeframe: str | None = None,
    direction: str | None = None,
    status: str | None = None,
    result: str | None = None,
    trade_allowed: bool | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[TradingSignal]:
    """
    Return filtered signal history.
    """

    query = db.query(TradingSignal)

    if symbol:
        query = query.filter(
            TradingSignal.symbol
            == _normalise_symbol(
                symbol
            )
        )

    if timeframe:
        query = query.filter(
            TradingSignal.timeframe
            == _normalise_timeframe(
                timeframe
            )
        )

    if direction:
        query = query.filter(
            TradingSignal.direction
            == _normalise_direction(direction)
        )

    if status:
        query = query.filter(
            TradingSignal.status
            == _normalise_status(status)
        )

    if result:
        query = query.filter(
            TradingSignal.result
            == _normalise_result(result)
        )

    if trade_allowed is not None:
        query = query.filter(
            TradingSignal.is_trade_allowed.is_(
                trade_allowed
                if isinstance(
                    trade_allowed,
                    bool,
                )
                else False
            )
        )

    resolved_limit = _safe_non_negative_int(
        limit,
        field_name="limit",
        maximum=MAXIMUM_LIST_LIMIT,
    )

    if resolved_limit < 1:
        resolved_limit = 1

    resolved_offset = _safe_non_negative_int(
        offset,
        field_name="offset",
        maximum=MAXIMUM_LIST_OFFSET,
    )

    return (
        query.order_by(
            TradingSignal.generated_at.desc()
        )
        .offset(resolved_offset)
        .limit(resolved_limit)
        .all()
    )


def activate_signal(
    db: Session,
    *,
    signal_id: int,
    commit: bool = True,
) -> TradingSignal:
    signal = require_signal(
        db,
        signal_id=signal_id,
    )

    if not signal.is_trade_allowed:
        raise TradingSignalStateError(
            "Signal does not meet trade-quality requirements."
        )

    if signal.status in {
        SIGNAL_STATUS_COMPLETED,
        SIGNAL_STATUS_CANCELLED,
        SIGNAL_STATUS_EXPIRED,
    }:
        raise TradingSignalStateError(
            "Finalized signal cannot be activated."
        )

    signal.activate()

    if commit:
        try:
            db.commit()
            db.refresh(signal)
        except Exception:
            db.rollback()
            raise
    else:
        db.flush()

    return signal


def complete_signal(
    db: Session,
    *,
    signal_id: int,
    result: str,
    commit: bool = True,
) -> TradingSignal:
    signal = require_signal(
        db,
        signal_id=signal_id,
    )

    if signal.status in {
        SIGNAL_STATUS_CANCELLED,
        SIGNAL_STATUS_EXPIRED,
    }:
        raise TradingSignalStateError(
            "Cancelled or expired signal cannot be completed."
        )

    try:
        signal.complete(
            result=_normalise_result(result)
        )
    except ValueError as exc:
        raise TradingSignalStateError(
            str(exc)
        ) from exc

    if commit:
        try:
            db.commit()
            db.refresh(signal)
        except Exception:
            db.rollback()
            raise
    else:
        db.flush()

    return signal


def cancel_signal(
    db: Session,
    *,
    signal_id: int,
    commit: bool = True,
) -> TradingSignal:
    signal = require_signal(
        db,
        signal_id=signal_id,
    )

    if signal.status == SIGNAL_STATUS_COMPLETED:
        raise TradingSignalStateError(
            "Completed signal cannot be cancelled."
        )

    signal.cancel()

    if commit:
        try:
            db.commit()
            db.refresh(signal)
        except Exception:
            db.rollback()
            raise
    else:
        db.flush()

    return signal


def expire_signal(
    db: Session,
    *,
    signal_id: int,
    commit: bool = True,
) -> TradingSignal:
    signal = require_signal(
        db,
        signal_id=signal_id,
    )

    if signal.status == SIGNAL_STATUS_COMPLETED:
        raise TradingSignalStateError(
            "Completed signal cannot be expired."
        )

    signal.expire()

    if commit:
        try:
            db.commit()
            db.refresh(signal)
        except Exception:
            db.rollback()
            raise
    else:
        db.flush()

    return signal


def bulk_expire_pending_signals(
    db: Session,
    *,
    before: datetime,
    commit: bool = True,
) -> int:
    """
    Expire pending or active signals generated before a cutoff.
    """

    if not isinstance(
        before,
        datetime,
    ):
        raise TradingSignalValidationError(
            "before must be a datetime."
        )

    cutoff = before

    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(
            tzinfo=timezone.utc
        )

    signals = (
        db.query(TradingSignal)
        .filter(
            TradingSignal.status.in_(
                [
                    SIGNAL_STATUS_PENDING,
                    SIGNAL_STATUS_ACTIVE,
                ]
            ),
            TradingSignal.generated_at < cutoff,
        )
        .all()
    )

    for signal in signals:
        signal.expire()

    if signals:
        if commit:
            try:
                db.commit()
            except Exception:
                db.rollback()
                raise
        else:
            db.flush()

    return len(signals)


def delete_signal(
    db: Session,
    *,
    signal_id: int,
    commit: bool = True,
) -> None:
    """
    Delete one signal record.

    Intended only for controlled testing or owner maintenance.
    """

    signal = require_signal(
        db,
        signal_id=signal_id,
    )

    db.delete(signal)

    if commit:
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
    else:
        db.flush()


def signal_public_payload(
    signal: TradingSignal,
) -> dict[str, object]:
    if not isinstance(
        signal,
        TradingSignal,
    ):
        raise TradingSignalValidationError(
            "Invalid trading signal instance."
        )

    payload = signal.to_public_dict()

    if not isinstance(
        payload,
        dict,
    ):
        raise TradingSignalValidationError(
            "Trading signal public payload is invalid."
        )

    return payload


def signals_public_payload(
    signals: Iterable[TradingSignal],
) -> list[dict[str, object]]:
    return [
        signal_public_payload(signal)
        for signal in signals
    ]


__all__ = [
    "MAXIMUM_CONFIRMATIONS",
    "MAXIMUM_LIST_LIMIT",
    "MAXIMUM_LIST_OFFSET",
    "MAXIMUM_RISK_REWARD",
    "MINIMUM_CONFIDENCE",
    "MINIMUM_CONFIRMATIONS",
    "MINIMUM_RISK_REWARD",
    "TradingSignalError",
    "TradingSignalNotFoundError",
    "TradingSignalStateError",
    "TradingSignalValidationError",
    "activate_signal",
    "bulk_expire_pending_signals",
    "cancel_signal",
    "complete_signal",
    "create_signal",
    "delete_signal",
    "evaluate_trade_eligibility",
    "expire_signal",
    "generate_signal_uid",
    "get_signal_by_id",
    "get_signal_by_uid",
    "list_signals",
    "require_signal",
    "signal_public_payload",
    "signals_public_payload",
    "utc_now",
]