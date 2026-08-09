from __future__ import annotations

import logging
from typing import Any, Final, Mapping

from app.market.provider import get_market_data
from app.trading.analysis import analyze_market


logger = logging.getLogger(__name__)

TIMEFRAMES: Final[tuple[str, ...]] = (
    "5min",
    "15min",
    "30min",
    "1h",
    "4h",
    "1day",
)

MAXIMUM_SYMBOL_LENGTH: Final[int] = 40


def _normalise_symbol(
    value: Any,
) -> str:
    symbol = str(
        value or ""
    ).strip().upper()

    if not symbol:
        raise ValueError(
            "Symbol is required."
        )

    if len(
        symbol
    ) > MAXIMUM_SYMBOL_LENGTH:
        raise ValueError(
            "Symbol is too long."
        )

    allowed = set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/"
    )

    if any(
        character not in allowed
        for character in symbol
    ):
        raise ValueError(
            "Symbol contains unsupported characters."
        )

    return symbol


def _safe_error_message(
    value: Any,
) -> str:
    message = str(
        value or "Market data unavailable."
    ).strip()

    if not message:
        message = "Market data unavailable."

    return message[:300]


def analyze_multi_timeframe(
    symbol: str,
) -> dict[str, dict[str, Any]]:
    """
    Analyze the complete automatic multi-timeframe stack.

    Each timeframe is isolated so one provider or analysis failure does not
    prevent the remaining timeframes from being returned.
    """

    try:
        resolved_symbol = _normalise_symbol(
            symbol
        )
    except ValueError as error:
        return {
            timeframe: {
                "error": str(error),
            }
            for timeframe in TIMEFRAMES
        }

    results: dict[
        str,
        dict[str, Any],
    ] = {}

    for timeframe in TIMEFRAMES:
        try:
            market = get_market_data(
                resolved_symbol,
                timeframe,
            )
        except Exception:
            logger.exception(
                "Market provider failed for %s %s.",
                resolved_symbol,
                timeframe,
            )
            results[
                timeframe
            ] = {
                "error": (
                    "Market data provider failed."
                ),
            }
            continue

        if not isinstance(
            market,
            Mapping,
        ):
            results[
                timeframe
            ] = {
                "error": (
                    "Market data provider returned an invalid response."
                ),
            }
            continue

        market = dict(
            market
        )

        if market.get(
            "error"
        ):
            results[
                timeframe
            ] = {
                "error": _safe_error_message(
                    market.get(
                        "error"
                    )
                ),
            }
            continue

        prices = market.get(
            "prices",
            [],
        )

        if not isinstance(
            prices,
            list,
        ) or not prices:
            results[
                timeframe
            ] = {
                "error": (
                    "No price data available."
                ),
            }
            continue

        analysis = analyze_market(
            resolved_symbol,
            prices,
        )

        if not isinstance(
            analysis,
            Mapping,
        ):
            results[
                timeframe
            ] = {
                "error": (
                    "Market analysis returned an invalid response."
                ),
            }
            continue

        analysis = dict(
            analysis
        )

        if analysis.get(
            "error"
        ):
            results[
                timeframe
            ] = {
                "error": _safe_error_message(
                    analysis.get(
                        "error"
                    )
                ),
            }
            continue

        results[
            timeframe
        ] = {
            "trend": analysis.get(
                "trend"
            ),
            "rsi": analysis.get(
                "rsi"
            ),
            "moving_average": analysis.get(
                "moving_average"
            ),
            "ema": analysis.get(
                "ema"
            ),
        }

    return results


__all__ = [
    "MAXIMUM_SYMBOL_LENGTH",
    "TIMEFRAMES",
    "analyze_multi_timeframe",
]