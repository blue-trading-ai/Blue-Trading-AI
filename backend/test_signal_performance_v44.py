from __future__ import annotations

import os
import sys
from decimal import Decimal
from typing import Any

import requests

from app.database.connection import SessionLocal
from app.models.trading_signal import TradingSignal
from app.services.signal_performance_service import (
    LEARNING_MINIMUM_COMPLETED_TRADES,
    get_overall_performance,
    get_performance_snapshot,
    get_recent_completed_signals,
    get_symbol_performance,
    get_timeframe_performance,
)
from app.services.trading_signal_service import create_signal


BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

TIMEOUT = 20


class ValidationFailure(Exception):
    pass


def print_step(number: int, title: str) -> None:
    print(f"\n[{number}/10] {title}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationFailure(message)


def json_body(response: requests.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception as exc:
        raise ValidationFailure(
            f"Response was not JSON: {response.text[:500]}"
        ) from exc

    require(
        isinstance(payload, dict),
        "Expected a JSON object response.",
    )

    return payload


def seed_completed_signal(
    db,
    *,
    symbol: str,
    timeframe: str,
    result: str,
    confidence: str,
    risk_reward: str,
) -> TradingSignal:
    signal = create_signal(
        db,
        symbol=symbol,
        timeframe=timeframe,
        direction="BUY",
        confidence=Decimal(confidence),
        confirmations_count=4,
        risk_reward_ratio=Decimal(risk_reward),
        entry_price=Decimal("100.00"),
        stop_loss=Decimal("95.00"),
        take_profit_1=Decimal("110.00"),
        strategy_version="V44_TEST",
        confirmations=[
            "BOS",
            "Order Block",
            "Liquidity Sweep",
            "RSI",
        ],
        commit=True,
    )

    signal.complete(result=result)
    db.commit()
    db.refresh(signal)

    return signal


def main() -> int:
    print("=" * 70)
    print("BLUE TRADING AI - VERSION 44 SIGNAL PERFORMANCE TEST")
    print("=" * 70)

    created_ids: list[int] = []

    try:
        print_step(1, "API reports Version 44")

        response = requests.get(
            f"{BASE_URL}/",
            timeout=TIMEOUT,
        )

        require(
            response.status_code == 200,
            (
                "Main API failed: "
                f"{response.status_code} {response.text}"
            ),
        )

        payload = json_body(response)

        require(
            str(payload.get("version")) == "44.0.0",
            f"Expected version 44.0.0, got {payload}",
        )

        print("PASSED")

        print_step(2, "Performance API rejects anonymous access")

        response = requests.get(
            f"{BASE_URL}/signals/performance/",
            timeout=TIMEOUT,
        )

        require(
            response.status_code in {401, 403},
            (
                "Anonymous access was not blocked: "
                f"{response.status_code} {response.text}"
            ),
        )

        print("PASSED")

        db = SessionLocal()

        try:
            print_step(3, "Completed signal history is seeded")

            dataset = [
                ("XAUUSD", "1h", "WIN", "90.00", "2.0000"),
                ("XAUUSD", "1h", "WIN", "88.00", "1.8000"),
                ("XAUUSD", "4h", "LOSS", "84.00", "1.6000"),
                ("BTCUSD", "15m", "LOSS", "82.00", "1.7000"),
                ("BTCUSD", "15m", "BREAKEVEN", "86.00", "1.9000"),
            ]

            for row in dataset:
                signal = seed_completed_signal(
                    db,
                    symbol=row[0],
                    timeframe=row[1],
                    result=row[2],
                    confidence=row[3],
                    risk_reward=row[4],
                )
                created_ids.append(int(signal.id))

            require(
                len(created_ids) == 5,
                "Expected five seeded signals.",
            )

            print("PASSED")

            print_step(4, "Overall result counts are correct")

            overall = get_overall_performance(db)

            require(
                int(overall["wins"]) >= 2,
                "Expected at least two wins.",
            )
            require(
                int(overall["losses"]) >= 2,
                "Expected at least two losses.",
            )
            require(
                int(overall["breakevens"]) >= 1,
                "Expected at least one breakeven.",
            )

            print("PASSED")

            print_step(5, "Win rate is calculated from decisive trades")

            require(
                Decimal(str(overall["win_rate"]))
                >= Decimal("50.00"),
                (
                    "Expected seeded decisive win rate "
                    "to be at least 50%."
                ),
            )

            require(
                Decimal(str(overall["average_confidence"]))
                > Decimal("0"),
                "Average confidence was not calculated.",
            )

            require(
                Decimal(str(overall["average_risk_reward"]))
                > Decimal("0"),
                "Average risk-reward was not calculated.",
            )

            print("PASSED")

            print_step(6, "Performance is grouped by symbol")

            by_symbol = get_symbol_performance(db)
            symbol_map = {
                row["symbol"]: row
                for row in by_symbol
            }

            require(
                "XAUUSD" in symbol_map,
                "XAUUSD performance is missing.",
            )
            require(
                "BTCUSD" in symbol_map,
                "BTCUSD performance is missing.",
            )
            require(
                int(
                    symbol_map["XAUUSD"][
                        "total_completed"
                    ]
                )
                >= 3,
                "XAUUSD completed count is incorrect.",
            )

            print("PASSED")

            print_step(7, "Performance is grouped by timeframe")

            by_timeframe = get_timeframe_performance(db)
            timeframe_map = {
                row["timeframe"]: row
                for row in by_timeframe
            }

            for timeframe in {"1h", "4h", "15m"}:
                require(
                    timeframe in timeframe_map,
                    (
                        "Missing timeframe performance: "
                        f"{timeframe}"
                    ),
                )

            print("PASSED")

            print_step(8, "Recent completed history respects limit")

            recent = get_recent_completed_signals(
                db,
                limit=3,
            )

            require(
                len(recent) <= 3,
                "Recent history exceeded requested limit.",
            )
            require(
                all(
                    row.get("status") == "COMPLETED"
                    for row in recent
                ),
                "Recent history returned incomplete signals.",
            )

            print("PASSED")

            print_step(9, "Performance snapshot contains all sections")

            snapshot = get_performance_snapshot(
                db,
                recent_limit=4,
            )

            for section in {
                "overall",
                "by_symbol",
                "by_timeframe",
                "recent_completed_signals",
            }:
                require(
                    section in snapshot,
                    f"Snapshot is missing: {section}",
                )

            require(
                len(
                    snapshot[
                        "recent_completed_signals"
                    ]
                )
                <= 4,
                "Snapshot recent limit was not enforced.",
            )

            print("PASSED")

            print_step(10, "Learning threshold remains 20 trades")

            require(
                LEARNING_MINIMUM_COMPLETED_TRADES == 20,
                "Learning minimum must remain 20.",
            )

            require(
                int(
                    overall[
                        "learning_minimum_completed_trades"
                    ]
                )
                == 20,
                "Overall performance returned wrong threshold.",
            )

            expected_ready = (
                int(overall["total_completed"])
                >= 20
            )

            require(
                bool(overall["learning_ready"])
                == expected_ready,
                "Learning readiness is inconsistent.",
            )

            print("PASSED")

        finally:
            for signal_id in created_ids:
                record = (
                    db.query(TradingSignal)
                    .filter(
                        TradingSignal.id
                        == int(signal_id)
                    )
                    .first()
                )

                if record is not None:
                    db.delete(record)

            db.commit()
            db.close()

        print("\n" + "=" * 70)
        print("VERSION 44 SIGNAL PERFORMANCE TEST: 10/10 PASSED")
        print("=" * 70)
        return 0

    except requests.RequestException as exc:
        print(f"\nFAILED: API connection error: {exc}")
        return 1
    except ValidationFailure as exc:
        print(f"\nFAILED: {exc}")
        return 1
    except Exception as exc:
        print(
            "\nFAILED: Unexpected error: "
            f"{type(exc).__name__}: {exc}"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())

