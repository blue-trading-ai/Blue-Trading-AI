from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Final

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database.connection import Base


SIGNAL_STATUS_PENDING: Final[str] = "PENDING"
SIGNAL_STATUS_ACTIVE: Final[str] = "ACTIVE"
SIGNAL_STATUS_COMPLETED: Final[str] = "COMPLETED"
SIGNAL_STATUS_CANCELLED: Final[str] = "CANCELLED"
SIGNAL_STATUS_EXPIRED: Final[str] = "EXPIRED"

SIGNAL_RESULT_WIN: Final[str] = "WIN"
SIGNAL_RESULT_LOSS: Final[str] = "LOSS"
SIGNAL_RESULT_BREAKEVEN: Final[str] = "BREAKEVEN"
SIGNAL_RESULT_NONE: Final[str] = "NONE"

SIGNAL_DIRECTION_BUY: Final[str] = "BUY"
SIGNAL_DIRECTION_SELL: Final[str] = "SELL"
SIGNAL_DIRECTION_NO_TRADE: Final[str] = "NO_TRADE"

MAXIMUM_SYMBOL_LENGTH: Final[int] = 40
MAXIMUM_TIMEFRAME_LENGTH: Final[int] = 20
MAXIMUM_SIGNAL_UID_LENGTH: Final[int] = 64
MAXIMUM_DIRECTION_LENGTH: Final[int] = 20
MAXIMUM_STATUS_LENGTH: Final[int] = 20
MAXIMUM_RESULT_LENGTH: Final[int] = 20
MAXIMUM_STRATEGY_VERSION_LENGTH: Final[int] = 50
MAXIMUM_SOURCE_LENGTH: Final[int] = 50
MAXIMUM_CONFIRMATIONS: Final[int] = 100
MAXIMUM_CONFIDENCE: Final[Decimal] = Decimal("100.00")
MAXIMUM_RISK_REWARD: Final[Decimal] = Decimal("100.0000")

VALID_SIGNAL_STATUSES: Final[set[str]] = {
    SIGNAL_STATUS_PENDING,
    SIGNAL_STATUS_ACTIVE,
    SIGNAL_STATUS_COMPLETED,
    SIGNAL_STATUS_CANCELLED,
    SIGNAL_STATUS_EXPIRED,
}

VALID_SIGNAL_RESULTS: Final[set[str]] = {
    SIGNAL_RESULT_WIN,
    SIGNAL_RESULT_LOSS,
    SIGNAL_RESULT_BREAKEVEN,
    SIGNAL_RESULT_NONE,
}

VALID_SIGNAL_DIRECTIONS: Final[set[str]] = {
    SIGNAL_DIRECTION_BUY,
    SIGNAL_DIRECTION_SELL,
    SIGNAL_DIRECTION_NO_TRADE,
}


def _positive_int_or_none(
    value: Any,
    *,
    field_name: str,
) -> int | None:
    """Resolve one optional positive integer without accepting booleans."""

    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):
        raise ValueError(
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
        raise ValueError(
            f"{field_name} must be an integer."
        ) from exc

    if resolved < 1:
        raise ValueError(
            f"{field_name} must be positive."
        )

    return resolved


def _bounded_int(
    value: Any,
    *,
    field_name: str,
    minimum: int,
    maximum: int,
) -> int:
    """Resolve one bounded integer without accepting booleans."""

    if isinstance(
        value,
        bool,
    ):
        raise ValueError(
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
        raise ValueError(
            f"{field_name} must be an integer."
        ) from exc

    if not (
        minimum
        <= resolved
        <= maximum
    ):
        raise ValueError(
            f"{field_name} is outside the supported range."
        )

    return resolved


def _strict_bool(
    value: Any,
    *,
    field_name: str,
    default: bool,
) -> bool:
    """Resolve one boolean without arbitrary truthiness conversion."""

    if value is None:
        return default

    if isinstance(
        value,
        bool,
    ):
        return value

    if isinstance(
        value,
        int,
    ) and value in {
        0,
        1,
    }:
        return bool(
            value
        )

    if isinstance(
        value,
        str,
    ):
        normalized = (
            value.strip()
            .lower()
        )

        if normalized in {
            "true",
            "1",
            "yes",
            "on",
        }:
            return True

        if normalized in {
            "false",
            "0",
            "no",
            "off",
        }:
            return False

    raise ValueError(
        f"{field_name} must be a boolean."
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _finite_decimal(
    value: object,
    *,
    field_name: str,
    allow_none: bool = True,
) -> Decimal | None:
    if value is None:
        if allow_none:
            return None
        raise ValueError(
            f"{field_name} is required."
        )

    try:
        resolved = Decimal(
            str(value)
        )
    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            f"{field_name} must be numeric."
        ) from exc

    if not resolved.is_finite():
        raise ValueError(
            f"{field_name} must be finite."
        )

    return resolved


def _ensure_utc(
    value: datetime | None,
) -> datetime | None:
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


class TradingSignal(Base):
    """
    Persisted trading-analysis signal.

    Security and integrity rules:
    - Signals are analysis records only.
    - No broker execution fields exist.
    - Confidence and confirmation counts are stored for audit.
    - Entry, stop loss and targets are immutable history inputs.
    - Completion result is stored separately from generation data.
    """

    __tablename__ = "trading_signals"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    signal_uid = Column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )

    created_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    symbol = Column(
        String(40),
        nullable=False,
        index=True,
    )

    timeframe = Column(
        String(20),
        nullable=False,
        index=True,
    )

    direction = Column(
        String(20),
        nullable=False,
        index=True,
    )

    status = Column(
        String(20),
        nullable=False,
        default=SIGNAL_STATUS_PENDING,
        index=True,
    )

    result = Column(
        String(20),
        nullable=False,
        default=SIGNAL_RESULT_NONE,
        index=True,
    )

    entry_price = Column(
        Numeric(24, 10),
        nullable=True,
    )

    stop_loss = Column(
        Numeric(24, 10),
        nullable=True,
    )

    take_profit_1 = Column(
        Numeric(24, 10),
        nullable=True,
    )

    take_profit_2 = Column(
        Numeric(24, 10),
        nullable=True,
    )

    take_profit_3 = Column(
        Numeric(24, 10),
        nullable=True,
    )

    risk_reward_ratio = Column(
        Numeric(12, 4),
        nullable=True,
        index=True,
    )

    confidence = Column(
        Numeric(6, 2),
        nullable=False,
        default=Decimal("0.00"),
        index=True,
    )

    confirmations_count = Column(
        Integer,
        nullable=False,
        default=0,
        index=True,
    )

    strategy_version = Column(
        String(50),
        nullable=True,
        index=True,
    )

    market_structure = Column(
        JSON,
        nullable=True,
    )

    confirmations = Column(
        JSON,
        nullable=True,
    )

    analysis_details = Column(
        JSON,
        nullable=True,
    )

    reasoning = Column(
        Text,
        nullable=True,
    )

    rejection_reason = Column(
        Text,
        nullable=True,
    )

    source = Column(
        String(50),
        nullable=False,
        default="MARKETMIND_AI",
        index=True,
    )

    is_trade_allowed = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    minimum_confidence_required = Column(
        Numeric(6, 2),
        nullable=False,
        default=Decimal("80.00"),
    )

    minimum_confirmations_required = Column(
        Integer,
        nullable=False,
        default=3,
    )

    minimum_risk_reward_required = Column(
        Numeric(12, 4),
        nullable=False,
        default=Decimal("1.5000"),
    )

    generated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )

    activated_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    cancelled_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    expired_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    created_by = relationship(
        "User",
        foreign_keys=[created_by_user_id],
        lazy="joined",
    )

    __table_args__ = (
        UniqueConstraint(
            "signal_uid",
            name="uq_trading_signals_signal_uid",
        ),
        Index(
            "ix_trading_signals_symbol_timeframe",
            "symbol",
            "timeframe",
        ),
        Index(
            "ix_trading_signals_status_result",
            "status",
            "result",
        ),
        Index(
            "ix_trading_signals_generated_status",
            "generated_at",
            "status",
        ),
        Index(
            "ix_trading_signals_trade_quality",
            "confidence",
            "confirmations_count",
            "risk_reward_ratio",
        ),
    )

    def normalise(self) -> None:
        self.symbol = str(
            self.symbol or ""
        ).strip().upper()

        self.timeframe = str(
            self.timeframe or ""
        ).strip().upper()

        self.direction = str(
            self.direction or ""
        ).strip().upper()

        self.status = str(
            self.status or SIGNAL_STATUS_PENDING
        ).strip().upper()

        self.result = str(
            self.result or SIGNAL_RESULT_NONE
        ).strip().upper()

        self.signal_uid = str(
            self.signal_uid or ""
        ).strip()

        self.source = str(
            self.source or "MARKETMIND_AI"
        ).strip().upper()

        self.strategy_version = (
            str(
                self.strategy_version
                or ""
            ).strip()
            or None
        )

        self.created_by_user_id = (
            _positive_int_or_none(
                self.created_by_user_id,
                field_name=(
                    "created_by_user_id"
                ),
            )
        )

        self.is_trade_allowed = (
            _strict_bool(
                self.is_trade_allowed,
                field_name=(
                    "is_trade_allowed"
                ),
                default=False,
            )
        )

    def validate_state(self) -> None:
        self.normalise()

        if not self.signal_uid:
            raise ValueError(
                "Signal UID cannot be empty."
            )

        if len(
            self.signal_uid
        ) > MAXIMUM_SIGNAL_UID_LENGTH:
            raise ValueError(
                "Signal UID is too long."
            )

        if self.direction not in VALID_SIGNAL_DIRECTIONS:
            raise ValueError(
                "Invalid signal direction."
            )

        if self.status not in VALID_SIGNAL_STATUSES:
            raise ValueError(
                "Invalid signal status."
            )

        if self.result not in VALID_SIGNAL_RESULTS:
            raise ValueError(
                "Invalid signal result."
            )

        if not self.symbol:
            raise ValueError(
                "Signal symbol cannot be empty."
            )

        if len(
            self.symbol
        ) > MAXIMUM_SYMBOL_LENGTH:
            raise ValueError(
                "Signal symbol is too long."
            )

        if not self.timeframe:
            raise ValueError(
                "Signal timeframe cannot be empty."
            )

        if len(
            self.timeframe
        ) > MAXIMUM_TIMEFRAME_LENGTH:
            raise ValueError(
                "Signal timeframe is too long."
            )

        if len(
            self.direction
        ) > MAXIMUM_DIRECTION_LENGTH:
            raise ValueError(
                "Signal direction is too long."
            )

        if len(
            self.status
        ) > MAXIMUM_STATUS_LENGTH:
            raise ValueError(
                "Signal status is too long."
            )

        if len(
            self.result
        ) > MAXIMUM_RESULT_LENGTH:
            raise ValueError(
                "Signal result is too long."
            )

        if (
            self.strategy_version is not None
            and len(
                self.strategy_version
            ) > MAXIMUM_STRATEGY_VERSION_LENGTH
        ):
            raise ValueError(
                "Strategy version is too long."
            )

        if not self.source:
            raise ValueError(
                "Signal source cannot be empty."
            )

        if len(
            self.source
        ) > MAXIMUM_SOURCE_LENGTH:
            raise ValueError(
                "Signal source is too long."
            )

        confidence = _finite_decimal(
            self.confidence,
            field_name="confidence",
            allow_none=False,
        )

        if (
            confidence < Decimal("0")
            or confidence > MAXIMUM_CONFIDENCE
        ):
            raise ValueError(
                "Confidence must be between 0 and 100."
            )

        self.confidence = confidence

        confirmations = _bounded_int(
            self.confirmations_count,
            field_name="confirmations_count",
            minimum=0,
            maximum=MAXIMUM_CONFIRMATIONS,
        )

        self.confirmations_count = (
            confirmations
        )

        risk_reward = _finite_decimal(
            self.risk_reward_ratio,
            field_name="risk_reward_ratio",
            allow_none=True,
        )

        if (
            risk_reward is not None
            and (
                risk_reward < Decimal("0")
                or risk_reward > MAXIMUM_RISK_REWARD
            )
        ):
            raise ValueError(
                "Risk-reward ratio must be between 0 and 100."
            )

        self.risk_reward_ratio = (
            risk_reward
        )

        for field_name in (
            "entry_price",
            "stop_loss",
            "take_profit_1",
            "take_profit_2",
            "take_profit_3",
        ):
            value = _finite_decimal(
                getattr(
                    self,
                    field_name,
                ),
                field_name=field_name,
                allow_none=True,
            )

            if (
                value is not None
                and value < Decimal("0")
            ):
                raise ValueError(
                    f"{field_name} cannot be negative."
                )

            setattr(
                self,
                field_name,
                value,
            )

        minimum_confidence = _finite_decimal(
            self.minimum_confidence_required,
            field_name="minimum_confidence_required",
            allow_none=False,
        )

        if not (
            Decimal("0")
            <= minimum_confidence
            <= MAXIMUM_CONFIDENCE
        ):
            raise ValueError(
                "Minimum confidence requirement is invalid."
            )

        self.minimum_confidence_required = (
            minimum_confidence
        )

        minimum_confirmations = _bounded_int(
            self.minimum_confirmations_required,
            field_name=(
                "minimum_confirmations_required"
            ),
            minimum=0,
            maximum=MAXIMUM_CONFIRMATIONS,
        )

        self.minimum_confirmations_required = (
            minimum_confirmations
        )

        minimum_risk_reward = _finite_decimal(
            self.minimum_risk_reward_required,
            field_name="minimum_risk_reward_required",
            allow_none=False,
        )

        if not (
            Decimal("0")
            <= minimum_risk_reward
            <= MAXIMUM_RISK_REWARD
        ):
            raise ValueError(
                "Minimum risk-reward requirement is invalid."
            )

        self.minimum_risk_reward_required = (
            minimum_risk_reward
        )

        self.generated_at = (
            _ensure_utc(
                self.generated_at
            )
            or utc_now()
        )
        self.activated_at = _ensure_utc(
            self.activated_at
        )
        self.completed_at = _ensure_utc(
            self.completed_at
        )
        self.cancelled_at = _ensure_utc(
            self.cancelled_at
        )
        self.expired_at = _ensure_utc(
            self.expired_at
        )
        self.created_at = (
            _ensure_utc(
                self.created_at
            )
            or utc_now()
        )
        self.updated_at = (
            _ensure_utc(
                self.updated_at
            )
            or utc_now()
        )

        if (
            self.status == SIGNAL_STATUS_COMPLETED
            and self.result
            not in {
                SIGNAL_RESULT_WIN,
                SIGNAL_RESULT_LOSS,
                SIGNAL_RESULT_BREAKEVEN,
            }
        ):
            raise ValueError(
                "Completed signals require a final result."
            )

        if (
            self.status != SIGNAL_STATUS_COMPLETED
            and self.result
            not in {
                SIGNAL_RESULT_NONE,
                SIGNAL_RESULT_WIN,
                SIGNAL_RESULT_LOSS,
                SIGNAL_RESULT_BREAKEVEN,
            }
        ):
            raise ValueError(
                "Signal result is inconsistent with its status."
            )

    def activate(self) -> None:
        if self.status in {
            SIGNAL_STATUS_COMPLETED,
            SIGNAL_STATUS_CANCELLED,
            SIGNAL_STATUS_EXPIRED,
        }:
            raise ValueError(
                "Finalized signal cannot be activated."
            )

        now = utc_now()
        self.status = SIGNAL_STATUS_ACTIVE
        self.activated_at = now
        self.updated_at = now

    def complete(
        self,
        *,
        result: str,
    ) -> None:
        resolved_result = str(
            result or ""
        ).strip().upper()

        if resolved_result not in {
            SIGNAL_RESULT_WIN,
            SIGNAL_RESULT_LOSS,
            SIGNAL_RESULT_BREAKEVEN,
        }:
            raise ValueError(
                "Completed signal result is invalid."
            )

        if self.status in {
            SIGNAL_STATUS_CANCELLED,
            SIGNAL_STATUS_EXPIRED,
        }:
            raise ValueError(
                "Cancelled or expired signal cannot be completed."
            )

        now = utc_now()

        self.status = SIGNAL_STATUS_COMPLETED
        self.result = resolved_result
        self.completed_at = now
        self.updated_at = now

    def cancel(self) -> None:
        if self.status == SIGNAL_STATUS_COMPLETED:
            raise ValueError(
                "Completed signal cannot be cancelled."
            )

        now = utc_now()

        self.status = SIGNAL_STATUS_CANCELLED
        self.cancelled_at = now
        self.updated_at = now

    def expire(self) -> None:
        if self.status == SIGNAL_STATUS_COMPLETED:
            raise ValueError(
                "Completed signal cannot be expired."
            )

        now = utc_now()

        self.status = SIGNAL_STATUS_EXPIRED
        self.expired_at = now
        self.updated_at = now

    def to_public_dict(self) -> dict[str, object]:
        self.validate_state()

        return {
            "id": self.id,
            "signal_uid": self.signal_uid,
            "created_by_user_id": self.created_by_user_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "direction": self.direction,
            "status": self.status,
            "result": self.result,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit_1": self.take_profit_1,
            "take_profit_2": self.take_profit_2,
            "take_profit_3": self.take_profit_3,
            "risk_reward_ratio": self.risk_reward_ratio,
            "confidence": self.confidence,
            "confirmations_count": self.confirmations_count,
            "strategy_version": self.strategy_version,
            "market_structure": self.market_structure,
            "confirmations": self.confirmations,
            "analysis_details": self.analysis_details,
            "reasoning": self.reasoning,
            "rejection_reason": self.rejection_reason,
            "source": self.source,
            "is_trade_allowed": (self.is_trade_allowed is True),
            "minimum_confidence_required": (
                self.minimum_confidence_required
            ),
            "minimum_confirmations_required": (
                self.minimum_confirmations_required
            ),
            "minimum_risk_reward_required": (
                self.minimum_risk_reward_required
            ),
            "generated_at": self.generated_at,
            "activated_at": self.activated_at,
            "completed_at": self.completed_at,
            "cancelled_at": self.cancelled_at,
            "expired_at": self.expired_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


__all__ = [
    "MAXIMUM_CONFIDENCE",
    "MAXIMUM_CONFIRMATIONS",
    "MAXIMUM_RISK_REWARD",
    "TradingSignal",
    "SIGNAL_DIRECTION_BUY",
    "SIGNAL_DIRECTION_NO_TRADE",
    "SIGNAL_DIRECTION_SELL",
    "SIGNAL_RESULT_BREAKEVEN",
    "SIGNAL_RESULT_LOSS",
    "SIGNAL_RESULT_NONE",
    "SIGNAL_RESULT_WIN",
    "SIGNAL_STATUS_ACTIVE",
    "SIGNAL_STATUS_CANCELLED",
    "SIGNAL_STATUS_COMPLETED",
    "SIGNAL_STATUS_EXPIRED",
    "SIGNAL_STATUS_PENDING",
    "VALID_SIGNAL_DIRECTIONS",
    "VALID_SIGNAL_RESULTS",
    "VALID_SIGNAL_STATUSES",
    "utc_now",
]