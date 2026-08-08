"""
Blue-Trading-AI
Version 30 — Master Signal Pipeline API

Purpose:
- Expose the Version 30 Master Signal Pipeline through FastAPI.
- Accept completed engine results.
- Return one unified BUY, SELL, or WAIT decision.
- Include Version 30 confidence guardrail results.

Important:
- Analysis only.
- No broker connection.
- No trade execution.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.services.master_signal_pipeline_service import (
    evaluate_master_signal_pipeline,
)


logger = logging.getLogger(__name__)

MAXIMUM_SIGNAL_ID_LENGTH = 128
MAXIMUM_SYMBOL_LENGTH = 32
MAXIMUM_TIMEFRAME_LENGTH = 16
MAXIMUM_ENGINE_PAYLOAD_KEYS = 500

ALLOWED_SYMBOL_CHARACTERS = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/"
)
ALLOWED_TIMEFRAME_CHARACTERS = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)


router = APIRouter(
    prefix="/master-signal",
    tags=["Master Signal Pipeline V30"],
)


def _validate_engine_payload(
    payload: dict[str, Any],
    field_name: str,
) -> dict[str, Any]:
    if len(payload) > MAXIMUM_ENGINE_PAYLOAD_KEYS:
        raise ValueError(
            f"{field_name} contains too many fields."
        )

    return payload


class MasterSignalPipelineRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    signal_id: str = Field(
        ...,
        min_length=1,
        max_length=MAXIMUM_SIGNAL_ID_LENGTH,
        examples=["XAU-001"],
    )

    symbol: str = Field(
        ...,
        min_length=1,
        max_length=MAXIMUM_SYMBOL_LENGTH,
        examples=["XAUUSD"],
    )

    timeframe: str = Field(
        ...,
        min_length=1,
        max_length=MAXIMUM_TIMEFRAME_LENGTH,
        examples=["M15"],
    )

    market_context: dict[str, Any]
    institutional_smc: dict[str, Any]
    ai_confluence: dict[str, Any]
    multi_timeframe: dict[str, Any]
    dynamic_confidence: dict[str, Any]
    risk_management: dict[str, Any]

    market_structure: dict[str, Any] | None = None
    momentum_analysis: dict[str, Any] | None = None
    pattern_analysis: dict[str, Any] | None = None
    market_regime: dict[str, Any] | None = None
    symbol_winrate: dict[str, Any] | None = None
    learning_intelligence: dict[str, Any] | None = None

    @field_validator(
        "signal_id",
    )
    @classmethod
    def normalize_signal_id(
        cls,
        value: str,
    ) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError(
                "signal_id is required"
            )

        return cleaned

    @field_validator(
        "symbol",
    )
    @classmethod
    def normalize_symbol(
        cls,
        value: str,
    ) -> str:
        cleaned = value.strip().upper()

        if not cleaned:
            raise ValueError(
                "symbol is required"
            )

        if any(
            character not in ALLOWED_SYMBOL_CHARACTERS
            for character in cleaned
        ):
            raise ValueError(
                "symbol contains unsupported characters"
            )

        return cleaned

    @field_validator(
        "timeframe",
    )
    @classmethod
    def normalize_timeframe(
        cls,
        value: str,
    ) -> str:
        cleaned = value.strip().upper()

        if not cleaned:
            raise ValueError(
                "timeframe is required"
            )

        if any(
            character not in ALLOWED_TIMEFRAME_CHARACTERS
            for character in cleaned
        ):
            raise ValueError(
                "timeframe contains unsupported characters"
            )

        return cleaned

    @field_validator(
        "market_context",
        "institutional_smc",
        "ai_confluence",
        "multi_timeframe",
        "dynamic_confidence",
        "risk_management",
        "market_structure",
        "momentum_analysis",
        "pattern_analysis",
        "market_regime",
        "symbol_winrate",
        "learning_intelligence",
    )
    @classmethod
    def validate_engine_payloads(
        cls,
        value: dict[str, Any] | None,
        info,
    ) -> dict[str, Any] | None:
        if value is None:
            return None

        return _validate_engine_payload(
            value,
            info.field_name,
        )


@router.get("/")
def master_signal_home() -> dict[str, Any]:
    return {
        "status": "success",
        "message": (
            "Blue-Trading-AI Version 30 Master Signal "
            "Pipeline API is working"
        ),
        "project": "Blue-Trading-AI",
        "module": "Master Signal Pipeline Engine",
        "version": "30.0.0",
        "safety_version": 30,
        "confidence_guardrail_enabled": True,
        "minimum_final_confidence": 80.0,
        "maximum_guardrail_adjustment": 4.0,
        "minimum_completed_trades": 20,
        "analysis_only": True,
        "broker_connection_enabled": False,
        "trade_execution_enabled": False,
    }


@router.get("/test")
def master_signal_test() -> dict[str, Any]:
    return {
        "status": "success",
        "project": "Blue-Trading-AI",
        "module": "Master Signal Pipeline Engine",
        "version": "30.0.0",
        "safety_version": 30,
        "features": [
            "unified_engine_orchestration",
            "market_context_validation",
            "institutional_smc_validation",
            "ai_confluence_validation",
            "multi_timeframe_validation",
            "dynamic_confidence_validation",
            "risk_management_validation",
            "market_regime_validation",
            "symbol_winrate_learning",
            "completed_trade_learning",
            "confidence_guardrail_v30",
            "direction_conflict_detection",
            "direction_alignment_validation",
            "minimum_confidence_validation",
            "minimum_ranking_score_validation",
            "minimum_confirmation_validation",
            "minimum_risk_reward_validation",
            "hierarchy_conflict_blocking",
            "high_risk_environment_blocking",
            "weak_signal_quality_blocking",
            "fake_breakout_blocking",
            "automatic_wait_decision",
            "final_quality_score",
            "guardrail_adjustment_limit",
            "no_timeframe_performance_learning",
            "no_strategy_optimization",
            "no_strategy_ranking",
            "no_broker_connection",
            "no_trade_execution",
        ],
        "supported_decisions": [
            "BUY",
            "SELL",
            "WAIT",
        ],
        "minimum_final_confidence": 80.0,
        "minimum_ranking_score": 75.0,
        "minimum_confirmations": 3,
        "minimum_risk_reward_ratio": 1.5,
        "minimum_direction_alignment": 75.0,
        "minimum_completed_trades_for_guardrail": 20,
        "maximum_guardrail_adjustment": 4.0,
        "timeframe_performance_learning_enabled": False,
        "strategy_optimization_enabled": False,
        "strategy_ranking_enabled": False,
        "analysis_only": True,
        "broker_connection_enabled": False,
        "trade_execution_enabled": False,
    }


@router.post("/evaluate")
def evaluate_master_signal(
    request: MasterSignalPipelineRequest,
) -> dict[str, Any]:
    """Evaluate all supplied engine outputs through the Version 30 pipeline."""

    try:
        result = evaluate_master_signal_pipeline(
            signal_id=request.signal_id,
            symbol=request.symbol,
            timeframe=request.timeframe,
            market_context=request.market_context,
            institutional_smc=request.institutional_smc,
            ai_confluence=request.ai_confluence,
            multi_timeframe=request.multi_timeframe,
            dynamic_confidence=request.dynamic_confidence,
            risk_management=request.risk_management,
            market_structure=request.market_structure,
            momentum_analysis=request.momentum_analysis,
            pattern_analysis=request.pattern_analysis,
            market_regime=request.market_regime,
            symbol_winrate=request.symbol_winrate,
            learning_intelligence=request.learning_intelligence,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                str(error)
                or "Invalid Master Signal Pipeline request."
            ),
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Unable to evaluate Version 30 Master Signal Pipeline.",
            extra={
                "signal_id": request.signal_id,
                "symbol": request.symbol,
                "timeframe": request.timeframe,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Unable to evaluate the Version 30 "
                "Master Signal Pipeline."
            ),
        ) from error

    if not isinstance(
        result,
        dict,
    ):
        logger.error(
            "Master Signal Pipeline service returned invalid response type.",
            extra={
                "signal_id": request.signal_id,
                "result_type": type(result).__name__,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Master Signal Pipeline returned an invalid response.",
        )

    return result


__all__ = [
    "MasterSignalPipelineRequest",
    "evaluate_master_signal",
    "master_signal_home",
    "master_signal_test",
    "router",
]