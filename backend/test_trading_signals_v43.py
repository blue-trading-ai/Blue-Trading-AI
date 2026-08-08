from __future__ import annotations

import os
import sys
from decimal import Decimal
from typing import Any

import requests
from sqlalchemy import inspect

from app.database.connection import SessionLocal, engine
from app.models.trading_signal import (
    TradingSignal,
    SIGNAL_RESULT_WIN,
    SIGNAL_STATUS_ACTIVE,
    SIGNAL_STATUS_COMPLETED,
    SIGNAL_STATUS_PENDING,
)
from app.services.trading_signal_service import (
    create_signal,
    delete_signal,
    evaluate_trade_eligibility,
    get_signal_by_uid,
    list_signals,
)


BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

TIMEOUT = 20


class ValidationFailure(Exception):
    pass


def print_step(number: int, title: str) -> None:
    print(f"\n[{number}/10] {title}")


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise ValidationFailure(message)


def json_body(
    response: requests.Response,
) -> dict[str, Any]:
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


def main() -> int:
    print("=" * 70)
    print("BLUE TRADING AI - VERSION 43 TRADING SIGNAL DATABASE TEST")
    print("=" * 70)

    created_signal_ids: list[int] = []

    try:
        print_step(1, "API reports Version 43")

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
            str(payload.get("version")) == "43.0.0",
            f"Expected version 43.0.0, got {payload}",
        )

        print("PASSED")

        print_step(2, "Signal API is registered")

        response = requests.get(
            f"{BASE_URL}/signals/",
            timeout=TIMEOUT,
        )

        require(
            response.status_code == 200,
            (
                "Signal API failed: "
                f"{response.status_code} {response.text}"
            ),
        )

        signal_home = json_body(response)

        require(
            int(signal_home.get("signal_api_version", 0)) == 43,
            f"Expected signal_api_version 43, got {signal_home}",
        )
        require(
            signal_home.get("broker_execution_enabled") is False,
            "Broker execution must remain disabled.",
        )

        print("PASSED")

        print_step(3, "Database contains trading_signals table")

        inspector = inspect(engine)

        require(
            "trading_signals"
            in inspector.get_table_names(),
            "trading_signals table is missing.",
        )

        columns = {
            column["name"]
            for column in inspector.get_columns(
                "trading_signals"
            )
        }

        for required_column in {
            "signal_uid",
            "symbol",
            "timeframe",
            "direction",
            "entry_price",
            "stop_loss",
            "take_profit_1",
            "confidence",
            "confirmations_count",
            "risk_reward_ratio",
            "is_trade_allowed",
            "status",
            "result",
        }:
            require(
                required_column in columns,
                (
                    "trading_signals is missing column: "
                    f"{required_column}"
                ),
            )

        print("PASSED")

        print_step(4, "Quality eligibility rules work")

        allowed, reasons = evaluate_trade_eligibility(
            direction="BUY",
            confidence=85,
            confirmations_count=4,
            risk_reward_ratio=2.0,
        )

        require(
            allowed is True,
            f"High-quality signal was blocked: {reasons}",
        )

        blocked, blocked_reasons = (
            evaluate_trade_eligibility(
                direction="SELL",
                confidence=79,
                confirmations_count=2,
                risk_reward_ratio=1.2,
            )
        )

        require(
            blocked is False,
            "Low-quality signal was incorrectly allowed.",
        )
        require(
            len(blocked_reasons) >= 3,
            (
                "Expected confidence, confirmation and R:R "
                "rejection reasons."
            ),
        )

        print("PASSED")

        db = SessionLocal()

        try:
            print_step(5, "High-quality signal is stored as active")

            good_signal = create_signal(
                db,
                symbol="XAUUSD",
                timeframe="1h",
                direction="BUY",
                confidence=Decimal("88.50"),
                confirmations_count=4,
                risk_reward_ratio=Decimal("2.1000"),
                entry_price=Decimal("2350.25"),
                stop_loss=Decimal("2338.50"),
                take_profit_1=Decimal("2375.00"),
                take_profit_2=Decimal("2390.00"),
                strategy_version="V43_TEST",
                confirmations=[
                    "BOS",
                    "Order Block",
                    "Liquidity Sweep",
                    "RSI Confirmation",
                ],
                market_structure={
                    "trend": "BULLISH",
                    "bos": True,
                },
                reasoning=(
                    "Version 43 high-quality persistence test."
                ),
                commit=True,
            )

            created_signal_ids.append(
                int(good_signal.id)
            )

            require(
                good_signal.is_trade_allowed is True,
                "High-quality signal is not trade eligible.",
            )
            require(
                good_signal.status
                == SIGNAL_STATUS_ACTIVE,
                "High-quality signal did not become ACTIVE.",
            )
            require(
                good_signal.signal_uid.startswith("SIG-"),
                "Signal UID format is invalid.",
            )

            print("PASSED")

            print_step(6, "Low-quality signal is stored but blocked")

            blocked_signal = create_signal(
                db,
                symbol="BTCUSD",
                timeframe="15m",
                direction="SELL",
                confidence=Decimal("72.00"),
                confirmations_count=2,
                risk_reward_ratio=Decimal("1.1000"),
                entry_price=Decimal("65000"),
                stop_loss=Decimal("66000"),
                take_profit_1=Decimal("63900"),
                strategy_version="V43_TEST",
                confirmations=[
                    "Resistance",
                    "Bearish Candle",
                ],
                commit=True,
            )

            created_signal_ids.append(
                int(blocked_signal.id)
            )

            require(
                blocked_signal.is_trade_allowed is False,
                "Low-quality signal was marked trade eligible.",
            )
            require(
                blocked_signal.status
                == SIGNAL_STATUS_PENDING,
                "Blocked signal should remain PENDING.",
            )
            require(
                bool(blocked_signal.rejection_reason),
                "Blocked signal has no rejection reason.",
            )

            print("PASSED")

            print_step(7, "Saved signal can be retrieved by UID")

            loaded = get_signal_by_uid(
                db,
                signal_uid=good_signal.signal_uid,
            )

            require(
                loaded is not None,
                "Saved signal could not be retrieved.",
            )
            require(
                loaded.symbol == "XAUUSD",
                "Loaded signal symbol is incorrect.",
            )
            require(
                Decimal(str(loaded.confidence))
                == Decimal("88.50"),
                "Loaded signal confidence is incorrect.",
            )

            print("PASSED")

            print_step(8, "Signal filtering works")

            filtered = list_signals(
                db,
                symbol="XAUUSD",
                timeframe="1h",
                trade_allowed=True,
                limit=20,
                offset=0,
            )

            require(
                any(
                    row.signal_uid
                    == good_signal.signal_uid
                    for row in filtered
                ),
                "Filtered list did not include the signal.",
            )

            require(
                all(
                    row.symbol == "XAUUSD"
                    and row.timeframe == "1h"
                    and row.is_trade_allowed is True
                    for row in filtered
                ),
                "Signal filters returned mismatched records.",
            )

            print("PASSED")

            print_step(9, "Signal can be completed with WIN result")

            good_signal.complete(
                result=SIGNAL_RESULT_WIN
            )
            db.commit()
            db.refresh(good_signal)

            require(
                good_signal.status
                == SIGNAL_STATUS_COMPLETED,
                "Signal status did not become COMPLETED.",
            )
            require(
                good_signal.result
                == SIGNAL_RESULT_WIN,
                "Signal result did not become WIN.",
            )
            require(
                good_signal.completed_at is not None,
                "Completed timestamp is missing.",
            )

            print("PASSED")

            print_step(10, "Stored records expose no execution fields")

            public_payload = good_signal.to_public_dict()
            serialized = str(public_payload).lower()

            for forbidden in {
                "broker_password",
                "broker_token",
                "api_secret",
                "execute_trade",
                "order_id",
            }:
                require(
                    forbidden not in serialized,
                    (
                        "Signal payload exposed forbidden field: "
                        f"{forbidden}"
                    ),
                )

            require(
                public_payload.get(
                    "minimum_confidence_required"
                )
                == Decimal("80.00"),
                "Minimum confidence rule was not stored.",
            )
            require(
                public_payload.get(
                    "minimum_confirmations_required"
                )
                == 3,
                "Minimum confirmation rule was not stored.",
            )

            print("PASSED")

        finally:
            for signal_id in created_signal_ids:
                signal = (
                    db.query(TradingSignal)
                    .filter(
                        TradingSignal.id
                        == int(signal_id)
                    )
                    .first()
                )

                if signal is not None:
                    db.delete(signal)

            db.commit()
            db.close()

        print("\n" + "=" * 70)
        print("VERSION 43 TRADING SIGNAL DATABASE TEST: 10/10 PASSED")
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

