from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TradeHistoryBase(BaseModel):
    symbol: str = Field(
        ...,
        min_length=1,
        max_length=50,
    )

    interval: str = Field(
        ...,
        min_length=1,
        max_length=20,
    )

    direction: str = Field(
        ...,
        pattern="^(BUY|SELL)$",
    )

    # Version 30 learning context
    market_session: Optional[str] = Field(
        default=None,
        max_length=20,
    )

    market_condition: Optional[str] = Field(
        default=None,
        max_length=80,
    )

    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float

    confidence: float = Field(
        ...,
        ge=0,
        le=100,
    )

    directional_confidence: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
    )

    confirmation_count: int = Field(
        default=0,
        ge=0,
    )

    trade_quality_score: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
    )

    trade_quality_grade: Optional[str] = Field(
        default=None,
        max_length=30,
    )

    reason: Optional[str] = None
    confirmation_details: Optional[str] = None
    engine_version: Optional[str] = Field(
        default=None,
        max_length=100,
    )


class TradeHistoryCreate(TradeHistoryBase):
    """
    Used internally when saving a newly approved BUY or SELL signal.
    """

    model_config = ConfigDict(extra="forbid")

    signal_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    trade_allowed: bool = True


class TradeHistoryUpdate(BaseModel):
    """
    Used when updating an active trade.

    All fields are optional because trade tracking and completed-trade
    learning updates happen gradually.
    """

    model_config = ConfigDict(extra="forbid")

    current_price: Optional[float] = None
    exit_price: Optional[float] = None

    status: Optional[str] = Field(
        default=None,
        pattern="^(ACTIVE|CLOSED|CANCELLED)$",
    )

    result: Optional[str] = Field(
        default=None,
        pattern=(
            "^(PENDING|TP1_HIT|TP2_HIT|STOP_LOSS|"
            "CANCELLED|BREAKEVEN|WIN|LOSS)$"
        ),
    )

    tp1_hit: Optional[bool] = None
    tp2_hit: Optional[bool] = None
    stop_loss_hit: Optional[bool] = None

    profit_loss_points: Optional[float] = None
    risk_reward_achieved: Optional[float] = None

    trade_duration_seconds: Optional[int] = Field(
        default=None,
        ge=0,
    )

    # Version 30 learning context and registration
    market_session: Optional[str] = Field(
        default=None,
        max_length=20,
    )

    market_condition: Optional[str] = Field(
        default=None,
        max_length=80,
    )

    learning_registered: Optional[bool] = None

    learning_registered_at: Optional[datetime] = None

    learning_result: Optional[str] = Field(
        default=None,
        pattern="^(WIN|LOSS|BREAKEVEN)$",
    )

    learning_confidence_adjustment: Optional[float] = Field(
        default=None,
        ge=-4.0,
        le=4.0,
    )

    updated_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None


class TradeHistoryResponse(TradeHistoryBase):
    """
    Returned by the Version 30 Trade History API.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    signal_id: str

    status: str
    result: str
    trade_allowed: bool

    current_price: Optional[float] = None
    exit_price: Optional[float] = None

    tp1_hit: bool
    tp2_hit: bool
    stop_loss_hit: bool

    profit_loss_points: float
    risk_reward_achieved: Optional[float] = None
    trade_duration_seconds: Optional[int] = None

    # Version 30 persistent learning state
    learning_registered: bool = False
    learning_registered_at: Optional[datetime] = None

    learning_result: Optional[str] = Field(
        default=None,
        pattern="^(WIN|LOSS|BREAKEVEN)$",
    )

    learning_confidence_adjustment: float = Field(
        default=0.0,
        ge=-4.0,
        le=4.0,
    )

    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None


class TradeHistoryListResponse(BaseModel):
    """
    Response format for a list of saved trade signals.
    """

    total: int = Field(
        ge=0,
    )

    trades: list[TradeHistoryResponse]


class TradeStatisticsResponse(BaseModel):
    """
    Performance statistics returned to the dashboard.
    """

    total_trades: int = Field(ge=0)
    active_trades: int = Field(ge=0)
    closed_trades: int = Field(ge=0)

    winning_trades: int = Field(ge=0)
    losing_trades: int = Field(ge=0)
    pending_trades: int = Field(ge=0)

    tp1_trades: int = Field(ge=0)
    tp2_trades: int = Field(ge=0)
    stop_loss_trades: int = Field(ge=0)

    win_rate: float = Field(
        ge=0,
        le=100,
    )

    loss_rate: float = Field(
        ge=0,
        le=100,
    )

    average_confidence: float = Field(
        ge=0,
        le=100,
    )

    average_trade_quality: float = Field(
        ge=0,
        le=100,
    )

    total_profit_loss_points: float


class TradeLearningStatusResponse(BaseModel):
    """
    Version 30 persistent completed-trade learning status.
    """

    version: int = 30
    completed_trade_learning_enabled: bool
    registered_trade_count: int = Field(ge=0)
    pending_learning_count: int = Field(ge=0)

    session_timezone: str
    supported_sessions: list[str]

    timeframe_performance_learning_enabled: bool
    confidence_guardrail_enabled: bool

    minimum_completed_trades: int = Field(
        ge=0,
    )

    maximum_confidence_adjustment: float = Field(
        ge=0,
    )

    minimum_signal_confidence: float = Field(
        ge=0,
        le=100,
    )

    cancelled_trade_learning_enabled: bool
    analysis_only: bool
    broker_connection_enabled: bool
    trade_execution_enabled: bool


__all__ = [
    "TradeHistoryBase",
    "TradeHistoryCreate",
    "TradeHistoryListResponse",
    "TradeHistoryResponse",
    "TradeHistoryUpdate",
    "TradeLearningStatusResponse",
    "TradeStatisticsResponse",
]