from __future__ import annotations

import logging
from typing import Any, Final

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.trading_signal import TradingSignal
from app.services.signal_publication_service import (
    evaluate_signal_for_publication,
)
from app.services.trading_signal_service import (
    TradingSignalValidationError,
    create_signal,
)


logger = logging.getLogger(__name__)

PUBLICATION_CONTROL_VERSION: Final[int] = 49
DEFAULT_STRATEGY_VERSION: Final[str] = "V49_HIGH_QUALITY"
DEFAULT_SOURCE: Final[str] = "HIGH_QUALITY_PIPELINE"
MAXIMUM_ANALYSIS_KEYS: Final[int] = 500
MAXIMUM_CONFIRMATION_ITEMS: Final[int] = 100


class HighQualitySignalError(Exception):
    """Base exception for high-quality signal creation."""


class HighQualitySignalRejected(
    HighQualitySignalError
):
    """Raised when a setup does not pass publication control."""


def _safe_bool(
    value: Any,
    default: bool = False,
) -> bool:
    if isinstance(
        value,
        bool,
    ):
        return value

    if isinstance(
        value,
        (int, float),
    ) and not isinstance(
        value,
        bool,
    ):
        if value == 1:
            return True
        if value == 0:
            return False
        return default

    if isinstance(
        value,
        str,
    ):
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
) -> int:
    if isinstance(
        value,
        bool,
    ):
        return default

    try:
        resolved = int(
            value
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return default

    return max(
        0,
        resolved,
    )


def _validate_mapping(
    value: Any,
    *,
    field_name: str,
    allow_none: bool = True,
) -> dict[str, Any] | None:
    if value is None:
        if allow_none:
            return None

        raise HighQualitySignalError(
            f"{field_name} is required."
        )

    if not isinstance(
        value,
        dict,
    ):
        raise HighQualitySignalError(
            f"{field_name} must be a dictionary."
        )

    if len(
        value
    ) > MAXIMUM_ANALYSIS_KEYS:
        raise HighQualitySignalError(
            f"{field_name} contains too many fields."
        )

    return value


def _validate_confirmations(
    value: list[Any] | dict[str, Any] | None,
) -> list[Any] | dict[str, Any] | None:
    if value is None:
        return None

    if isinstance(
        value,
        list,
    ):
        if len(
            value
        ) > MAXIMUM_CONFIRMATION_ITEMS:
            raise HighQualitySignalError(
                "confirmations contains too many items."
            )

        return value

    if isinstance(
        value,
        dict,
    ):
        if len(
            value
        ) > MAXIMUM_ANALYSIS_KEYS:
            raise HighQualitySignalError(
                "confirmations contains too many fields."
            )

        return value

    raise HighQualitySignalError(
        "confirmations must be a list or dictionary."
    )


def create_high_quality_signal(
    db: Session,
    *,
    symbol: str,
    timeframe: str,
    direction: str,
    confidence: Any,
    confirmations_count: int,
    risk_reward_ratio: Any,
    multi_timeframe_agreement: bool,
    market_structure_confirmed: bool,
    fundamental_conflict: bool = False,
    high_impact_news_risk: bool = False,
    entry_price: Any = None,
    stop_loss: Any = None,
    take_profit_1: Any = None,
    take_profit_2: Any = None,
    take_profit_3: Any = None,
    strategy_version: str | None = None,
    market_structure: dict[str, Any] | None = None,
    confirmations: list[Any] | dict[str, Any] | None = None,
    analysis_details: dict[str, Any] | None = None,
    reasoning: str | None = None,
    source: str = DEFAULT_SOURCE,
    user_id: int | None = None,
    commit: bool = True,
) -> tuple[
    TradingSignal,
    dict[str, Any],
]:
    """
    Evaluate and store one publishable high-quality signal.

    The signal is rejected before database creation when:
    - confidence is below 80%;
    - confirmations are below 3;
    - risk-reward is below 1.5;
    - multi-timeframe agreement is missing;
    - market structure is not confirmed;
    - fundamentals conflict;
    - high-impact news risk is present;
    - a duplicate active signal exists;
    - the daily limit has been reached.
    """

    if not isinstance(
        db,
        Session,
    ):
        raise HighQualitySignalError(
            "A valid database session is required."
        )

    resolved_market_structure = _validate_mapping(
        market_structure,
        field_name="market_structure",
    )
    resolved_analysis_details = (
        _validate_mapping(
            analysis_details,
            field_name="analysis_details",
        )
        or {}
    )
    resolved_confirmations = _validate_confirmations(
        confirmations
    )

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

    try:
        evaluation = evaluate_signal_for_publication(
            db,
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            confidence=confidence,
            confirmations_count=confirmations_count,
            risk_reward_ratio=risk_reward_ratio,
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
    except SQLAlchemyError:
        raise
    except HighQualitySignalError:
        raise
    except Exception:
        logger.exception(
            "Signal publication evaluation failed.",
            extra={
                "symbol": str(
                    symbol or ""
                ).strip().upper(),
                "timeframe": str(
                    timeframe or ""
                ).strip().upper(),
            },
        )
        raise

    if not isinstance(
        evaluation,
        dict,
    ):
        raise HighQualitySignalError(
            "Publication control returned an invalid response."
        )

    publishable = _safe_bool(
        evaluation.get(
            "publishable",
            False,
        )
    )

    raw_rejection_reasons = evaluation.get(
        "rejection_reasons",
        [],
    )

    if isinstance(
        raw_rejection_reasons,
        list,
    ):
        rejection_reasons = [
            str(
                reason
            ).strip()
            for reason in raw_rejection_reasons
            if str(
                reason
            ).strip()
        ]
    else:
        rejection_reasons = []

    if not publishable:
        reasons = "; ".join(
            rejection_reasons
        )

        raise HighQualitySignalRejected(
            reasons
            or "Signal did not pass publication control."
        )

    publication_control = {
        "version": PUBLICATION_CONTROL_VERSION,
        "quality_score": str(
            evaluation.get(
                "quality_score",
                "0",
            )
        ),
        "published_today_before_creation": (
            _safe_non_negative_int(
                evaluation.get(
                    "published_today",
                    0,
                )
            )
        ),
        "daily_signal_limit": (
            _safe_non_negative_int(
                evaluation.get(
                    "daily_signal_limit",
                    0,
                )
            )
        ),
        "preferred_daily_target": (
            _safe_non_negative_int(
                evaluation.get(
                    "preferred_daily_target",
                    0,
                )
            )
        ),
        "remaining_signal_slots_before_creation": (
            _safe_non_negative_int(
                evaluation.get(
                    "remaining_signal_slots",
                    0,
                )
            )
        ),
        "multi_timeframe_agreement": (
            resolved_multi_timeframe_agreement
        ),
        "market_structure_confirmed": (
            resolved_market_structure_confirmed
        ),
        "fundamental_conflict": (
            resolved_fundamental_conflict
        ),
        "high_impact_news_risk": (
            resolved_high_impact_news_risk
        ),
    }

    resolved_analysis_details = dict(
        resolved_analysis_details
    )
    resolved_analysis_details[
        "publication_control"
    ] = publication_control

    resolved_user_id: int | None

    if user_id is None:
        resolved_user_id = None
    else:
        if isinstance(
            user_id,
            bool,
        ):
            raise HighQualitySignalError(
                "user_id must be an integer."
            )

        try:
            resolved_user_id = int(
                user_id
            )
        except (
            TypeError,
            ValueError,
            OverflowError,
        ) as exc:
            raise HighQualitySignalError(
                "user_id must be an integer."
            ) from exc

        if resolved_user_id < 0:
            raise HighQualitySignalError(
                "user_id cannot be negative."
            )

    try:
        signal = create_signal(
            db,
            created_by_user_id=resolved_user_id,
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            confidence=confidence,
            confirmations_count=(
                confirmations_count
            ),
            risk_reward_ratio=(
                risk_reward_ratio
            ),
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            take_profit_3=take_profit_3,
            strategy_version=(
                strategy_version
                or DEFAULT_STRATEGY_VERSION
            ),
            market_structure=(
                resolved_market_structure
            ),
            confirmations=(
                resolved_confirmations
            ),
            analysis_details=(
                resolved_analysis_details
            ),
            reasoning=reasoning,
            source=(
                source
                or DEFAULT_SOURCE
            ),
            commit=commit,
        )
    except TradingSignalValidationError:
        if commit:
            db.rollback()
        raise
    except SQLAlchemyError:
        if commit:
            db.rollback()
        raise
    except Exception:
        if commit:
            db.rollback()

        logger.exception(
            "High-quality signal persistence failed.",
            extra={
                "symbol": str(
                    symbol or ""
                ).strip().upper(),
                "timeframe": str(
                    timeframe or ""
                ).strip().upper(),
            },
        )
        raise

    result = dict(
        evaluation
    )
    result[
        "signal_uid"
    ] = signal.signal_uid
    result[
        "signal_id"
    ] = signal.id

    published_today_before = _safe_non_negative_int(
        evaluation.get(
            "published_today",
            0,
        )
    )
    daily_signal_limit = _safe_non_negative_int(
        evaluation.get(
            "daily_signal_limit",
            0,
        )
    )

    published_today_after = (
        published_today_before
        + 1
    )

    result[
        "published_today_after_creation"
    ] = published_today_after
    result[
        "remaining_signal_slots_after_creation"
    ] = max(
        0,
        daily_signal_limit
        - published_today_after,
    )

    return (
        signal,
        result,
    )


def try_create_high_quality_signal(
    db: Session,
    **fields: Any,
) -> dict[str, Any]:
    """Safe non-raising interface for pipelines and APIs."""

    try:
        signal, publication = (
            create_high_quality_signal(
                db,
                **fields,
            )
        )

        return {
            "created": True,
            "signal": signal,
            "publication": publication,
            "rejection_reasons": [],
        }

    except HighQualitySignalRejected as error:
        db.rollback()

        return {
            "created": False,
            "signal": None,
            "publication": None,
            "rejection_reasons": [
                reason.strip()
                for reason in str(
                    error
                ).split(";")
                if reason.strip()
            ],
        }


__all__ = [
    "DEFAULT_SOURCE",
    "DEFAULT_STRATEGY_VERSION",
    "HighQualitySignalError",
    "HighQualitySignalRejected",
    "PUBLICATION_CONTROL_VERSION",
    "create_high_quality_signal",
    "try_create_high_quality_signal",
]