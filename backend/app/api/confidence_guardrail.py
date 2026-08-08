"""
Blue-Trading-AI
Version 30
app/api/confidence_guardrail.py

API routes for Version 30 confidence guardrails.

Analysis only:
- No broker connection
- No order placement
- No automatic trade execution
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Final

from fastapi import APIRouter, HTTPException, status
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.services.confidence_guardrail_integration import (
    apply_complete_confidence_guardrail,
    get_confidence_guardrail_integration_status,
    integrate_guardrail_into_pipeline_result,
)
from app.services.confidence_guardrail_service import (
    apply_guardrail_to_signal,
    calculate_guarded_confidence,
    get_confidence_guardrail_rules,
)
from app.services.learning_analytics_service import (
    get_direction_performance,
    get_market_condition_performance,
    get_session_performance,
    get_symbol_performance,
)


logger = logging.getLogger(__name__)

PROJECT_NAME: Final = "Blue-Trading-AI"
GUARDRAIL_VERSION: Final[int] = 30
API_VERSION: Final = "30.0.0"

MAXIMUM_SYMBOL_LENGTH: Final[int] = 40
MAXIMUM_SESSION_LENGTH: Final[int] = 40
MAXIMUM_CONDITION_LENGTH: Final[int] = 80
MAXIMUM_DIRECTION_LENGTH: Final[int] = 20
MAXIMUM_TOP_LEVEL_KEYS: Final[int] = 500


router = APIRouter(
    prefix="/confidence-guardrail",
    tags=["Confidence Guardrail V30"],
)


def _normalize_symbol(
    value: str,
) -> str:
    normalized = str(
        value or ""
    ).strip().upper()

    if not normalized:
        raise ValueError(
            "symbol is required"
        )

    allowed = set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/"
    )

    if any(
        character not in allowed
        for character in normalized
    ):
        raise ValueError(
            "symbol contains unsupported characters"
        )

    return normalized


def _normalize_text(
    value: str,
    *,
    field_name: str,
) -> str:
    normalized = str(
        value or ""
    ).strip()

    if not normalized:
        raise ValueError(
            f"{field_name} is required"
        )

    return normalized


def _validate_mapping(
    value: Dict[str, Any],
    *,
    field_name: str,
) -> Dict[str, Any]:
    if not isinstance(
        value,
        dict,
    ):
        raise ValueError(
            f"{field_name} must be an object"
        )

    if len(
        value
    ) > MAXIMUM_TOP_LEVEL_KEYS:
        raise ValueError(
            f"{field_name} contains too many fields"
        )

    return value


def _safe_dict_response(
    value: Any,
    *,
    operation: str,
) -> Dict[str, Any]:
    if isinstance(
        value,
        dict,
    ):
        return value

    logger.error(
        "Confidence guardrail service returned an invalid response.",
        extra={
            "operation": operation,
            "result_type": type(
                value
            ).__name__,
        },
    )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Confidence guardrail service returned an invalid response.",
    )


class ConfidenceGuardrailRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    base_confidence: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        allow_inf_nan=False,
    )
    symbol: str = Field(
        ...,
        min_length=1,
        max_length=MAXIMUM_SYMBOL_LENGTH,
    )
    market_session: str = Field(
        ...,
        min_length=1,
        max_length=MAXIMUM_SESSION_LENGTH,
    )
    market_condition: str = Field(
        ...,
        min_length=1,
        max_length=MAXIMUM_CONDITION_LENGTH,
    )
    direction: str = Field(
        ...,
        min_length=1,
        max_length=MAXIMUM_DIRECTION_LENGTH,
    )

    @field_validator(
        "symbol",
    )
    @classmethod
    def normalize_symbol(
        cls,
        value: str,
    ) -> str:
        return _normalize_symbol(
            value
        )

    @field_validator(
        "market_session",
        "market_condition",
        "direction",
    )
    @classmethod
    def normalize_text_fields(
        cls,
        value: str,
        info,
    ) -> str:
        normalized = _normalize_text(
            value,
            field_name=info.field_name,
        )

        if info.field_name == "direction":
            normalized = normalized.upper()

            aliases = {
                "LONG": "BUY",
                "BULLISH": "BUY",
                "SHORT": "SELL",
                "BEARISH": "SELL",
            }

            normalized = aliases.get(
                normalized,
                normalized,
            )

        elif info.field_name == "market_session":
            normalized = normalized.lower()

        elif info.field_name == "market_condition":
            normalized = normalized.lower().replace(
                " ",
                "_",
            )

        return normalized


class SignalGuardrailRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    signal: Dict[str, Any]

    @field_validator(
        "signal",
    )
    @classmethod
    def validate_signal(
        cls,
        value: Dict[str, Any],
    ) -> Dict[str, Any]:
        return _validate_mapping(
            value,
            field_name="signal",
        )


class PipelineGuardrailRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    pipeline_result: Dict[str, Any]

    @field_validator(
        "pipeline_result",
    )
    @classmethod
    def validate_pipeline_result(
        cls,
        value: Dict[str, Any],
    ) -> Dict[str, Any]:
        return _validate_mapping(
            value,
            field_name="pipeline_result",
        )


def get_current_analytics_summary() -> Dict[str, Any]:
    """Build the Version 29 analytics input used by Version 30."""

    try:
        summary = {
            "symbol_performance": get_symbol_performance(),
            "session_performance": get_session_performance(),
            "market_condition_performance": (
                get_market_condition_performance()
            ),
            "direction_performance": get_direction_performance(),
        }
    except Exception:
        logger.exception(
            "Unable to build confidence-guardrail analytics summary."
        )
        raise

    return summary


@router.get("/")
def confidence_guardrail_home() -> Dict[str, Any]:
    """Return Version 30 module information."""

    try:
        rules = get_confidence_guardrail_rules()
    except Exception as error:
        logger.exception(
            "Unable to load confidence guardrail rules."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to load Version 30 confidence guardrail rules.",
        ) from error

    return {
        "status": "success",
        "project": PROJECT_NAME,
        "version": API_VERSION,
        "safety_version": GUARDRAIL_VERSION,
        "module": "Confidence Guardrail Intelligence",
        "rules": _safe_dict_response(
            rules,
            operation="home_rules",
        ),
        "features": [
            "completed_trade_confidence_calibration",
            "symbol_performance_guardrail",
            "session_performance_guardrail",
            "market_condition_guardrail",
            "buy_sell_direction_guardrail",
            "minimum_20_completed_trades",
            "maximum_plus_minus_4_adjustment",
            "minimum_80_confidence_signal_rule",
        ],
    }


@router.get("/health")
def confidence_guardrail_health() -> Dict[str, Any]:
    """Return a lightweight health response."""

    return {
        "status": "healthy",
        "project": PROJECT_NAME,
        "version": GUARDRAIL_VERSION,
        "service": "confidence_guardrail",
        "analysis_only": True,
        "broker_connection_enabled": False,
        "trade_execution_enabled": False,
    }


@router.get("/rules")
def confidence_guardrail_rules() -> Dict[str, Any]:
    """Return all Version 30 guardrail rules."""

    try:
        rules = get_confidence_guardrail_rules()
    except Exception as error:
        logger.exception(
            "Unable to load confidence guardrail rules."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to load Version 30 confidence guardrail rules.",
        ) from error

    return {
        "status": "success",
        "version": GUARDRAIL_VERSION,
        "data": _safe_dict_response(
            rules,
            operation="rules",
        ),
    }


@router.get("/integration-status")
def confidence_guardrail_integration_status() -> Dict[str, Any]:
    """Return Version 30 master-pipeline integration status."""

    try:
        result = get_confidence_guardrail_integration_status()
    except Exception as error:
        logger.exception(
            "Unable to load Version 30 integration status."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to load Version 30 integration status.",
        ) from error

    return {
        "status": "success",
        "version": GUARDRAIL_VERSION,
        "data": _safe_dict_response(
            result,
            operation="integration_status",
        ),
    }


@router.post("/evaluate")
def evaluate_confidence_guardrail(
    payload: ConfidenceGuardrailRequest,
) -> Dict[str, Any]:
    """Evaluate one confidence score using current learning analytics."""

    try:
        result = calculate_guarded_confidence(
            base_confidence=payload.base_confidence,
            symbol=payload.symbol,
            market_session=payload.market_session,
            market_condition=payload.market_condition,
            direction=payload.direction,
            symbol_performance=get_symbol_performance(),
            session_performance=get_session_performance(),
            market_condition_performance=(
                get_market_condition_performance()
            ),
            direction_performance=get_direction_performance(),
        )

        if result is None or not hasattr(
            result,
            "to_dict",
        ):
            raise TypeError(
                "Invalid guardrail evaluation result."
            )

        result_payload = result.to_dict()

        if not isinstance(
            result_payload,
            dict,
        ):
            raise TypeError(
                "Invalid guardrail evaluation payload."
            )

        return {
            "status": "success",
            "version": GUARDRAIL_VERSION,
            "data": result_payload,
        }

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                str(error)
                or "Invalid confidence guardrail request."
            ),
        ) from error

    except HTTPException:
        raise

    except Exception as error:
        logger.exception(
            "Unable to evaluate Version 30 confidence guardrail.",
            extra={
                "symbol": payload.symbol,
                "direction": payload.direction,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to evaluate Version 30 confidence guardrail.",
        ) from error


@router.post("/apply-to-signal")
def apply_confidence_guardrail_to_signal(
    payload: SignalGuardrailRequest,
) -> Dict[str, Any]:
    """Apply Version 30 guardrails to one signal object."""

    try:
        updated_signal = apply_guardrail_to_signal(
            signal=dict(
                payload.signal
            ),
            analytics_summary=get_current_analytics_summary(),
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                str(error)
                or "Invalid signal guardrail request."
            ),
        ) from error
    except Exception as error:
        logger.exception(
            "Unable to apply Version 30 confidence guardrail to signal."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to apply Version 30 confidence guardrail to signal.",
        ) from error

    return {
        "status": "success",
        "version": GUARDRAIL_VERSION,
        "data": _safe_dict_response(
            updated_signal,
            operation="apply_to_signal",
        ),
    }


@router.post("/apply-complete")
def apply_complete_guardrail(
    payload: SignalGuardrailRequest,
) -> Dict[str, Any]:
    """Apply Version 30 analytics calibration and final decision enforcement."""

    try:
        updated_signal = apply_complete_confidence_guardrail(
            dict(
                payload.signal
            )
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                str(error)
                or "Invalid complete guardrail request."
            ),
        ) from error
    except Exception as error:
        logger.exception(
            "Unable to apply the complete Version 30 confidence guardrail."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to apply the complete Version 30 confidence guardrail.",
        ) from error

    return {
        "status": "success",
        "version": GUARDRAIL_VERSION,
        "data": _safe_dict_response(
            updated_signal,
            operation="apply_complete",
        ),
    }


@router.post("/apply-to-pipeline")
def apply_guardrail_to_pipeline(
    payload: PipelineGuardrailRequest,
) -> Dict[str, Any]:
    """Apply Version 30 guardrails to a master-pipeline result."""

    try:
        updated_result = integrate_guardrail_into_pipeline_result(
            dict(
                payload.pipeline_result
            )
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                str(error)
                or "Invalid pipeline guardrail request."
            ),
        ) from error
    except Exception as error:
        logger.exception(
            "Unable to apply Version 30 guardrails to pipeline result."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to apply Version 30 guardrails to the pipeline result.",
        ) from error

    return {
        "status": "success",
        "version": GUARDRAIL_VERSION,
        "data": _safe_dict_response(
            updated_result,
            operation="apply_to_pipeline",
        ),
    }


__all__ = [
    "ConfidenceGuardrailRequest",
    "PipelineGuardrailRequest",
    "SignalGuardrailRequest",
    "confidence_guardrail_health",
    "confidence_guardrail_home",
    "confidence_guardrail_integration_status",
    "confidence_guardrail_rules",
    "evaluate_confidence_guardrail",
    "apply_confidence_guardrail_to_signal",
    "apply_complete_guardrail",
    "apply_guardrail_to_pipeline",
    "get_current_analytics_summary",
    "router",
]