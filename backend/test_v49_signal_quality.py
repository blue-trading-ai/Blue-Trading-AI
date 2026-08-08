from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_ROOT))


def check(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise AssertionError(message)

    print(f"[PASS] {message}")


def main() -> None:
    print("=" * 58)
    print("BLUE-TRADING-AI VERSION 49 SMOKE TEST")
    print("=" * 58)

    from app.services.signal_publication_service import (
        DAILY_SIGNAL_LIMIT,
        DUPLICATE_SIGNAL_COOLDOWN_HOURS,
        MINIMUM_SIGNAL_CONFIDENCE,
        MINIMUM_SIGNAL_CONFIRMATIONS,
        MINIMUM_SIGNAL_RISK_REWARD,
        PREFERRED_DAILY_SIGNAL_TARGET,
        calculate_signal_quality_score,
        rank_signal_candidates,
    )

    check(
        DAILY_SIGNAL_LIMIT == 10,
        "Daily signal limit is 10",
    )

    check(
        PREFERRED_DAILY_SIGNAL_TARGET == 5,
        "Preferred daily signal target is 5",
    )

    check(
        float(MINIMUM_SIGNAL_CONFIDENCE) == 80.0,
        "Minimum confidence is 80%",
    )

    check(
        MINIMUM_SIGNAL_CONFIRMATIONS == 3,
        "Minimum confirmations is 3",
    )

    check(
        float(MINIMUM_SIGNAL_RISK_REWARD) == 1.5,
        "Minimum risk-reward is 1.5",
    )

    check(
        DUPLICATE_SIGNAL_COOLDOWN_HOURS == 4,
        "Duplicate cooldown is 4 hours",
    )

    quality_score = calculate_signal_quality_score(
        confidence=88,
        confirmations_count=5,
        risk_reward_ratio=2.1,
        multi_timeframe_agreement=True,
        market_structure_confirmed=True,
        fundamental_conflict=False,
        high_impact_news_risk=False,
    )

    check(
        float(quality_score) >= 80.0,
        "Strong setup receives a high quality score",
    )

    candidates = [
        {
            "symbol": "EURUSD",
            "confidence": 82,
            "confirmations_count": 3,
            "risk_reward_ratio": 1.6,
            "multi_timeframe_agreement": True,
            "market_structure_confirmed": True,
        },
        {
            "symbol": "XAUUSD",
            "confidence": 91,
            "confirmations_count": 6,
            "risk_reward_ratio": 2.4,
            "multi_timeframe_agreement": True,
            "market_structure_confirmed": True,
        },
        {
            "symbol": "GBPUSD",
            "confidence": 86,
            "confirmations_count": 4,
            "risk_reward_ratio": 1.9,
            "multi_timeframe_agreement": True,
            "market_structure_confirmed": True,
        },
    ]

    ranked = rank_signal_candidates(candidates)

    check(
        len(ranked) == 3,
        "Signal candidates are ranked",
    )

    check(
        ranked[0]["symbol"] == "XAUUSD",
        "Strongest candidate ranks first",
    )

    from app.services.high_quality_signal_service import (
        HighQualitySignalRejected,
        create_high_quality_signal,
        try_create_high_quality_signal,
    )

    check(
        HighQualitySignalRejected is not None,
        "High-quality rejection class imports",
    )

    check(
        callable(create_high_quality_signal),
        "High-quality creation service imports",
    )

    check(
        callable(try_create_high_quality_signal),
        "Safe high-quality creation service imports",
    )

    from main import app

    openapi_schema = app.openapi()
    registered_routes = set(
        openapi_schema.get("paths", {}).keys()
    )

    expected_routes = {
        "/signals/quality/",
        "/signals/quality/status",
        "/signals/quality/create",
    }

    for route_path in sorted(expected_routes):
        check(
            route_path in registered_routes,
            f"Route registered: {route_path}",
        )

    print("=" * 58)
    print("VERSION 49 SMOKE TEST PASSED")
    print("=" * 58)


if __name__ == "__main__":
    main()

