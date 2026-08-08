from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Path as ApiPath, status

from app.services.fundamental_analysis_service import (
    analyze_currency_fundamentals,
    analyze_symbol_fundamentals,
    compare_currency_fundamentals,
    get_fundamental_analysis_configuration,
    get_fundamental_data,
    list_fundamental_data,
)


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/fundamental-analysis",
    tags=["Fundamental Analysis"],
)


def _normalize_currency(
    currency: str,
) -> str:
    normalized = currency.strip().upper()

    if len(normalized) != 3 or not normalized.isalpha():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Currency must be a 3-letter alphabetic code."
            ),
        )

    return normalized


def _normalize_symbol(
    symbol: str,
) -> str:
    normalized = symbol.strip().upper()

    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Symbol cannot be empty.",
        )

    allowed_characters = set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/"
    )

    if any(
        character not in allowed_characters
        for character in normalized
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Symbol contains unsupported characters.",
        )

    return normalized


def _validate_result(
    result: Any,
    operation: str,
) -> Any:
    if isinstance(
        result,
        (
            dict,
            list,
        ),
    ):
        return result

    logger.error(
        "Fundamental Analysis service returned an invalid response type.",
        extra={
            "operation": operation,
            "result_type": type(result).__name__,
        },
    )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=(
            "Fundamental Analysis returned an invalid response."
        ),
    )


@router.get("/")
def home() -> dict[str, Any]:
    return {
        "module": "Fundamental Analysis Intelligence",
        "version": "24.0.0",
        "analysis_only": True,
    }


@router.get("/test")
def test() -> dict[str, str]:
    return {
        "status": "ok",
        "module": "Fundamental Analysis",
    }


@router.get("/configuration")
def configuration() -> Any:
    try:
        result = get_fundamental_analysis_configuration()
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                str(error)
                or "Invalid Fundamental Analysis configuration request."
            ),
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Failed to load Fundamental Analysis configuration."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Fundamental Analysis configuration could not be loaded."
            ),
        ) from error

    return _validate_result(
        result,
        "configuration",
    )


@router.get("/currencies")
def currencies() -> Any:
    try:
        result = list_fundamental_data()
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                str(error)
                or "Invalid Fundamental Analysis currencies request."
            ),
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Failed to list Fundamental Analysis currencies."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Fundamental Analysis currencies could not be loaded."
            ),
        ) from error

    return _validate_result(
        result,
        "currencies",
    )


@router.get("/currency/{currency}")
def currency(
    currency: str = ApiPath(
        ...,
        min_length=3,
        max_length=3,
    ),
) -> Any:
    normalized_currency = _normalize_currency(
        currency
    )

    try:
        result = analyze_currency_fundamentals(
            normalized_currency
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                str(error)
                or "Invalid currency fundamental-analysis request."
            ),
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Currency fundamental analysis failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Currency fundamental analysis failed.",
        ) from error

    return _validate_result(
        result,
        "currency",
    )


@router.get("/data/{currency}")
def currency_data(
    currency: str = ApiPath(
        ...,
        min_length=3,
        max_length=3,
    ),
) -> Any:
    normalized_currency = _normalize_currency(
        currency
    )

    try:
        result = get_fundamental_data(
            normalized_currency
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                str(error)
                or "Invalid fundamental-data request."
            ),
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Failed to load fundamental data."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Fundamental data could not be loaded.",
        ) from error

    return _validate_result(
        result,
        "currency-data",
    )


@router.get("/compare/{base}/{quote}")
def compare(
    base: str = ApiPath(
        ...,
        min_length=3,
        max_length=3,
    ),
    quote: str = ApiPath(
        ...,
        min_length=3,
        max_length=3,
    ),
) -> Any:
    normalized_base = _normalize_currency(
        base
    )
    normalized_quote = _normalize_currency(
        quote
    )

    try:
        result = compare_currency_fundamentals(
            normalized_base,
            normalized_quote,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                str(error)
                or "Invalid currency-comparison request."
            ),
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Currency fundamental comparison failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Currency fundamental comparison failed.",
        ) from error

    return _validate_result(
        result,
        "compare",
    )


@router.get("/symbol/{symbol}")
def symbol(
    symbol: str = ApiPath(
        ...,
        min_length=1,
        max_length=32,
    ),
) -> Any:
    normalized_symbol = _normalize_symbol(
        symbol
    )

    try:
        result = analyze_symbol_fundamentals(
            normalized_symbol
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                str(error)
                or "Invalid symbol fundamental-analysis request."
            ),
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Symbol fundamental analysis failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Symbol fundamental analysis failed.",
        ) from error

    return _validate_result(
        result,
        "symbol",
    )


__all__ = [
    "compare",
    "configuration",
    "currencies",
    "currency",
    "currency_data",
    "home",
    "router",
    "symbol",
    "test",
]