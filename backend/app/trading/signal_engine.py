ENGINE_VERSION = "2026.07.30-MYT-TRADE-QUALITY-SAFETY-8"

import math
from typing import Any, Final, Mapping

MAXIMUM_SYMBOL_LENGTH: Final[int] = 40
MAXIMUM_PRICE_POINTS: Final[int] = 100_000
MAXIMUM_CANDLES: Final[int] = 100_000
MINIMUM_SIGNAL_CONFIDENCE: Final[int] = 80
MINIMUM_SIGNAL_CONFIRMATIONS: Final[int] = 3


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        resolved = float(value)
    except (TypeError, ValueError, OverflowError):
        try:
            resolved = float(default)
        except (TypeError, ValueError, OverflowError):
            resolved = 0.0

    if not math.isfinite(resolved):
        try:
            fallback = float(default)
        except (TypeError, ValueError, OverflowError):
            fallback = 0.0

        return fallback if math.isfinite(fallback) else 0.0

    return resolved


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value == 1:
            return True
        if value == 0:
            return False
        return default

    if isinstance(value, str):
        normalized = value.strip().lower()

        if normalized in {
            "true",
            "1",
            "yes",
            "approved",
            "allowed",
            "active",
        }:
            return True

        if normalized in {
            "false",
            "0",
            "no",
            "blocked",
            "rejected",
            "wait",
        }:
            return False

    return default


def _safe_mapping(value: Any) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_nested_mapping(
    source: Mapping[str, Any],
    key: str,
) -> dict:
    return _safe_mapping(source.get(key))


def _normalise_symbol(value: Any) -> str:
    symbol = str(value or "").strip().upper()

    if not symbol:
        raise ValueError("Symbol is required.")

    if len(symbol) > MAXIMUM_SYMBOL_LENGTH:
        raise ValueError("Symbol is too long.")

    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/")

    if any(character not in allowed for character in symbol):
        raise ValueError("Symbol contains unsupported characters.")

    return symbol


def _normalise_prices(values: Any) -> list[float]:
    if not isinstance(values, list) or not values:
        raise ValueError("No price data available.")

    if len(values) > MAXIMUM_PRICE_POINTS:
        raise ValueError("Price history exceeds the supported safety limit.")

    output: list[float] = []

    for value in values:
        resolved = _safe_float(value, default=float("nan"))

        if not math.isfinite(resolved) or resolved <= 0.0:
            raise ValueError("Price data contains an invalid value.")

        output.append(resolved)

    return output


def _normalise_candles(values: Any) -> list[dict] | None:
    if values is None:
        return None

    if not isinstance(values, list):
        raise ValueError("Candles must be a list.")

    if len(values) > MAXIMUM_CANDLES:
        raise ValueError("Candle history exceeds the supported safety limit.")

    output: list[dict] = []

    for candle in values:
        if not isinstance(candle, Mapping):
            raise ValueError("Candle data contains an invalid record.")

        output.append(dict(candle))

    return output


from app.trading.analysis import analyze_market
from app.trading.multi_timeframe import analyze_multi_timeframe

from app.trading.patterns import (
    detect_double_bottom,
    detect_double_top,
    detect_breakout,
)

from app.trading.market_structure import detect_market_structure
from app.trading.bos import detect_bos
from app.trading.choch import detect_choch
from app.trading.order_blocks import detect_order_block
from app.trading.liquidity import detect_liquidity_sweep
from app.trading.fvg import detect_fair_value_gap
from app.trading.premium_discount import detect_premium_discount_zone
from app.trading.ote import detect_optimal_trade_entry
from app.trading.candlestick_patterns import detect_candlestick_pattern
from app.trading.trendline import detect_trendline
from app.trading.supply_demand import detect_supply_demand
from app.trading.equal_high_low import detect_equal_highs_lows
from app.trading.breaker_block import detect_breaker_block
from app.trading.mitigation_block import detect_mitigation_block
from app.trading.volume_confirmation import detect_volume_confirmation
from app.trading.atr_volatility import detect_atr_volatility
from app.trading.session_analysis import analyze_trading_session
from app.trading.market_regime import analyze_market_regime
from app.trading.retest_confirmation import detect_retest_confirmation
from app.trading.market_alignment import (
    evaluate_market_alignment,
    apply_alignment_penalty,
)

from app.trading.risk import format_price
from app.trading.dynamic_sl_tp_engine import calculate_fixed_sl_tp
from app.trading.trade_quality import evaluate_trade_quality


def generate_signal(
    symbol: str,
    prices: list,
    candles: list | None = None,
) -> dict:
    """
    Generate a trading signal using technical analysis, market structure,
    BOS, CHoCH, Order Blocks, Liquidity Sweeps, Fair Value Gaps,
    Premium/Discount zones, Optimal Trade Entry, candlestick patterns,
    multi-timeframe confirmation, chart patterns, and risk management.
    """

    # ==========================================
    # VALIDATE DATA
    # ==========================================
    try:
        symbol = _normalise_symbol(symbol)
        prices = _normalise_prices(prices)
        candles = _normalise_candles(candles)
    except ValueError as error:
        return {
            "error": str(error),
            "engine_version": ENGINE_VERSION,
            "trade_allowed": False,
            "signal": "NO TRADE",
        }

    analysis = analyze_market(symbol, prices)

    if not isinstance(analysis, Mapping):
        return {
            "error": "Market analysis returned an invalid response.",
            "engine_version": ENGINE_VERSION,
            "trade_allowed": False,
            "signal": "NO TRADE",
        }

    analysis = dict(analysis)

    if "error" in analysis:
        return {
            "error": str(
                analysis.get("error")
                or "Market analysis failed."
            )[:500],
            "engine_version": ENGINE_VERSION,
            "trade_allowed": False,
            "signal": "NO TRADE",
        }

    current_price = prices[-1]

    trend = analysis.get("trend")

    def _optional_finite(value: Any) -> float | None:
        if value is None:
            return None

        resolved = _safe_float(
            value,
            default=float("nan"),
        )

        return resolved if math.isfinite(resolved) else None

    rsi = _optional_finite(
        analysis.get("rsi")
    )
    ema = _optional_finite(
        analysis.get("ema")
    )
    moving_average = _optional_finite(
        analysis.get("moving_average")
    )
    support = _optional_finite(
        analysis.get("support")
    )
    resistance = _optional_finite(
        analysis.get("resistance")
    )

    # ==========================================
    # MULTI-TIMEFRAME ANALYSIS
    # ==========================================
    multi_tf = analyze_multi_timeframe(symbol)

    if not isinstance(multi_tf, dict):
        multi_tf = {}

    d1_trend = _safe_nested_mapping(
        multi_tf,
        "1day",
    ).get("trend")
    h4_trend = _safe_nested_mapping(
        multi_tf,
        "4h",
    ).get("trend")
    h1_trend = _safe_nested_mapping(
        multi_tf,
        "1h",
    ).get("trend")
    m30_trend = _safe_nested_mapping(
        multi_tf,
        "30min",
    ).get("trend")
    m15_trend = _safe_nested_mapping(
        multi_tf,
        "15min",
    ).get("trend")
    m5_trend = _safe_nested_mapping(
        multi_tf,
        "5min",
    ).get("trend")

    # ==========================================
    # CHART PATTERNS
    # ==========================================
    double_bottom = detect_double_bottom(prices)
    double_top = detect_double_top(prices)

    breakout = detect_breakout(
        current_price,
        support,
        resistance,
    )

    # ==========================================
    # MARKET STRUCTURE
    # ==========================================
    market_structure = detect_market_structure(prices)

    if not isinstance(market_structure, dict):
        market_structure = {}

    structure = market_structure.get("structure")

    # Compatibility with the older output format.
    if structure is None:
        if market_structure.get("HH") and market_structure.get("HL"):
            structure = "HH-HL"
        elif market_structure.get("LH") and market_structure.get("LL"):
            structure = "LH-LL"
        else:
            structure = "RANGE"

    # ==========================================
    # BREAK OF STRUCTURE
    # ==========================================
    bos = detect_bos(
        prices=prices,
        lookback=2,
        confirmation_buffer=0.0,
    )

    if not isinstance(bos, dict):
        bos = {}

    bos_direction = bos.get("direction", "NONE")

    # ==========================================
    # CHANGE OF CHARACTER
    # ==========================================
    choch = detect_choch(
        prices=prices,
        lookback=2,
        confirmation_buffer=0.0,
    )

    if not isinstance(choch, dict):
        choch = {
            "detected": False,
            "direction": "NONE",
            "level": None,
            "break_price": current_price,
            "distance": None,
            "previous_structure": structure,
        }

    choch_direction = choch.get("direction", "NONE")

    # ==========================================
    # ORDER BLOCK
    # ==========================================
    order_block = detect_order_block(
        candles if candles is not None else prices
    )

    if not isinstance(order_block, dict):
        order_block = {
            "detected": False,
            "direction": "NONE",
            "status": "NO_ORDER_BLOCK",
            "zone_high": None,
            "zone_low": None,
            "candle_index": None,
            "impulse_strength": None,
            "mitigated": False,
            "current_price": current_price,
        }

    order_block_direction = order_block.get("direction", "NONE")
    order_block_status = order_block.get("status", "NO_ORDER_BLOCK")
    order_block_zone_high = order_block.get("zone_high")
    order_block_zone_low = order_block.get("zone_low")
    order_block_price_inside = False
    order_block_price_near = False

    if (
        isinstance(order_block_zone_high, (int, float))
        and isinstance(order_block_zone_low, (int, float))
        and math.isfinite(float(order_block_zone_high))
        and math.isfinite(float(order_block_zone_low))
    ):
        ob_high = max(
            float(order_block_zone_high),
            float(order_block_zone_low),
        )
        ob_low = min(
            float(order_block_zone_high),
            float(order_block_zone_low),
        )
        ob_width = max(ob_high - ob_low, current_price * 0.0005)
        ob_near_tolerance = max(ob_width * 0.50, current_price * 0.0005)
        order_block_price_inside = ob_low <= current_price <= ob_high
        order_block_price_near = (
            not order_block_price_inside
            and (
                abs(current_price - ob_low) <= ob_near_tolerance
                or abs(current_price - ob_high) <= ob_near_tolerance
            )
        )

    # ==========================================
    # LIQUIDITY SWEEP
    # ==========================================
    liquidity = detect_liquidity_sweep(
        candles if candles is not None else prices,
        lookback=20,
        confirmation_buffer=0.0,
    )

    if not isinstance(liquidity, dict):
        liquidity = {
            "detected": False,
            "direction": "NONE",
            "status": "NO_LIQUIDITY_SWEEP",
            "level": None,
            "sweep_price": None,
            "close_price": current_price,
            "distance": None,
            "candle_index": None,
            "liquidity_candle_index": None,
        }

    liquidity_direction = liquidity.get("direction", "NONE")
    liquidity_status = liquidity.get(
        "status",
        "NO_LIQUIDITY_SWEEP",
    )

    # ==========================================
    # FAIR VALUE GAP
    # ==========================================
    fvg = detect_fair_value_gap(
        candles if candles is not None else prices,
        lookback=30,
        minimum_gap=0.0,
    )

    if not isinstance(fvg, dict):
        fvg = {
            "detected": False,
            "direction": "NONE",
            "status": "NO_FVG",
            "zone_high": None,
            "zone_low": None,
            "gap_size": None,
            "candle_index": None,
            "filled": False,
            "price_inside_zone": False,
            "current_price": current_price,
        }

    fvg_direction = fvg.get("direction", "NONE")
    fvg_status = fvg.get("status", "NO_FVG")
    fvg_price_inside = fvg.get("price_inside_zone", False)

    # ==========================================
    # PREMIUM / DISCOUNT ZONE
    # ==========================================
    premium_discount = detect_premium_discount_zone(
        candles if candles is not None else prices,
        lookback=30,
        equilibrium_tolerance=0.05,
    )

    if not isinstance(premium_discount, dict):
        premium_discount = {
            "detected": False,
            "status": "NO_RANGE",
            "zone": "NONE",
            "swing_high": None,
            "swing_low": None,
            "equilibrium": None,
            "premium_start": None,
            "discount_end": None,
            "current_price": current_price,
            "range_size": None,
            "position_percent": None,
            "high_index": None,
            "low_index": None,
        }

    dealing_zone = premium_discount.get("zone", "NONE")
    dealing_zone_status = premium_discount.get(
        "status",
        "NO_RANGE",
    )

    # ==========================================
    # OPTIMAL TRADE ENTRY
    # ==========================================
    ote = detect_optimal_trade_entry(
        candles if candles is not None else prices,
        lookback=30,
    )

    if not isinstance(ote, dict):
        ote = {
            "detected": False,
            "status": "NO_OTE",
            "direction": "NONE",
            "swing_high": None,
            "swing_low": None,
            "range_direction": "NONE",
            "ote_zone_high": None,
            "ote_zone_low": None,
            "fib_62": None,
            "fib_705": None,
            "fib_79": None,
            "current_price": current_price,
            "price_inside_zone": False,
            "position_percent": None,
            "high_index": None,
            "low_index": None,
        }

    ote_direction = ote.get("direction", "NONE")
    ote_status = ote.get("status", "NO_OTE")
    ote_price_inside = ote.get("price_inside_zone", False)

    # ==========================================
    # CANDLESTICK PATTERN
    # ==========================================
    candlestick = detect_candlestick_pattern(
        candles if candles is not None else prices
    )

    if not isinstance(candlestick, dict):
        candlestick = {
            "detected": False,
            "status": "NO_PATTERN",
            "direction": "NONE",
            "pattern": "NONE",
            "strength": 0,
            "candle_index": None,
            "confirmation_index": None,
            "current_price": current_price,
        }

    candlestick_direction = candlestick.get("direction", "NONE")
    candlestick_status = candlestick.get("status", "NO_PATTERN")
    candlestick_strength = candlestick.get("strength", 0) or 0
    candlestick_pattern = candlestick.get("pattern", "NONE")

    # ==========================================
    # TRENDLINE ANALYSIS
    # ==========================================
    trendline = detect_trendline(
        candles if candles is not None else prices,
        lookback=50,
        swing_strength=2,
    )

    if not isinstance(trendline, dict):
        trendline = {
            "detected": False,
            "status": "NO_TRENDLINE",
            "direction": "NONE",
            "trendline_type": "NONE",
            "slope": None,
            "start_index": None,
            "end_index": None,
            "start_price": None,
            "end_price": None,
            "projected_price": None,
            "current_price": current_price,
            "break_detected": False,
            "break_direction": "NONE",
            "retest_detected": False,
            "distance_to_trendline": None,
        }

    trendline_detected = trendline.get("detected", False)
    trendline_status = trendline.get("status", "NO_TRENDLINE")
    trendline_direction = trendline.get("direction", "NONE")
    trendline_break_direction = trendline.get(
        "break_direction",
        "NONE",
    )
    trendline_retest = trendline.get("retest_detected", False)

    # ==========================================
    # SUPPLY AND DEMAND ANALYSIS
    # ==========================================
    supply_demand = detect_supply_demand(
        candles if candles is not None else prices,
        lookback=50,
    )

    if not isinstance(supply_demand, dict):
        supply_demand = {
            "detected": False,
            "status": "NO_ZONE",
            "direction": "NONE",
            "zone_type": "NONE",
            "zone_high": None,
            "zone_low": None,
            "candle_index": None,
            "impulse_index": None,
            "impulse_strength": 0,
            "current_price": current_price,
            "price_inside_zone": False,
            "price_near_zone": False,
            "near_tolerance": None,
            "mitigated": False,
            "distance_to_zone": None,
            "distance_percent": None,
            "relevance": "NONE",
        }

    supply_demand_detected = supply_demand.get("detected", False)
    supply_demand_status = supply_demand.get("status", "NO_ZONE")
    supply_demand_direction = supply_demand.get("direction", "NONE")
    supply_demand_price_inside = supply_demand.get(
        "price_inside_zone",
        False,
    )
    supply_demand_price_near = supply_demand.get(
        "price_near_zone",
        False,
    )
    supply_demand_relevance = supply_demand.get(
        "relevance",
        "NONE",
    )
    supply_demand_strength = supply_demand.get(
        "impulse_strength",
        0,
    ) or 0

    # ==========================================
    # ATR AND VOLATILITY ANALYSIS
    # ==========================================
    atr_volatility = detect_atr_volatility(
        candles if candles is not None else prices,
        period=14,
    )

    if not isinstance(atr_volatility, dict):
        atr_volatility = {
            "detected": False,
            "status": "INSUFFICIENT_DATA",
            "atr": None,
            "atr_percent": None,
            "volatility": "UNKNOWN",
            "trade_environment": "UNKNOWN",
            "too_low": False,
            "too_high": False,
            "normal": False,
            "strength": 0,
            "actionable": False,
        }

    atr_detected = atr_volatility.get("detected", False)
    atr_volatility_type = atr_volatility.get(
        "volatility",
        "UNKNOWN",
    )
    atr_environment = atr_volatility.get(
        "trade_environment",
        "UNKNOWN",
    )
    atr_strength = atr_volatility.get("strength", 0) or 0
    atr_actionable = atr_volatility.get("actionable", False)

    # ==========================================
    # THREE-SESSION AND KILL-ZONE ANALYSIS
    # ==========================================
    try:
        session_analysis = analyze_trading_session(
            candles if isinstance(candles, list) else None
        )
    except Exception as session_error:
        # Session timing must never crash the trading signal engine.
        # This fallback uses fixed Malaysia time (MYT, UTC+8) and avoids
        # all external timezone-database dependencies.
        from datetime import datetime, timedelta, timezone

        myt = timezone(timedelta(hours=8), name="MYT")
        malaysia_time = datetime.now(timezone.utc).astimezone(myt)
        minute = malaysia_time.hour * 60 + malaysia_time.minute

        def _inside(start: int, end: int) -> bool:
            return (start <= minute < end) if start < end else (minute >= start or minute < end)

        active_sessions = []
        if _inside(7 * 60, 16 * 60):
            active_sessions.append("ASIAN")
        if _inside(15 * 60, 24 * 60):
            active_sessions.append("EUROPEAN")
        if _inside(20 * 60, 5 * 60):
            active_sessions.append("US")

        overlaps = []
        if "ASIAN" in active_sessions and "EUROPEAN" in active_sessions:
            overlaps.append("ASIAN_EUROPEAN")
        if "EUROPEAN" in active_sessions and "US" in active_sessions:
            overlaps.append("EUROPEAN_US")

        session_analysis = {
            "detected": True,
            "status": "ACTIVE" if active_sessions else "OFF_SESSION",
            "time_source": "SAFE_MYT_FALLBACK",
            "timezone": "Asia/Kuala_Lumpur",
            "timezone_abbreviation": "MYT",
            "utc_offset": "+08:00",
            "market_time_utc": datetime.now(timezone.utc).isoformat(),
            "market_time_malaysia": malaysia_time.isoformat(),
            "market_date_malaysia": malaysia_time.strftime("%Y-%m-%d"),
            "market_clock_malaysia": malaysia_time.strftime("%I:%M %p"),
            "current_session": active_sessions[-1] if active_sessions else "OFF_SESSION",
            "primary_session": active_sessions[-1] if active_sessions else "OFF_SESSION",
            "active_sessions": active_sessions,
            "overlap": bool(overlaps),
            "overlap_name": overlaps[-1] if overlaps else None,
            "session_overlaps": overlaps,
            "kill_zones": [],
            "in_kill_zone": False,
            "in_session_overlap": bool(overlaps),
            "liquidity": "HIGH" if overlaps else ("NORMAL" if active_sessions else "LOW"),
            "volatility": "HIGH" if overlaps else ("NORMAL" if active_sessions else "LOW"),
            "trade_environment": "FAVORABLE" if overlaps else ("ACTIVE" if active_sessions else "QUIET"),
            "strength": 85 if overlaps else (65 if active_sessions else 30),
            "actionable": bool(active_sessions),
            "session_windows_malaysia": {
                "ASIAN": "07:00 AM-04:00 PM",
                "EUROPEAN": "03:00 PM-12:00 AM",
                "US": "08:00 PM-05:00 AM",
            },
            "overlap_windows_malaysia": {
                "ASIAN_EUROPEAN": "03:00 PM-04:00 PM",
                "EUROPEAN_US": "08:00 PM-12:00 AM",
            },
            "fallback_used": True,
        }

    if not isinstance(session_analysis, Mapping):
        session_analysis = {
            "detected": False,
            "status": "OFF_SESSION",
            "current_session": "OFF_SESSION",
            "primary_session": "OFF_SESSION",
            "active_sessions": [],
            "session_overlaps": [],
            "kill_zones": [],
            "in_kill_zone": False,
            "in_session_overlap": False,
            "overlap": False,
            "overlap_name": None,
            "liquidity": "LOW",
            "volatility": "LOW",
            "trade_environment": "QUIET",
            "strength": 0,
            "actionable": False,
            "session_windows_malaysia": {},
            "overlap_windows_malaysia": {},
        }
    else:
        session_analysis = dict(session_analysis)

    session_actionable = _safe_bool(
        session_analysis.get("actionable", False)
    )
    session_in_kill_zone = session_analysis.get("in_kill_zone", False)
    session_in_overlap = session_analysis.get("in_session_overlap", False)
    session_primary = session_analysis.get("current_session", "OFF_SESSION")
    session_overlap_name = session_analysis.get("overlap_name")
    session_liquidity = session_analysis.get("liquidity", "LOW")
    session_volatility = session_analysis.get("volatility", "LOW")

    # ==========================================
    # VOLUME CONFIRMATION ANALYSIS
    # ==========================================
    volume_confirmation = detect_volume_confirmation(
        candles if candles is not None else prices,
        period=20,
    )

    if not isinstance(volume_confirmation, dict):
        volume_confirmation = {
            "detected": False,
            "status": "NO_VOLUME_DATA",
            "direction": "NONE",
            "current_volume": None,
            "average_volume": None,
            "volume_ratio": None,
            "relative_volume": None,
            "volume_trend": "NONE",
            "price_direction": "NONE",
            "bullish_confirmation": False,
            "bearish_confirmation": False,
            "climax": False,
            "divergence": False,
            "strength": 0,
            "actionable": False,
        }

    volume_detected = volume_confirmation.get("detected", False)
    volume_status = volume_confirmation.get(
        "status",
        "NO_VOLUME_DATA",
    )
    volume_direction = volume_confirmation.get("direction", "NONE")
    volume_strength = volume_confirmation.get("strength", 0) or 0
    volume_actionable = volume_confirmation.get("actionable", False)
    volume_climax = volume_confirmation.get("climax", False)
    volume_divergence = volume_confirmation.get("divergence", False)

    # ==========================================
    # MITIGATION BLOCK ANALYSIS
    # ==========================================
    mitigation_block = detect_mitigation_block(
        candles if candles is not None else prices,
        bos=bos,
        choch=choch,
        lookback=50,
    )

    if not isinstance(mitigation_block, dict):
        mitigation_block = {
            "detected": False,
            "status": "NO_MITIGATION_BLOCK",
            "direction": "NONE",
            "zone_high": None,
            "zone_low": None,
            "source_index": None,
            "impulse_index": None,
            "retest_index": None,
            "current_price": current_price,
            "price_inside_zone": False,
            "price_near_zone": False,
            "near_tolerance": None,
            "retest": False,
            "mitigated": False,
            "bos_confirmed": False,
            "choch_confirmed": False,
            "distance_to_zone": None,
            "distance_percent": None,
            "impulse_strength": 0,
            "strength": 0,
            "actionable": False,
        }

    mitigation_detected = mitigation_block.get("detected", False)
    mitigation_direction = mitigation_block.get("direction", "NONE")
    mitigation_inside = mitigation_block.get(
        "price_inside_zone",
        False,
    )
    mitigation_near = mitigation_block.get(
        "price_near_zone",
        False,
    )
    mitigation_retest = mitigation_block.get("retest", False)
    mitigation_strength = mitigation_block.get("strength", 0) or 0
    mitigation_actionable = mitigation_block.get(
        "actionable",
        False,
    )

    # ==========================================
    # BREAKER BLOCK ANALYSIS
    # ==========================================
    breaker_block = detect_breaker_block(
        candles if candles is not None else prices,
        bos=bos,
        choch=choch,
        lookback=50,
    )

    if not isinstance(breaker_block, dict):
        breaker_block = {
            "detected": False,
            "status": "NO_BREAKER_BLOCK",
            "direction": "NONE",
            "zone_high": None,
            "zone_low": None,
            "source_index": None,
            "break_index": None,
            "retest_index": None,
            "current_price": current_price,
            "price_inside_zone": False,
            "price_near_zone": False,
            "near_tolerance": None,
            "retest": False,
            "mitigated": False,
            "bos_confirmed": False,
            "choch_confirmed": False,
            "distance_to_zone": None,
            "distance_percent": None,
            "strength": 0,
            "actionable": False,
        }

    breaker_detected = breaker_block.get("detected", False)
    breaker_status = breaker_block.get(
        "status",
        "NO_BREAKER_BLOCK",
    )
    breaker_direction = breaker_block.get("direction", "NONE")
    breaker_inside = breaker_block.get("price_inside_zone", False)
    breaker_near = breaker_block.get("price_near_zone", False)
    breaker_retest = breaker_block.get("retest", False)
    breaker_strength = breaker_block.get("strength", 0) or 0
    breaker_mitigated = breaker_block.get("mitigated", False)
    breaker_bos_confirmed = breaker_block.get("bos_confirmed", False)
    breaker_choch_confirmed = breaker_block.get("choch_confirmed", False)

    # A breaker block is actionable only when price has returned to the zone,
    # both structure confirmations agree, and the zone is still valid.
    breaker_actionable = bool(
        breaker_detected
        and breaker_status == "DETECTED"
        and not breaker_mitigated
        and (breaker_inside or breaker_near)
        and breaker_bos_confirmed
        and breaker_choch_confirmed
    )

    # Keep the API payload and downstream scoring consistent with the
    # corrected Blue-Trading-AI breaker validation.
    breaker_block["actionable"] = breaker_actionable

    # ==========================================
    # EQUAL HIGHS / EQUAL LOWS ANALYSIS
    # ==========================================
    equal_high_low = detect_equal_highs_lows(
        candles if candles is not None else prices,
        lookback=50,
    )

    if not isinstance(equal_high_low, dict):
        equal_high_low = {
            "detected": False,
            "status": "NO_LIQUIDITY_POOL",
            "type": "NONE",
            "direction": "NONE",
            "level": None,
            "first_index": None,
            "second_index": None,
            "touches": 0,
            "tolerance": None,
            "distance_to_level": None,
            "distance_percent": None,
            "current_price": current_price,
            "price_near_level": False,
            "swept": False,
            "breakout": False,
            "strength": 0,
        }

    equal_high_low_detected = equal_high_low.get("detected", False)
    equal_high_low_status = equal_high_low.get(
        "status",
        "NO_LIQUIDITY_POOL",
    )
    equal_high_low_type = equal_high_low.get("type", "NONE")
    equal_high_low_near = equal_high_low.get(
        "price_near_level",
        False,
    )
    equal_high_low_swept = equal_high_low.get("swept", False)
    equal_high_low_breakout = equal_high_low.get(
        "breakout",
        False,
    )
    equal_high_low_strength = equal_high_low.get("strength", 0) or 0

    # ==========================================
    # SCORE ENGINE
    # ==========================================
    buy_score = 0
    sell_score = 0

    buy_reasons = []
    sell_reasons = []

    buy_confirmations = 0
    sell_confirmations = 0

    buy_confirmation_details = []
    sell_confirmation_details = []

    # ==========================================
    # CURRENT TIMEFRAME TREND
    # ==========================================
    if trend == "UPTREND":
        buy_score += 30
        buy_reasons.append("Current timeframe trend is bullish")

    elif trend == "DOWNTREND":
        sell_score += 30
        sell_reasons.append("Current timeframe trend is bearish")

    # ==========================================
    # MARKET STRUCTURE
    # ==========================================
    if structure == "HH-HL":
        if trend == "UPTREND":
            buy_score += 30
            buy_reasons.append(
                "Bullish market structure aligned with current trend"
            )
        else:
            buy_score += 10
            buy_reasons.append(
                "Bullish market structure detected, but current trend is bearish"
            )

    elif structure == "LH-LL":
        if trend == "DOWNTREND":
            sell_score += 30
            sell_reasons.append(
                "Bearish market structure aligned with current trend"
            )
        else:
            sell_score += 10
            sell_reasons.append(
                "Bearish market structure detected, but current trend is bullish"
            )

    # ==========================================
    # RSI
    # ==========================================
    if rsi is not None:
        if 50 <= rsi <= 65:
            buy_score += 20
            buy_reasons.append("RSI confirms bullish momentum")

        elif 35 <= rsi < 50:
            sell_score += 20
            sell_reasons.append("RSI confirms bearish momentum")

        elif rsi > 70:
            buy_score -= 15
            buy_reasons.append("RSI is overbought")

        elif rsi < 30:
            sell_score -= 15
            sell_reasons.append("RSI is oversold")

    # ==========================================
    # EMA VS SMA
    # ==========================================
    if ema is not None and moving_average is not None:
        if ema > moving_average:
            buy_score += 20
            buy_reasons.append("EMA is above SMA")

        elif ema < moving_average:
            sell_score += 20
            sell_reasons.append("EMA is below SMA")

    # ==========================================
    # SUPPORT AND RESISTANCE
    # ==========================================
    if support is not None and current_price > support:
        buy_score += 10
        buy_reasons.append("Price is above support")

    if resistance is not None and current_price < resistance:
        sell_score += 10
        sell_reasons.append("Price is below resistance")

    # ==========================================
    # MULTI-TIMEFRAME CONFIRMATION
    # ==========================================
    timeframe_trends = {
        "D1": d1_trend,
        "H4": h4_trend,
        "H1": h1_trend,
        "M30": m30_trend,
        "M15": m15_trend,
        "M5": m5_trend,
    }
    timeframe_weights = {
        "D1": 3,
        "H4": 3,
        "H1": 2,
        "M30": 1,
        "M15": 1,
        "M5": 1,
    }

    bullish_mtf_weight = sum(
        timeframe_weights[label]
        for label, timeframe_trend in timeframe_trends.items()
        if timeframe_trend == "UPTREND"
    )
    bearish_mtf_weight = sum(
        timeframe_weights[label]
        for label, timeframe_trend in timeframe_trends.items()
        if timeframe_trend == "DOWNTREND"
    )
    available_mtf_weight = sum(
        timeframe_weights[label]
        for label, timeframe_trend in timeframe_trends.items()
        if timeframe_trend in {"UPTREND", "DOWNTREND"}
    )

    buy_confirmed = bool(
        available_mtf_weight >= 6
        and bullish_mtf_weight >= 7
        and bullish_mtf_weight > bearish_mtf_weight
        and d1_trend != "DOWNTREND"
        and h4_trend != "DOWNTREND"
    )

    sell_confirmed = bool(
        available_mtf_weight >= 6
        and bearish_mtf_weight >= 7
        and bearish_mtf_weight > bullish_mtf_weight
        and d1_trend != "UPTREND"
        and h4_trend != "UPTREND"
    )

    if buy_confirmed:
        buy_score += 30
        buy_reasons.append(
            "D1, H4, H1, M30, M15 and M5 weighted bias confirms bullish alignment"
        )

    if sell_confirmed:
        sell_score += 30
        sell_reasons.append(
            "D1, H4, H1, M30, M15 and M5 weighted bias confirms bearish alignment"
        )

    # ==========================================
    # CHART PATTERNS
    # ==========================================
    if double_bottom:
        buy_score += 15
        buy_reasons.append("Double Bottom detected")

    if double_top:
        sell_score += 15
        sell_reasons.append("Double Top detected")

    if breakout == "BULLISH BREAKOUT":
        buy_score += 20
        buy_reasons.append("Bullish breakout detected")

    elif breakout == "BEARISH BREAKOUT":
        sell_score += 20
        sell_reasons.append("Bearish breakout detected")

    # ==========================================
    # BREAK OF STRUCTURE SCORING
    # ==========================================
    if bos_direction == "BULLISH_BOS":
        if structure == "HH-HL":
            buy_score += 25
            buy_reasons.append(
                "Bullish BOS confirms bullish market structure"
            )
        else:
            buy_score += 15
            buy_reasons.append("Bullish BOS detected")

    elif bos_direction == "BEARISH_BOS":
        if structure == "LH-LL":
            sell_score += 25
            sell_reasons.append(
                "Bearish BOS confirms bearish market structure"
            )
        else:
            sell_score += 15
            sell_reasons.append("Bearish BOS detected")

    # ==========================================
    # CHANGE OF CHARACTER SCORING
    # ==========================================
    if choch_direction == "BULLISH_CHOCH":
        buy_score += 20
        sell_score -= 10
        buy_reasons.append(
            "Bullish CHoCH indicates a possible bearish-to-bullish reversal"
        )
        sell_reasons.append(
            "Bullish CHoCH weakens the bearish setup"
        )

    elif choch_direction == "BEARISH_CHOCH":
        sell_score += 20
        buy_score -= 10
        sell_reasons.append(
            "Bearish CHoCH indicates a possible bullish-to-bearish reversal"
        )
        buy_reasons.append(
            "Bearish CHoCH weakens the bullish setup"
        )

    # ==========================================
    # ORDER BLOCK SCORING
    # ==========================================
    if (
        order_block_direction == "BULLISH_ORDER_BLOCK"
        and order_block_status == "ACTIVE"
        and (order_block_price_inside or order_block_price_near)
    ):
        buy_score += 15 if order_block_price_inside else 8
        buy_reasons.append(
            "Price is inside the active bullish Order Block"
            if order_block_price_inside
            else "Price is near the active bullish Order Block"
        )

    elif (
        order_block_direction == "BEARISH_ORDER_BLOCK"
        and order_block_status == "ACTIVE"
        and (order_block_price_inside or order_block_price_near)
    ):
        sell_score += 15 if order_block_price_inside else 8
        sell_reasons.append(
            "Price is inside the active bearish Order Block"
            if order_block_price_inside
            else "Price is near the active bearish Order Block"
        )

    # Mitigated blocks remain visible but do not add points.

    # ==========================================
    # LIQUIDITY SWEEP SCORING
    # ==========================================
    if (
        liquidity_direction == "BULLISH_LIQUIDITY_SWEEP"
        and liquidity_status == "CONFIRMED"
    ):
        buy_score += 20
        sell_score -= 10
        buy_reasons.append(
            "Bullish liquidity sweep confirms rejection below liquidity"
        )
        sell_reasons.append(
            "Bullish liquidity sweep weakens the SELL setup"
        )

    elif (
        liquidity_direction == "BEARISH_LIQUIDITY_SWEEP"
        and liquidity_status == "CONFIRMED"
    ):
        sell_score += 20
        buy_score -= 10
        sell_reasons.append(
            "Bearish liquidity sweep confirms rejection above liquidity"
        )
        buy_reasons.append(
            "Bearish liquidity sweep weakens the BUY setup"
        )

    # ==========================================
    # FAIR VALUE GAP SCORING
    # ==========================================
    if (
        fvg_direction == "BULLISH_FVG"
        and fvg_status == "ACTIVE"
    ):
        if fvg_price_inside:
            buy_score += 20
            buy_reasons.append(
                "Price is inside an active bullish Fair Value Gap"
            )
        else:
            buy_score += 10
            buy_reasons.append(
                "Active bullish Fair Value Gap supports the BUY setup"
            )

    elif (
        fvg_direction == "BEARISH_FVG"
        and fvg_status == "ACTIVE"
    ):
        if fvg_price_inside:
            sell_score += 20
            sell_reasons.append(
                "Price is inside an active bearish Fair Value Gap"
            )
        else:
            sell_score += 10
            sell_reasons.append(
                "Active bearish Fair Value Gap supports the SELL setup"
            )

    # Filled FVGs remain visible but do not add points.

    # ==========================================
    # PREMIUM / DISCOUNT ZONE SCORING
    # ==========================================
    if dealing_zone_status == "ACTIVE":
        if dealing_zone == "DISCOUNT":
            buy_score += 15
            sell_score -= 10

            buy_reasons.append(
                "Price is in the Discount zone, supporting a BUY setup"
            )
            sell_reasons.append(
                "Price is too low in the range for a strong SELL setup"
            )

        elif dealing_zone == "PREMIUM":
            sell_score += 15
            buy_score -= 10

            sell_reasons.append(
                "Price is in the Premium zone, supporting a SELL setup"
            )
            buy_reasons.append(
                "Price is too high in the range for a strong BUY setup"
            )

        elif dealing_zone == "EQUILIBRIUM":
            buy_reasons.append(
                "Price is near Equilibrium with no strong BUY location advantage"
            )
            sell_reasons.append(
                "Price is near Equilibrium with no strong SELL location advantage"
            )

    # ==========================================
    # OPTIMAL TRADE ENTRY SCORING
    # ==========================================
    if (
        ote_direction == "BULLISH_OTE"
        and ote_status == "ACTIVE"
        and ote_price_inside
    ):
        buy_score += 20
        buy_reasons.append(
            "Price is inside the bullish Optimal Trade Entry zone"
        )

        if dealing_zone == "DISCOUNT":
            buy_score += 10
            buy_reasons.append(
                "Bullish OTE aligns with the Discount zone"
            )

    elif (
        ote_direction == "BEARISH_OTE"
        and ote_status == "ACTIVE"
        and ote_price_inside
    ):
        sell_score += 20
        sell_reasons.append(
            "Price is inside the bearish Optimal Trade Entry zone"
        )

        if dealing_zone == "PREMIUM":
            sell_score += 10
            sell_reasons.append(
                "Bearish OTE aligns with the Premium zone"
            )

    # ==========================================
    # ATR AND VOLATILITY SCORING
    # ==========================================
    if atr_detected:
        if atr_volatility_type == "NORMAL":
            if buy_score > sell_score:
                buy_score += 5
                buy_reasons.append(
                    "Normal volatility supports the BUY setup"
                )
            elif sell_score > buy_score:
                sell_score += 5
                sell_reasons.append(
                    "Normal volatility supports the SELL setup"
                )

        elif atr_volatility_type == "HIGH":
            if buy_score > sell_score:
                buy_reasons.append(
                    "High volatility detected; wider risk controls are required"
                )
            elif sell_score > buy_score:
                sell_reasons.append(
                    "High volatility detected; wider risk controls are required"
                )

        elif atr_volatility_type == "LOW":
            if buy_score > sell_score:
                buy_score = max(0, buy_score - 10)
                buy_reasons.append(
                    "Low volatility weakens the BUY setup"
                )
            elif sell_score > buy_score:
                sell_score = max(0, sell_score - 10)
                sell_reasons.append(
                    "Low volatility weakens the SELL setup"
                )

        elif atr_volatility_type == "EXTREME":
            if buy_score > sell_score:
                buy_score = max(0, buy_score - 15)
                buy_reasons.append(
                    "Extreme volatility makes the BUY setup unsafe"
                )
            elif sell_score > buy_score:
                sell_score = max(0, sell_score - 15)
                sell_reasons.append(
                    "Extreme volatility makes the SELL setup unsafe"
                )

    # ==========================================
    # VOLUME CONFIRMATION SCORING
    # ==========================================
    if volume_detected:
        if volume_actionable and volume_direction == "BULLISH":
            buy_score += 15
            buy_reasons.append(
                "Bullish price movement is confirmed by strong volume"
            )

            if volume_strength >= 80:
                buy_score += 5
                buy_reasons.append(
                    "High-strength bullish volume confirmation"
                )

            if volume_climax:
                buy_score += 5
                buy_reasons.append(
                    "Bullish volume climax detected"
                )

        elif volume_actionable and volume_direction == "BEARISH":
            sell_score += 15
            sell_reasons.append(
                "Bearish price movement is confirmed by strong volume"
            )

            if volume_strength >= 80:
                sell_score += 5
                sell_reasons.append(
                    "High-strength bearish volume confirmation"
                )

            if volume_climax:
                sell_score += 5
                sell_reasons.append(
                    "Bearish volume climax detected"
                )

        if volume_divergence:
            if buy_score > sell_score:
                buy_score = max(0, buy_score - 5)
                buy_reasons.append(
                    "Volume divergence weakens the BUY setup"
                )
            elif sell_score > buy_score:
                sell_score = max(0, sell_score - 5)
                sell_reasons.append(
                    "Volume divergence weakens the SELL setup"
                )

    if atr_detected and atr_actionable:
        if buy_score > sell_score:
            buy_confirmations += 1
            buy_confirmation_details.append(
                "Favorable ATR volatility environment"
            )
        elif sell_score > buy_score:
            sell_confirmations += 1
            sell_confirmation_details.append(
                "Favorable ATR volatility environment"
            )

    if volume_detected and volume_actionable:
        if volume_direction == "BULLISH":
            buy_confirmations += 1
            buy_confirmation_details.append(
                "Bullish volume confirmation"
            )

        elif volume_direction == "BEARISH":
            sell_confirmations += 1
            sell_confirmation_details.append(
                "Bearish volume confirmation"
            )

    if mitigation_detected and mitigation_actionable:
        if mitigation_direction == "BULLISH":
            buy_score += 15
            buy_reasons.append(
                "Active bullish mitigation block supports the BUY setup"
            )

            if mitigation_inside:
                buy_score += 10
                buy_reasons.append(
                    "Price is inside the bullish mitigation block"
                )
            elif mitigation_near:
                buy_score += 5
                buy_reasons.append(
                    "Price is near the bullish mitigation block"
                )

            if mitigation_retest:
                buy_score += 5
                buy_reasons.append(
                    "Bullish mitigation retest confirmed"
                )

            if mitigation_strength >= 80:
                buy_score += 5
                buy_reasons.append(
                    "Strong bullish mitigation block"
                )

        elif mitigation_direction == "BEARISH":
            sell_score += 15
            sell_reasons.append(
                "Active bearish mitigation block supports the SELL setup"
            )

            if mitigation_inside:
                sell_score += 10
                sell_reasons.append(
                    "Price is inside the bearish mitigation block"
                )
            elif mitigation_near:
                sell_score += 5
                sell_reasons.append(
                    "Price is near the bearish mitigation block"
                )

            if mitigation_retest:
                sell_score += 5
                sell_reasons.append(
                    "Bearish mitigation retest confirmed"
                )

            if mitigation_strength >= 80:
                sell_score += 5
                sell_reasons.append(
                    "Strong bearish mitigation block"
                )

    # ==========================================
    # BREAKER BLOCK SCORING
    # ==========================================
    if mitigation_detected and mitigation_actionable:
        if mitigation_direction == "BULLISH":
            buy_confirmations += 1
            buy_confirmation_details.append(
                "Bullish mitigation block retest"
            )

        elif mitigation_direction == "BEARISH":
            sell_confirmations += 1
            sell_confirmation_details.append(
                "Bearish mitigation block retest"
            )

    if breaker_detected and breaker_actionable:
        if breaker_direction == "BULLISH":
            buy_score += 20
            buy_reasons.append(
                "Active bullish breaker block supports the BUY setup"
            )

            if breaker_inside:
                buy_score += 10
                buy_reasons.append(
                    "Price is inside the bullish breaker block"
                )
            elif breaker_near:
                buy_score += 5
                buy_reasons.append(
                    "Price is near the bullish breaker block"
                )

            if breaker_retest:
                buy_score += 5
                buy_reasons.append(
                    "Bullish breaker retest confirmed"
                )

            if breaker_strength >= 80:
                buy_score += 5
                buy_reasons.append(
                    "Strong bullish breaker block"
                )

        elif breaker_direction == "BEARISH":
            sell_score += 20
            sell_reasons.append(
                "Active bearish breaker block supports the SELL setup"
            )

            if breaker_inside:
                sell_score += 10
                sell_reasons.append(
                    "Price is inside the bearish breaker block"
                )
            elif breaker_near:
                sell_score += 5
                sell_reasons.append(
                    "Price is near the bearish breaker block"
                )

            if breaker_retest:
                sell_score += 5
                sell_reasons.append(
                    "Bearish breaker retest confirmed"
                )

            if breaker_strength >= 80:
                sell_score += 5
                sell_reasons.append(
                    "Strong bearish breaker block"
                )

    # ==========================================
    # EQUAL HIGHS / EQUAL LOWS SCORING
    # ==========================================
    if breaker_detected and breaker_actionable:
        if breaker_direction == "BULLISH":
            buy_confirmations += 1
            buy_confirmation_details.append(
                "Confirmed bullish breaker block proximity"
            )

        elif breaker_direction == "BEARISH":
            sell_confirmations += 1
            sell_confirmation_details.append(
                "Confirmed bearish breaker block proximity"
            )

    if equal_high_low_detected:
        if equal_high_low_type == "EQUAL_HIGHS":
            if equal_high_low_swept:
                sell_score += 15
                sell_reasons.append(
                    "Equal highs were swept, supporting a bearish reversal"
                )
            elif equal_high_low_near:
                sell_score += 5
                sell_reasons.append(
                    "Price is near equal highs and buy-side liquidity"
                )
            elif equal_high_low_breakout:
                buy_score += 5
                buy_reasons.append(
                    "Price broke above equal highs"
                )

            if (
                equal_high_low_strength >= 70
                and (equal_high_low_swept or equal_high_low_near)
            ):
                sell_score += 5
                sell_reasons.append(
                    "Strong equal-high liquidity pool detected"
                )

        elif equal_high_low_type == "EQUAL_LOWS":
            if equal_high_low_swept:
                buy_score += 15
                buy_reasons.append(
                    "Equal lows were swept, supporting a bullish reversal"
                )
            elif equal_high_low_near:
                buy_score += 5
                buy_reasons.append(
                    "Price is near equal lows and sell-side liquidity"
                )
            elif equal_high_low_breakout:
                sell_score += 5
                sell_reasons.append(
                    "Price broke below equal lows"
                )

            if (
                equal_high_low_strength >= 70
                and (equal_high_low_swept or equal_high_low_near)
            ):
                buy_score += 5
                buy_reasons.append(
                    "Strong equal-low liquidity pool detected"
                )

    # ==========================================
    # SUPPLY AND DEMAND SCORING
    # ==========================================
    supply_demand_actionable = (
        supply_demand_detected
        and supply_demand_status == "ACTIVE"
        and supply_demand_relevance in {"INSIDE", "NEAR"}
    )

    if equal_high_low_detected:
        if (
            equal_high_low_type == "EQUAL_HIGHS"
            and equal_high_low_swept
        ):
            sell_confirmations += 1
            sell_confirmation_details.append(
                "Equal highs liquidity sweep"
            )

        elif (
            equal_high_low_type == "EQUAL_LOWS"
            and equal_high_low_swept
        ):
            buy_confirmations += 1
            buy_confirmation_details.append(
                "Equal lows liquidity sweep"
            )

        elif (
            equal_high_low_type == "EQUAL_HIGHS"
            and equal_high_low_near
        ):
            sell_confirmations += 1
            sell_confirmation_details.append(
                "Price near equal highs"
            )

        elif (
            equal_high_low_type == "EQUAL_LOWS"
            and equal_high_low_near
        ):
            buy_confirmations += 1
            buy_confirmation_details.append(
                "Price near equal lows"
            )

    if supply_demand_actionable:
        inside_bonus = 15
        near_bonus = 10
        strength_bonus = 5 if supply_demand_strength >= 2.0 else 0

        if supply_demand_direction == "BULLISH":
            if supply_demand_price_inside:
                buy_score += inside_bonus
                buy_reasons.append(
                    "Price is inside an active demand zone"
                )
            elif supply_demand_price_near:
                buy_score += near_bonus
                buy_reasons.append(
                    "Price is near an active demand zone"
                )

            if strength_bonus:
                buy_score += strength_bonus
                buy_reasons.append(
                    "Strong bullish displacement from demand"
                )

        elif supply_demand_direction == "BEARISH":
            if supply_demand_price_inside:
                sell_score += inside_bonus
                sell_reasons.append(
                    "Price is inside an active supply zone"
                )
            elif supply_demand_price_near:
                sell_score += near_bonus
                sell_reasons.append(
                    "Price is near an active supply zone"
                )

            if strength_bonus:
                sell_score += strength_bonus
                sell_reasons.append(
                    "Strong bearish displacement from supply"
                )

    # ==========================================
    # TRENDLINE SCORING
    # ==========================================
    if trendline_detected:
        if (
            trendline_status == "ACTIVE"
            and trendline_direction == "BULLISH"
        ):
            buy_score += 10
            buy_reasons.append(
                "Active bullish trendline supports the BUY setup"
            )

        elif (
            trendline_status == "ACTIVE"
            and trendline_direction == "BEARISH"
        ):
            sell_score += 10
            sell_reasons.append(
                "Active bearish trendline supports the SELL setup"
            )

        if trendline_break_direction == "BULLISH_BREAK":
            buy_score += 20
            buy_reasons.append(
                "Bullish break above bearish trendline"
            )

            if trendline_retest:
                buy_score += 10
                buy_reasons.append(
                    "Bullish trendline break retest confirmed"
                )

        elif trendline_break_direction == "BEARISH_BREAK":
            sell_score += 20
            sell_reasons.append(
                "Bearish break below bullish trendline"
            )

            if trendline_retest:
                sell_score += 10
                sell_reasons.append(
                    "Bearish trendline break retest confirmed"
                )

    # ==========================================
    # CANDLESTICK PATTERN SCORING
    # ==========================================
    if trendline_detected:
        if (
            trendline_status == "ACTIVE"
            and trendline_direction == "BULLISH"
        ):
            buy_confirmations += 1
            buy_confirmation_details.append(
                "Active bullish trendline"
            )

        elif (
            trendline_status == "ACTIVE"
            and trendline_direction == "BEARISH"
        ):
            sell_confirmations += 1
            sell_confirmation_details.append(
                "Active bearish trendline"
            )

        elif trendline_break_direction == "BULLISH_BREAK":
            buy_confirmations += 1
            buy_confirmation_details.append(
                "Bullish trendline break"
                + (
                    " with retest"
                    if trendline_retest
                    else ""
                )
            )

        elif trendline_break_direction == "BEARISH_BREAK":
            sell_confirmations += 1
            sell_confirmation_details.append(
                "Bearish trendline break"
                + (
                    " with retest"
                    if trendline_retest
                    else ""
                )
            )

    if supply_demand_actionable:
        if supply_demand_direction == "BULLISH":
            buy_confirmations += 1
            buy_confirmation_details.append(
                "Demand zone: "
                + (
                    "price inside"
                    if supply_demand_price_inside
                    else "price near"
                )
            )

        elif supply_demand_direction == "BEARISH":
            sell_confirmations += 1
            sell_confirmation_details.append(
                "Supply zone: "
                + (
                    "price inside"
                    if supply_demand_price_inside
                    else "price near"
                )
            )

    if (
        candlestick_direction == "BULLISH"
        and candlestick_status == "CONFIRMED"
    ):
        buy_score += 15
        buy_reasons.append(
            f"Bullish candlestick pattern detected: {candlestick_pattern}"
        )

        if candlestick_strength >= 85:
            buy_score += 5
            buy_reasons.append(
                "High-strength bullish candlestick confirmation"
            )

    elif (
        candlestick_direction == "BEARISH"
        and candlestick_status == "CONFIRMED"
    ):
        sell_score += 15
        sell_reasons.append(
            f"Bearish candlestick pattern detected: {candlestick_pattern}"
        )

        if candlestick_strength >= 85:
            sell_score += 5
            sell_reasons.append(
                "High-strength bearish candlestick confirmation"
            )

    elif candlestick_direction == "NEUTRAL":
        buy_reasons.append(
            "Neutral candlestick pattern detected with no directional score"
        )
        sell_reasons.append(
            "Neutral candlestick pattern detected with no directional score"
        )

    # ==========================================
    # CONFIRMATION COUNTING
    # ==========================================
    # Each independent module counts only once.

    if trend == "UPTREND":
        buy_confirmations += 1
        buy_confirmation_details.append("Current timeframe trend")

    elif trend == "DOWNTREND":
        sell_confirmations += 1
        sell_confirmation_details.append("Current timeframe trend")

    if structure == "HH-HL":
        buy_confirmations += 1
        buy_confirmation_details.append("Bullish market structure")

    elif structure == "LH-LL":
        sell_confirmations += 1
        sell_confirmation_details.append("Bearish market structure")

    if buy_confirmed:
        buy_confirmations += 1
        buy_confirmation_details.append("Multi-timeframe trend alignment")

    if sell_confirmed:
        sell_confirmations += 1
        sell_confirmation_details.append("Multi-timeframe trend alignment")

    if bos_direction == "BULLISH_BOS":
        buy_confirmations += 1
        buy_confirmation_details.append("Bullish BOS")

    elif bos_direction == "BEARISH_BOS":
        sell_confirmations += 1
        sell_confirmation_details.append("Bearish BOS")

    if choch_direction == "BULLISH_CHOCH":
        buy_confirmations += 1
        buy_confirmation_details.append("Bullish CHoCH")

    elif choch_direction == "BEARISH_CHOCH":
        sell_confirmations += 1
        sell_confirmation_details.append("Bearish CHoCH")

    if (
        order_block_direction == "BULLISH_ORDER_BLOCK"
        and order_block_status == "ACTIVE"
        and (order_block_price_inside or order_block_price_near)
    ):
        buy_confirmations += 1
        buy_confirmation_details.append(
            "Bullish Order Block entry location"
        )

    elif (
        order_block_direction == "BEARISH_ORDER_BLOCK"
        and order_block_status == "ACTIVE"
        and (order_block_price_inside or order_block_price_near)
    ):
        sell_confirmations += 1
        sell_confirmation_details.append(
            "Bearish Order Block entry location"
        )

    if (
        liquidity_direction == "BULLISH_LIQUIDITY_SWEEP"
        and liquidity_status == "CONFIRMED"
    ):
        buy_confirmations += 1
        buy_confirmation_details.append("Bullish liquidity sweep")

    elif (
        liquidity_direction == "BEARISH_LIQUIDITY_SWEEP"
        and liquidity_status == "CONFIRMED"
    ):
        sell_confirmations += 1
        sell_confirmation_details.append("Bearish liquidity sweep")

    if (
        fvg_direction == "BULLISH_FVG"
        and fvg_status == "ACTIVE"
    ):
        buy_confirmations += 1
        buy_confirmation_details.append("Bullish Fair Value Gap")

    elif (
        fvg_direction == "BEARISH_FVG"
        and fvg_status == "ACTIVE"
    ):
        sell_confirmations += 1
        sell_confirmation_details.append("Bearish Fair Value Gap")

    if dealing_zone_status == "ACTIVE":
        if dealing_zone == "DISCOUNT":
            buy_confirmations += 1
            buy_confirmation_details.append("Discount zone")

        elif dealing_zone == "PREMIUM":
            sell_confirmations += 1
            sell_confirmation_details.append("Premium zone")

    if (
        ote_direction == "BULLISH_OTE"
        and ote_status == "ACTIVE"
        and ote_price_inside
    ):
        buy_confirmations += 1
        buy_confirmation_details.append("Bullish OTE")

    elif (
        ote_direction == "BEARISH_OTE"
        and ote_status == "ACTIVE"
        and ote_price_inside
    ):
        sell_confirmations += 1
        sell_confirmation_details.append("Bearish OTE")

    if double_bottom:
        buy_confirmations += 1
        buy_confirmation_details.append("Double Bottom")

    if double_top:
        sell_confirmations += 1
        sell_confirmation_details.append("Double Top")

    if breakout == "BULLISH BREAKOUT":
        buy_confirmations += 1
        buy_confirmation_details.append("Bullish breakout")

    elif breakout == "BEARISH BREAKOUT":
        sell_confirmations += 1
        sell_confirmation_details.append("Bearish breakout")

    if (
        candlestick_direction == "BULLISH"
        and candlestick_status == "CONFIRMED"
    ):
        buy_confirmations += 1
        buy_confirmation_details.append(
            f"Bullish candlestick: {candlestick_pattern}"
        )

    elif (
        candlestick_direction == "BEARISH"
        and candlestick_status == "CONFIRMED"
    ):
        sell_confirmations += 1
        sell_confirmation_details.append(
            f"Bearish candlestick: {candlestick_pattern}"
        )

    # ==========================================
    # EXTRA ALIGNMENT CONFIRMATION
    # ==========================================
    if (
        trend == "UPTREND"
        and buy_confirmed
        and structure == "HH-HL"
        and ema is not None
        and moving_average is not None
        and ema > moving_average
    ):
        buy_score += 15
        buy_reasons.append(
            "Trend, EMA and bullish market structure are aligned"
        )

    if (
        trend == "DOWNTREND"
        and sell_confirmed
        and structure == "LH-LL"
        and ema is not None
        and moving_average is not None
        and ema < moving_average
    ):
        sell_score += 15
        sell_reasons.append(
            "Trend, EMA and bearish market structure are aligned"
        )

    # ==========================================
    # HIGHER-TIMEFRAME CONFLICT PENALTIES
    # ==========================================
    if d1_trend == "DOWNTREND":
        buy_score -= 30
        buy_reasons.append("D1 trend conflicts with a BUY signal")
    elif d1_trend == "UPTREND":
        sell_score -= 30
        sell_reasons.append("D1 trend conflicts with a SELL signal")

    if h4_trend == "DOWNTREND":
        buy_score -= 25
        buy_reasons.append("H4 trend conflicts with a BUY signal")
    elif h4_trend == "UPTREND":
        sell_score -= 25
        sell_reasons.append("H4 trend conflicts with a SELL signal")

    if h1_trend == "DOWNTREND":
        buy_score -= 15
        buy_reasons.append("H1 trend conflicts with a BUY signal")
    elif h1_trend == "UPTREND":
        sell_score -= 15
        sell_reasons.append("H1 trend conflicts with a SELL signal")

    if m30_trend == "DOWNTREND":
        buy_score -= 5
        buy_reasons.append("M30 trend weakens the BUY setup")
    elif m30_trend == "UPTREND":
        sell_score -= 5
        sell_reasons.append("M30 trend weakens the SELL setup")

    # ==========================================
    # LIMIT SCORES
    # ==========================================
    buy_score = max(0, min(100, buy_score))
    sell_score = max(0, min(100, sell_score))

    # ==========================================
    # FINAL SIGNAL
    # ==========================================
    # ==========================================
    # MARKET ALIGNMENT ENGINE
    # ==========================================
    proposed_direction = (
        "BUY"
        if buy_score > sell_score
        else "SELL"
        if sell_score > buy_score
        else "NONE"
    )

    mtf_direction = (
        "UPTREND"
        if buy_confirmed and not sell_confirmed
        else "DOWNTREND"
        if sell_confirmed and not buy_confirmed
        else "NONE"
    )

    alignment = evaluate_market_alignment(
        proposed_direction=proposed_direction,
        trend=trend,
        market_structure=structure,
        bos=bos_direction,
        choch=choch_direction,
        trendline=trendline_break_direction
        if trendline_break_direction != "NONE"
        else trendline_direction,
        fair_value_gap=fvg_direction,
        candlestick=candlestick_direction,
        multi_timeframe=mtf_direction,
    )

    if not isinstance(alignment, Mapping):
        alignment = {
            "proposed_direction": proposed_direction,
            "aligned": False,
            "status": "INVALID_ALIGNMENT_RESPONSE",
            "alignment_score": 0,
            "penalty": 20,
            "supporting_modules": [],
            "conflicting_modules": [],
            "neutral_modules": [],
            "module_directions": {},
        }
    else:
        alignment = dict(alignment)

    # Normalize alignment penalties. Strong alignment must not be penalized.
    alignment_score = max(
        0.0,
        min(
            100.0,
            _safe_float(
                alignment.get(
                    "alignment_score",
                    0,
                ),
                0.0,
            ),
        ),
    )
    if alignment_score >= 75:
        alignment["penalty"] = 0
        alignment["aligned"] = True
        alignment["status"] = "STRONGLY_ALIGNED"
    elif alignment_score >= 65:
        alignment["penalty"] = 5
        alignment["aligned"] = True
        alignment["status"] = "ALIGNED"
    elif alignment_score >= 55:
        alignment["penalty"] = 10
        alignment["aligned"] = False
        alignment["status"] = "MIXED"
    else:
        alignment["penalty"] = 20
        alignment["aligned"] = False
        alignment["status"] = "WEAK_ALIGNMENT"

    raw_buy_score = buy_score
    raw_sell_score = sell_score

    if proposed_direction == "BUY":
        buy_score = apply_alignment_penalty(
            buy_score,
            alignment,
        )

        if alignment.get("penalty", 0) > 0:
            buy_reasons.append(
                "Market alignment penalty applied: "
                f"-{alignment['penalty']} points"
            )

    elif proposed_direction == "SELL":
        sell_score = apply_alignment_penalty(
            sell_score,
            alignment,
        )

        if alignment.get("penalty", 0) > 0:
            sell_reasons.append(
                "Market alignment penalty applied: "
                f"-{alignment['penalty']} points"
            )

    # ==========================================
    # SESSION QUALITY SCORE (MALAYSIA TIME)
    # ==========================================
    # Session timing is supporting evidence only. It cannot create a signal,
    # add confirmations, or bypass alignment and entry-safety validation.
    session_strength = int(
        max(
            0.0,
            min(
                100.0,
                _safe_float(
                    session_analysis.get(
                        "strength",
                        0,
                    ),
                    0.0,
                ),
            ),
        )
    )
    session_trade_environment = str(
        session_analysis.get("trade_environment", "QUIET")
    ).upper()
    session_score_adjustment = 0
    session_score_reason = "No session score adjustment"

    if session_overlap_name == "EUROPEAN_US":
        session_score_adjustment = 5
        session_score_reason = (
            "European-US overlap provides maximum session liquidity"
        )
    elif session_overlap_name == "ASIAN_EUROPEAN":
        session_score_adjustment = 3
        session_score_reason = (
            "Asian-European overlap provides improving session liquidity"
        )
    elif session_primary == "US" and session_actionable:
        session_score_adjustment = 3
        session_score_reason = "US session supports active market conditions"
    elif session_primary == "EUROPEAN" and session_actionable:
        session_score_adjustment = 2
        session_score_reason = (
            "European session supports active market conditions"
        )
    elif session_primary == "ASIAN" and session_actionable:
        if session_strength < 65 or session_trade_environment in {
            "QUIET",
            "LOW",
        }:
            session_score_adjustment = -5
            session_score_reason = (
                "Quiet Asian conditions reduce session confirmation strength"
            )
        else:
            session_score_adjustment = 0
            session_score_reason = (
                "Asian session is active but adds no confidence bonus"
            )
    elif not session_actionable:
        session_score_adjustment = -5
        session_score_reason = (
            "Off-session conditions reduce execution confidence"
        )

    # Apply the session adjustment only to the already-preferred direction.
    if proposed_direction == "BUY" and buy_score > sell_score:
        buy_score = max(0, min(100, buy_score + session_score_adjustment))
        if session_score_adjustment != 0:
            sign = "+" if session_score_adjustment > 0 else ""
            buy_reasons.append(
                f"Session quality adjustment applied: {sign}"
                f"{session_score_adjustment} points - {session_score_reason}"
            )
    elif proposed_direction == "SELL" and sell_score > buy_score:
        sell_score = max(0, min(100, sell_score + session_score_adjustment))
        if session_score_adjustment != 0:
            sign = "+" if session_score_adjustment > 0 else ""
            sell_reasons.append(
                f"Session quality adjustment applied: {sign}"
                f"{session_score_adjustment} points - {session_score_reason}"
            )

    session_analysis["score_adjustment"] = session_score_adjustment
    session_analysis["score_reason"] = session_score_reason
    session_analysis["scoring_policy"] = {
        "EUROPEAN_US": 5,
        "ASIAN_EUROPEAN": 3,
        "US": 3,
        "EUROPEAN": 2,
        "ASIAN": "0 or -5 when quiet",
        "OFF_SESSION": -5,
    }

    # ==========================================
    # MARKET REGIME FILTER
    # ==========================================
    # Regime classification changes confidence quality only. It never adds
    # BUY/SELL confirmations and cannot bypass alignment or entry validation.
    market_regime = analyze_market_regime(
        prices=prices,
        candles=candles,
        trend=trend,
        ema=ema,
        moving_average=moving_average,
        market_structure=market_structure,
        bos=bos,
        choch=choch,
        liquidity_sweep=liquidity,
        candlestick_pattern=candlestick,
        atr_volatility=atr_volatility,
        trendline=trendline,
        breakout=breakout,
        multi_timeframe=multi_tf,
    )

    if not isinstance(market_regime, dict):
        market_regime = {
            "detected": False,
            "status": "ERROR",
            "regime": "UNKNOWN",
            "strength": 0,
            "confidence": 0,
            "confidence_adjustment": 0,
            "trade_allowed": False,
            "recommended_strategy": "NO_TRADE",
            "reason": ["Market regime analysis returned an invalid result"],
        }

    regime_adjustment = int(
        max(
            -5.0,
            min(
                5.0,
                _safe_float(
                    market_regime.get(
                        "confidence_adjustment",
                        0,
                    ),
                    0.0,
                ),
            ),
        )
    )
    regime_name = str(
        market_regime.get(
            "regime",
            "UNKNOWN",
        )
    )
    regime_trade_allowed = _safe_bool(
        market_regime.get(
            "trade_allowed",
            True,
        ),
        default=True,
    )

    if proposed_direction == "BUY" and buy_score > sell_score:
        buy_score = max(0, min(100, buy_score + regime_adjustment))
        if regime_adjustment != 0:
            sign = "+" if regime_adjustment > 0 else ""
            buy_reasons.append(
                f"Market regime adjustment applied: {sign}{regime_adjustment} "
                f"points ({regime_name})"
            )
    elif proposed_direction == "SELL" and sell_score > buy_score:
        sell_score = max(0, min(100, sell_score + regime_adjustment))
        if regime_adjustment != 0:
            sign = "+" if regime_adjustment > 0 else ""
            sell_reasons.append(
                f"Market regime adjustment applied: {sign}{regime_adjustment} "
                f"points ({regime_name})"
            )

    # ==========================================
    # RETEST AND REJECTION CONFIRMATION
    # ==========================================
    # Retest confirmation controls entry timing only. It cannot bypass the
    # market-structure, confidence, alignment, or regime safety gates.
    retest_confirmation = detect_retest_confirmation(
        candles if candles is not None else prices,
        preferred_direction=proposed_direction,
        atr=atr_volatility.get("atr"),
        support=support,
        resistance=resistance,
        bos=bos,
        choch=choch,
        order_block=order_block,
        fair_value_gap=fvg,
        optimal_trade_entry=ote,
        supply_demand=supply_demand,
        breaker_block=breaker_block,
        mitigation_block=mitigation_block,
        lookback=5,
        max_confirmation_age=2,
        max_distance_atr=0.15,
    )

    if not isinstance(retest_confirmation, dict):
        retest_confirmation = {
            "detected": False,
            "confirmed": False,
            "status": "ERROR",
            "direction": proposed_direction,
            "zone_type": "NONE",
            "zone_low": None,
            "zone_high": None,
            "zone_mid": None,
            "touch_index": None,
            "confirmation_index": None,
            "current_price": current_price,
            "rejection_type": "NONE",
            "rejection_strength": 0,
            "freshness_score": 0,
            "candles_since_confirmation": None,
            "max_confirmation_age": 2,
            "max_action_distance": None,
            "distance_to_zone": None,
            "distance_percent": None,
            "reason": ["Retest confirmation returned an invalid result"],
            "candidates_checked": 0,
            "rules": {},
        }

    retest_confirmed = _safe_bool(
        retest_confirmation.get(
            "confirmed",
            False,
        )
    )
    retest_direction = str(
        retest_confirmation.get("direction", "NONE")
    ).upper()

    if retest_confirmed and retest_direction == "BUY":
        buy_confirmations += 1
        buy_confirmation_details.append(
            "Bullish retest and rejection confirmation"
        )
        buy_score = min(100, buy_score + 10)
        buy_reasons.extend(retest_confirmation.get("reason", []))

    elif retest_confirmed and retest_direction == "SELL":
        sell_confirmations += 1
        sell_confirmation_details.append(
            "Bearish retest and rejection confirmation"
        )
        sell_score = min(100, sell_score + 10)
        sell_reasons.extend(retest_confirmation.get("reason", []))

    # ==========================================
    # ENTRY LOCATION VALIDATION
    # ==========================================
    position_percent = premium_discount.get("position_percent")
    atr_value = atr_volatility.get("atr")
    buy_entry_valid = True
    sell_entry_valid = True
    buy_entry_issue = None
    sell_entry_issue = None

    if isinstance(position_percent, (int, float)):
        if position_percent >= 80:
            buy_entry_valid = False
            buy_entry_issue = (
                "BUY entry is too high in the dealing range; wait for a pullback"
            )
        if position_percent <= 20:
            sell_entry_valid = False
            sell_entry_issue = (
                "SELL entry is too low in the dealing range; wait for a retracement"
            )

    if isinstance(atr_value, (int, float)) and atr_value > 0:
        if isinstance(resistance, (int, float)) and current_price >= resistance - (0.25 * atr_value):
            buy_entry_valid = False
            buy_entry_issue = "BUY entry is too close to resistance"
        if isinstance(support, (int, float)) and current_price <= support + (0.25 * atr_value):
            sell_entry_valid = False
            sell_entry_issue = "SELL entry is too close to support"

    # A high-confidence directional setup must still wait for a fresh zone
    # retest and directional rejection before execution.
    if proposed_direction == "BUY" and not (
        retest_confirmed and retest_direction == "BUY"
    ):
        buy_entry_valid = False
        buy_entry_issue = (
            retest_confirmation.get("reason", [None])[0]
            if retest_confirmation.get("reason")
            else "BUY requires a confirmed retest and bullish rejection"
        )

    if proposed_direction == "SELL" and not (
        retest_confirmed and retest_direction == "SELL"
    ):
        sell_entry_valid = False
        sell_entry_issue = (
            retest_confirmation.get("reason", [None])[0]
            if retest_confirmation.get("reason")
            else "SELL requires a confirmed retest and bearish rejection"
        )

    signal = "NO TRADE"
    reasons = []

    minimum_confidence = MINIMUM_SIGNAL_CONFIDENCE
    minimum_confirmations = MINIMUM_SIGNAL_CONFIRMATIONS

    buy_allowed = (
        buy_score > sell_score
        and buy_score >= minimum_confidence
        and buy_confirmations >= minimum_confirmations
        and alignment.get("aligned", False)
        and regime_trade_allowed
        and buy_entry_valid
    )

    sell_allowed = (
        sell_score > buy_score
        and sell_score >= minimum_confidence
        and sell_confirmations >= minimum_confirmations
        and alignment.get("aligned", False)
        and regime_trade_allowed
        and sell_entry_valid
    )

    # ==========================================
    # STRUCTURE CONFIRMATION SAFETY GATE
    # ==========================================
    # A high score, session bonus, market regime bonus, or MTF agreement must
    # never override an opposing market structure without BOS/CHoCH evidence.
    bullish_structure_confirmed = (
        structure == "HH-HL"
        or bos_direction == "BULLISH_BOS"
        or choch_direction == "BULLISH_CHOCH"
    )

    bearish_structure_confirmed = (
        structure == "LH-LL"
        or bos_direction == "BEARISH_BOS"
        or choch_direction == "BEARISH_CHOCH"
    )

    if buy_allowed and not bullish_structure_confirmed:
        buy_allowed = False
        buy_entry_valid = False
        buy_entry_issue = (
            "BUY requires bullish market structure, bullish BOS, "
            "or bullish CHoCH"
        )
        buy_reasons.append(buy_entry_issue)

    if sell_allowed and not bearish_structure_confirmed:
        sell_allowed = False
        sell_entry_valid = False
        sell_entry_issue = (
            "SELL requires bearish market structure, bearish BOS, "
            "or bearish CHoCH"
        )
        sell_reasons.append(sell_entry_issue)

    if buy_allowed:
        signal = "STRONG BUY" if buy_score >= 90 else "BUY"
        reasons = buy_reasons

    elif sell_allowed:
        signal = "STRONG SELL" if sell_score >= 90 else "SELL"
        reasons = sell_reasons

    else:
        reasons = buy_reasons if buy_score >= sell_score else sell_reasons

        preferred_direction = "BUY" if buy_score >= sell_score else "SELL"
        location_issue = (
            buy_entry_issue
            if preferred_direction == "BUY"
            else sell_entry_issue
        )

        if (
            location_issue
            and max(buy_score, sell_score) >= minimum_confidence
            and alignment.get("aligned", False)
        ):
            signal = "WAIT FOR RETEST"
            reasons.append(location_issue)
            reasons.append(
                "No immediate entry: direction is valid but entry location is unsafe"
            )

        stronger_score = max(buy_score, sell_score)
        stronger_confirmations = (
            buy_confirmations
            if buy_score >= sell_score
            else sell_confirmations
        )

        if stronger_score < minimum_confidence:
            reasons.append(
                f"No trade: confidence is below {minimum_confidence}%"
            )

        if stronger_confirmations < minimum_confirmations:
            reasons.append(
                "No trade: fewer than "
                f"{minimum_confirmations} confirmations"
            )

        if not alignment.get("aligned", False):
            reasons.append(
                "No trade: major market modules are not sufficiently aligned"
            )

        if not regime_trade_allowed:
            reasons.append(
                "No trade: market regime does not permit execution "
                f"({regime_name})"
            )

    executable_signals = {"BUY", "STRONG BUY", "SELL", "STRONG SELL"}
    trade_allowed = signal in executable_signals
    directional_confidence = max(buy_score, sell_score)
    confidence = directional_confidence if trade_allowed else 0

    # Remove repeated validation messages while preserving their original order.
    reasons = list(dict.fromkeys(reasons))

    entry = current_price

    # ==========================================
    # DYNAMIC SL/TP ENGINE
    # Global fixed price distances for every symbol:
    # SL = 15.00, TP1 = 10.00, TP2 = 30.00
    # ==========================================
    risk_plan = calculate_fixed_sl_tp(
        entry_price=entry,
        signal=signal,
        trade_allowed=trade_allowed,
    )

    if not isinstance(risk_plan, Mapping):
        risk_plan = {}

    risk_plan = dict(risk_plan)

    required_risk_fields = (
        "stop_loss",
        "take_profit_1",
        "take_profit_2",
        "risk_reward_tp1",
        "risk_reward_tp2",
        "model",
        "calculated",
        "direction",
        "stop_loss_distance",
        "take_profit_1_distance",
        "take_profit_2_distance",
        "reason",
    )

    if any(
        field not in risk_plan
        for field in required_risk_fields
    ):
        trade_allowed = False
        signal = "NO TRADE"
        confidence = 0
        reasons.append(
            "No trade: risk-management engine returned an incomplete plan"
        )

        risk_plan = {
            "stop_loss": None,
            "take_profit_1": None,
            "take_profit_2": None,
            "risk_reward_tp1": None,
            "risk_reward_tp2": None,
            "model": "UNAVAILABLE",
            "calculated": False,
            "direction": "NONE",
            "stop_loss_distance": None,
            "take_profit_1_distance": None,
            "take_profit_2_distance": None,
            "reason": "Risk-management plan unavailable.",
        }

    stop_loss = risk_plan["stop_loss"]
    take_profit_1 = risk_plan["take_profit_1"]
    take_profit_2 = risk_plan["take_profit_2"]
    risk_tp1 = risk_plan["risk_reward_tp1"]
    risk_tp2 = risk_plan["risk_reward_tp2"]

    # ==========================================
    # TRADE QUALITY ENGINE â€” SAFETY VERSION 7
    # Descriptive only: it cannot override the Signal Engine.
    # ==========================================
    preferred_direction = "BUY" if buy_score >= sell_score else "SELL"

    selected_confirmations = (
        buy_confirmations
        if preferred_direction == "BUY"
        else sell_confirmations
    )

    selected_entry_valid = (
        buy_entry_valid
        if preferred_direction == "BUY"
        else sell_entry_valid
    )

    selected_structure_confirmed = (
        bullish_structure_confirmed
        if preferred_direction == "BUY"
        else bearish_structure_confirmed
    )

    trade_quality = evaluate_trade_quality(
        signal=signal,
        trade_allowed=trade_allowed,
        confidence=confidence,
        directional_confidence=directional_confidence,
        confirmations=selected_confirmations,
        minimum_confirmations=minimum_confirmations,
        alignment=alignment,
        market_regime={
            **market_regime,
            "trade_allowed": regime_trade_allowed,
        },
        retest_confirmation=retest_confirmation,
        entry_valid=selected_entry_valid,
        structure_confirmed=selected_structure_confirmed,
        atr_volatility=atr_volatility,
        session_analysis=session_analysis,
        risk_plan=risk_plan,
    )

    if not isinstance(trade_quality, Mapping):
        trade_quality = {
            "score": 0,
            "grade": "UNRATED",
            "status": "UNAVAILABLE",
            "reason": [
                "Trade-quality engine returned an invalid response."
            ],
        }
    else:
        trade_quality = dict(trade_quality)

    # Final safety enforcement. Supporting modules cannot turn a blocked
    # setup into an executable signal.
    trade_allowed = bool(
        trade_allowed
        and signal in executable_signals
        and confidence >= minimum_confidence
        and selected_confirmations >= minimum_confirmations
        and selected_entry_valid
        and selected_structure_confirmed
        and _safe_bool(
            alignment.get(
                "aligned",
                False,
            )
        )
        and regime_trade_allowed
    )

    if not trade_allowed:
        signal = (
            signal
            if signal == "WAIT FOR RETEST"
            else "NO TRADE"
        )
        confidence = 0

    # ==========================================
    # RETURN RESULT
    # ==========================================
    return {
        "engine_version": ENGINE_VERSION,
        "symbol": symbol,
        "signal": signal,
        "trade_allowed": trade_allowed,
        "confidence": confidence,
        "directional_confidence": directional_confidence,
        "market_price": format_price(current_price, symbol),
        "entry_price": format_price(entry, symbol),
        "stop_loss": stop_loss,
        "take_profit_1": take_profit_1,
        "take_profit_2": take_profit_2,
        "risk_management": {
            "model": risk_plan["model"],
            "calculated": risk_plan["calculated"],
            "direction": risk_plan["direction"],
            "stop_loss_distance": risk_plan["stop_loss_distance"],
            "take_profit_1_distance": risk_plan["take_profit_1_distance"],
            "take_profit_2_distance": risk_plan["take_profit_2_distance"],
            "TP1": risk_tp1,
            "TP2": risk_tp2,
            "reason": risk_plan["reason"],
        },
        "trade_quality": trade_quality,
        "reason": reasons,
        "scores": {
            "raw_buy": raw_buy_score,
            "raw_sell": raw_sell_score,
            "buy": buy_score,
            "sell": sell_score,
        },
        "market_regime": {
            "detected": market_regime.get("detected", False),
            "status": market_regime.get("status", "UNKNOWN"),
            "regime": market_regime.get("regime", "UNKNOWN"),
            "strength": market_regime.get("strength", 0),
            "confidence": market_regime.get("confidence", 0),
            "confidence_adjustment": regime_adjustment,
            "trade_allowed": regime_trade_allowed,
            "recommended_strategy": market_regime.get(
                "recommended_strategy", "NO_TRADE"
            ),
            "reason": market_regime.get("reason", []),
            "metrics": market_regime.get("metrics", {}),
            "rules": market_regime.get("rules", {}),
            "scoring_policy": market_regime.get("scoring_policy", {}),
        },
        "market_alignment": {
            "proposed_direction": alignment.get(
                "proposed_direction",
                "NONE",
            ),
            "aligned": alignment.get("aligned", False),
            "status": alignment.get("status", "NO_DIRECTION"),
            "alignment_score": alignment.get(
                "alignment_score",
                0,
            ),
            "penalty": alignment.get("penalty", 0),
            "supporting_modules": alignment.get(
                "supporting_modules",
                [],
            ),
            "conflicting_modules": alignment.get(
                "conflicting_modules",
                [],
            ),
            "neutral_modules": alignment.get(
                "neutral_modules",
                [],
            ),
            "module_directions": alignment.get(
                "module_directions",
                {},
            ),
        },
        "retest_confirmation": {
            "detected": retest_confirmation.get("detected", False),
            "confirmed": retest_confirmed,
            "status": retest_confirmation.get("status", "NO_RETEST"),
            "direction": retest_direction,
            "zone_type": retest_confirmation.get("zone_type", "NONE"),
            "zone_low": (
                format_price(retest_confirmation.get("zone_low"), symbol)
                if retest_confirmation.get("zone_low") is not None
                else None
            ),
            "zone_high": (
                format_price(retest_confirmation.get("zone_high"), symbol)
                if retest_confirmation.get("zone_high") is not None
                else None
            ),
            "zone_mid": (
                format_price(retest_confirmation.get("zone_mid"), symbol)
                if retest_confirmation.get("zone_mid") is not None
                else None
            ),
            "touch_index": retest_confirmation.get("touch_index"),
            "confirmation_index": retest_confirmation.get(
                "confirmation_index"
            ),
            "current_price": (
                format_price(
                    retest_confirmation.get("current_price"),
                    symbol,
                )
                if retest_confirmation.get("current_price") is not None
                else format_price(current_price, symbol)
            ),
            "rejection_type": retest_confirmation.get(
                "rejection_type",
                "NONE",
            ),
            "rejection_strength": retest_confirmation.get(
                "rejection_strength",
                0,
            ),
            "freshness_score": retest_confirmation.get("freshness_score", 0),
            "candles_since_confirmation": retest_confirmation.get(
                "candles_since_confirmation"
            ),
            "max_confirmation_age": retest_confirmation.get(
                "max_confirmation_age", 2
            ),
            "max_action_distance": retest_confirmation.get(
                "max_action_distance"
            ),
            "distance_to_zone": retest_confirmation.get(
                "distance_to_zone"
            ),
            "distance_percent": retest_confirmation.get(
                "distance_percent"
            ),
            "reason": retest_confirmation.get("reason", []),
            "candidates_checked": retest_confirmation.get(
                "candidates_checked",
                0,
            ),
            "rules": retest_confirmation.get("rules", {}),
        },
        "entry_validation": {
            "status": (
                "VALID"
                if (
                    (buy_score >= sell_score and buy_entry_valid)
                    or (sell_score > buy_score and sell_entry_valid)
                )
                else "WAIT_FOR_RETEST"
            ),
            "preferred_direction": (
                "BUY" if buy_score >= sell_score else "SELL"
            ),
            "buy_entry_valid": buy_entry_valid,
            "sell_entry_valid": sell_entry_valid,
            "buy_issue": buy_entry_issue,
            "sell_issue": sell_entry_issue,
            "position_percent": position_percent,
            "near_support": (
                isinstance(atr_value, (int, float))
                and isinstance(support, (int, float))
                and current_price <= support + (0.25 * atr_value)
            ),
            "near_resistance": (
                isinstance(atr_value, (int, float))
                and isinstance(resistance, (int, float))
                and current_price >= resistance - (0.25 * atr_value)
            ),
        },
        "validation": {
            "minimum_confidence": minimum_confidence,
            "minimum_confirmations": minimum_confirmations,
            "buy_confirmations": buy_confirmations,
            "sell_confirmations": sell_confirmations,
            "buy_confirmation_details": buy_confirmation_details,
            "sell_confirmation_details": sell_confirmation_details,
            "buy_allowed": buy_allowed,
            "sell_allowed": sell_allowed,
            "bullish_structure_confirmed": bullish_structure_confirmed,
            "bearish_structure_confirmed": bearish_structure_confirmed,
        },
        "market_structure": {
            "structure": structure,
            "trend": market_structure.get("trend", "RANGE"),
            "bullish": structure == "HH-HL",
            "bearish": structure == "LH-LL",
            "last_high": market_structure.get("last_high"),
            "previous_high": market_structure.get("previous_high"),
            "last_low": market_structure.get("last_low"),
            "previous_low": market_structure.get("previous_low"),
        },
        "bos": {
            "detected": bos.get("detected", False),
            "direction": bos.get("direction", "NONE"),
            "level": (
                format_price(bos.get("level"), symbol)
                if bos.get("level") is not None
                else None
            ),
            "break_price": (
                format_price(bos.get("break_price"), symbol)
                if bos.get("break_price") is not None
                else None
            ),
            "distance": bos.get("distance"),
            "previous_structure": bos.get(
                "previous_structure",
                structure,
            ),
        },
        "choch": {
            "detected": choch.get("detected", False),
            "direction": choch.get("direction", "NONE"),
            "level": (
                format_price(choch.get("level"), symbol)
                if choch.get("level") is not None
                else None
            ),
            "break_price": (
                format_price(choch.get("break_price"), symbol)
                if choch.get("break_price") is not None
                else None
            ),
            "distance": choch.get("distance"),
            "previous_structure": choch.get(
                "previous_structure",
                structure,
            ),
        },
        "order_block": {
            "detected": order_block.get("detected", False),
            "direction": order_block.get("direction", "NONE"),
            "status": order_block.get("status", "NO_ORDER_BLOCK"),
            "zone_high": (
                format_price(order_block.get("zone_high"), symbol)
                if order_block.get("zone_high") is not None
                else None
            ),
            "zone_low": (
                format_price(order_block.get("zone_low"), symbol)
                if order_block.get("zone_low") is not None
                else None
            ),
            "candle_index": order_block.get("candle_index"),
            "impulse_strength": order_block.get("impulse_strength"),
            "mitigated": order_block.get("mitigated", False),
            "current_price": (
                format_price(order_block.get("current_price"), symbol)
                if order_block.get("current_price") is not None
                else format_price(current_price, symbol)
            ),
        },
        "liquidity_sweep": {
            "detected": liquidity.get("detected", False),
            "direction": liquidity.get("direction", "NONE"),
            "status": liquidity.get(
                "status",
                "NO_LIQUIDITY_SWEEP",
            ),
            "level": (
                format_price(liquidity.get("level"), symbol)
                if liquidity.get("level") is not None
                else None
            ),
            "sweep_price": (
                format_price(liquidity.get("sweep_price"), symbol)
                if liquidity.get("sweep_price") is not None
                else None
            ),
            "close_price": (
                format_price(liquidity.get("close_price"), symbol)
                if liquidity.get("close_price") is not None
                else format_price(current_price, symbol)
            ),
            "distance": liquidity.get("distance"),
            "candle_index": liquidity.get("candle_index"),
            "liquidity_candle_index": liquidity.get(
                "liquidity_candle_index"
            ),
        },
        "fair_value_gap": {
            "detected": fvg.get("detected", False),
            "direction": fvg.get("direction", "NONE"),
            "status": fvg.get("status", "NO_FVG"),
            "zone_high": (
                format_price(fvg.get("zone_high"), symbol)
                if fvg.get("zone_high") is not None
                else None
            ),
            "zone_low": (
                format_price(fvg.get("zone_low"), symbol)
                if fvg.get("zone_low") is not None
                else None
            ),
            "gap_size": fvg.get("gap_size"),
            "candle_index": fvg.get("candle_index"),
            "filled": fvg.get("filled", False),
            "price_inside_zone": fvg.get(
                "price_inside_zone",
                False,
            ),
            "current_price": (
                format_price(fvg.get("current_price"), symbol)
                if fvg.get("current_price") is not None
                else format_price(current_price, symbol)
            ),
        },
        "premium_discount": {
            "detected": premium_discount.get("detected", False),
            "status": premium_discount.get("status", "NO_RANGE"),
            "zone": premium_discount.get("zone", "NONE"),
            "swing_high": (
                format_price(
                    premium_discount.get("swing_high"),
                    symbol,
                )
                if premium_discount.get("swing_high") is not None
                else None
            ),
            "swing_low": (
                format_price(
                    premium_discount.get("swing_low"),
                    symbol,
                )
                if premium_discount.get("swing_low") is not None
                else None
            ),
            "equilibrium": (
                format_price(
                    premium_discount.get("equilibrium"),
                    symbol,
                )
                if premium_discount.get("equilibrium") is not None
                else None
            ),
            "premium_start": (
                format_price(
                    premium_discount.get("premium_start"),
                    symbol,
                )
                if premium_discount.get("premium_start") is not None
                else None
            ),
            "discount_end": (
                format_price(
                    premium_discount.get("discount_end"),
                    symbol,
                )
                if premium_discount.get("discount_end") is not None
                else None
            ),
            "current_price": (
                format_price(
                    premium_discount.get("current_price"),
                    symbol,
                )
                if premium_discount.get("current_price") is not None
                else format_price(current_price, symbol)
            ),
            "range_size": premium_discount.get("range_size"),
            "position_percent": premium_discount.get(
                "position_percent"
            ),
            "high_index": premium_discount.get("high_index"),
            "low_index": premium_discount.get("low_index"),
        },
        "optimal_trade_entry": {
            "detected": ote.get("detected", False),
            "status": ote.get("status", "NO_OTE"),
            "direction": ote.get("direction", "NONE"),
            "range_direction": ote.get(
                "range_direction",
                "NONE",
            ),
            "swing_high": (
                format_price(ote.get("swing_high"), symbol)
                if ote.get("swing_high") is not None
                else None
            ),
            "swing_low": (
                format_price(ote.get("swing_low"), symbol)
                if ote.get("swing_low") is not None
                else None
            ),
            "ote_zone_high": (
                format_price(ote.get("ote_zone_high"), symbol)
                if ote.get("ote_zone_high") is not None
                else None
            ),
            "ote_zone_low": (
                format_price(ote.get("ote_zone_low"), symbol)
                if ote.get("ote_zone_low") is not None
                else None
            ),
            "fib_62": (
                format_price(ote.get("fib_62"), symbol)
                if ote.get("fib_62") is not None
                else None
            ),
            "fib_705": (
                format_price(ote.get("fib_705"), symbol)
                if ote.get("fib_705") is not None
                else None
            ),
            "fib_79": (
                format_price(ote.get("fib_79"), symbol)
                if ote.get("fib_79") is not None
                else None
            ),
            "current_price": (
                format_price(ote.get("current_price"), symbol)
                if ote.get("current_price") is not None
                else format_price(current_price, symbol)
            ),
            "price_inside_zone": ote.get(
                "price_inside_zone",
                False,
            ),
            "position_percent": ote.get("position_percent"),
            "high_index": ote.get("high_index"),
            "low_index": ote.get("low_index"),
        },
        "session_analysis": {
            "detected": session_analysis.get("detected", False),
            "status": session_analysis.get("status", "OFF_SESSION"),
            "time_source": session_analysis.get("time_source"),
            "timezone": session_analysis.get(
                "timezone", "Asia/Kuala_Lumpur"
            ),
            "timezone_abbreviation": session_analysis.get(
                "timezone_abbreviation", "MYT"
            ),
            "utc_offset": session_analysis.get("utc_offset", "+08:00"),
            "market_time_utc": session_analysis.get("market_time_utc"),
            "market_time_malaysia": session_analysis.get(
                "market_time_malaysia"
            ),
            "market_date_malaysia": session_analysis.get(
                "market_date_malaysia"
            ),
            "market_clock_malaysia": session_analysis.get(
                "market_clock_malaysia"
            ),
            "current_session": session_primary,
            "primary_session": session_primary,
            "active_sessions": session_analysis.get(
                "active_sessions", []
            ),
            "overlap": session_in_overlap,
            "overlap_name": session_overlap_name,
            "session_overlaps": session_analysis.get(
                "session_overlaps", []
            ),
            "kill_zones": session_analysis.get("kill_zones", []),
            "in_kill_zone": session_in_kill_zone,
            "in_session_overlap": session_in_overlap,
            "liquidity": session_liquidity,
            "volatility": session_volatility,
            "trade_environment": session_analysis.get(
                "trade_environment", "QUIET"
            ),
            "strength": session_analysis.get("strength", 0),
            "actionable": session_actionable,
            "score_adjustment": session_analysis.get("score_adjustment", 0),
            "score_reason": session_analysis.get(
                "score_reason", "No session score adjustment"
            ),
            "scoring_policy": session_analysis.get("scoring_policy", {}),
            "session_windows_malaysia": session_analysis.get(
                "session_windows_malaysia", {}
            ),
            "overlap_windows_malaysia": session_analysis.get(
                "overlap_windows_malaysia", {}
            ),
        },
        "atr_volatility": {
            "detected": atr_volatility.get("detected", False),
            "status": atr_volatility.get(
                "status",
                "INSUFFICIENT_DATA",
            ),
            "atr": atr_volatility.get("atr"),
            "atr_percent": atr_volatility.get("atr_percent"),
            "volatility": atr_volatility.get(
                "volatility",
                "UNKNOWN",
            ),
            "trade_environment": atr_volatility.get(
                "trade_environment",
                "UNKNOWN",
            ),
            "too_low": atr_volatility.get("too_low", False),
            "too_high": atr_volatility.get("too_high", False),
            "normal": atr_volatility.get("normal", False),
            "strength": atr_volatility.get("strength", 0),
            "actionable": atr_volatility.get(
                "actionable",
                False,
            ),
        },
        "volume_confirmation": {
            "detected": volume_confirmation.get("detected", False),
            "status": volume_confirmation.get(
                "status",
                "NO_VOLUME_DATA",
            ),
            "direction": volume_confirmation.get(
                "direction",
                "NONE",
            ),
            "current_volume": volume_confirmation.get(
                "current_volume",
            ),
            "average_volume": volume_confirmation.get(
                "average_volume",
            ),
            "volume_ratio": volume_confirmation.get(
                "volume_ratio",
            ),
            "relative_volume": volume_confirmation.get(
                "relative_volume",
            ),
            "volume_trend": volume_confirmation.get(
                "volume_trend",
                "NONE",
            ),
            "price_direction": volume_confirmation.get(
                "price_direction",
                "NONE",
            ),
            "bullish_confirmation": volume_confirmation.get(
                "bullish_confirmation",
                False,
            ),
            "bearish_confirmation": volume_confirmation.get(
                "bearish_confirmation",
                False,
            ),
            "climax": volume_confirmation.get("climax", False),
            "divergence": volume_confirmation.get(
                "divergence",
                False,
            ),
            "strength": volume_confirmation.get("strength", 0),
            "actionable": volume_confirmation.get(
                "actionable",
                False,
            ),
        },
        "mitigation_block": {
            "detected": mitigation_block.get("detected", False),
            "status": mitigation_block.get(
                "status",
                "NO_MITIGATION_BLOCK",
            ),
            "direction": mitigation_block.get("direction", "NONE"),
            "zone_high": (
                format_price(mitigation_block.get("zone_high"), symbol)
                if mitigation_block.get("zone_high") is not None
                else None
            ),
            "zone_low": (
                format_price(mitigation_block.get("zone_low"), symbol)
                if mitigation_block.get("zone_low") is not None
                else None
            ),
            "source_index": mitigation_block.get("source_index"),
            "impulse_index": mitigation_block.get("impulse_index"),
            "retest_index": mitigation_block.get("retest_index"),
            "current_price": (
                format_price(
                    mitigation_block.get("current_price"),
                    symbol,
                )
                if mitigation_block.get("current_price") is not None
                else format_price(current_price, symbol)
            ),
            "price_inside_zone": mitigation_block.get(
                "price_inside_zone",
                False,
            ),
            "price_near_zone": mitigation_block.get(
                "price_near_zone",
                False,
            ),
            "near_tolerance": (
                round(mitigation_block.get("near_tolerance"), 6)
                if mitigation_block.get("near_tolerance") is not None
                else None
            ),
            "retest": mitigation_block.get("retest", False),
            "mitigated": mitigation_block.get("mitigated", False),
            "bos_confirmed": mitigation_block.get(
                "bos_confirmed",
                False,
            ),
            "choch_confirmed": mitigation_block.get(
                "choch_confirmed",
                False,
            ),
            "distance_to_zone": (
                round(mitigation_block.get("distance_to_zone"), 6)
                if mitigation_block.get("distance_to_zone") is not None
                else None
            ),
            "distance_percent": mitigation_block.get(
                "distance_percent",
            ),
            "impulse_strength": mitigation_block.get(
                "impulse_strength",
                0,
            ),
            "strength": mitigation_block.get("strength", 0),
            "actionable": mitigation_block.get("actionable", False),
        },
        "breaker_block": {
            "detected": breaker_block.get("detected", False),
            "status": breaker_block.get(
                "status",
                "NO_BREAKER_BLOCK",
            ),
            "direction": breaker_block.get("direction", "NONE"),
            "zone_high": (
                format_price(breaker_block.get("zone_high"), symbol)
                if breaker_block.get("zone_high") is not None
                else None
            ),
            "zone_low": (
                format_price(breaker_block.get("zone_low"), symbol)
                if breaker_block.get("zone_low") is not None
                else None
            ),
            "source_index": breaker_block.get("source_index"),
            "break_index": breaker_block.get("break_index"),
            "retest_index": breaker_block.get("retest_index"),
            "current_price": (
                format_price(
                    breaker_block.get("current_price"),
                    symbol,
                )
                if breaker_block.get("current_price") is not None
                else format_price(current_price, symbol)
            ),
            "price_inside_zone": breaker_block.get(
                "price_inside_zone",
                False,
            ),
            "price_near_zone": breaker_block.get(
                "price_near_zone",
                False,
            ),
            "near_tolerance": (
                round(breaker_block.get("near_tolerance"), 6)
                if breaker_block.get("near_tolerance") is not None
                else None
            ),
            "retest": breaker_block.get("retest", False),
            "mitigated": breaker_block.get("mitigated", False),
            "bos_confirmed": breaker_block.get(
                "bos_confirmed",
                False,
            ),
            "choch_confirmed": breaker_block.get(
                "choch_confirmed",
                False,
            ),
            "distance_to_zone": (
                round(breaker_block.get("distance_to_zone"), 6)
                if breaker_block.get("distance_to_zone") is not None
                else None
            ),
            "distance_percent": breaker_block.get(
                "distance_percent",
            ),
            "strength": breaker_block.get("strength", 0),
            "actionable": breaker_block.get("actionable", False),
        },
        "equal_high_low": {
            "detected": equal_high_low.get("detected", False),
            "status": equal_high_low.get(
                "status",
                "NO_LIQUIDITY_POOL",
            ),
            "type": equal_high_low.get("type", "NONE"),
            "direction": equal_high_low.get("direction", "NONE"),
            "level": (
                format_price(equal_high_low.get("level"), symbol)
                if equal_high_low.get("level") is not None
                else None
            ),
            "first_index": equal_high_low.get("first_index"),
            "second_index": equal_high_low.get("second_index"),
            "touches": equal_high_low.get("touches", 0),
            "tolerance": (
                round(equal_high_low.get("tolerance"), 6)
                if equal_high_low.get("tolerance") is not None
                else None
            ),
            "distance_to_level": (
                round(equal_high_low.get("distance_to_level"), 6)
                if equal_high_low.get("distance_to_level") is not None
                else None
            ),
            "distance_percent": equal_high_low.get(
                "distance_percent",
            ),
            "current_price": (
                format_price(
                    equal_high_low.get("current_price"),
                    symbol,
                )
                if equal_high_low.get("current_price") is not None
                else format_price(current_price, symbol)
            ),
            "price_near_level": equal_high_low.get(
                "price_near_level",
                False,
            ),
            "swept": equal_high_low.get("swept", False),
            "breakout": equal_high_low.get("breakout", False),
            "strength": equal_high_low.get("strength", 0),
        },
        "supply_demand": {
            "detected": supply_demand.get("detected", False),
            "status": supply_demand.get("status", "NO_ZONE"),
            "direction": supply_demand.get("direction", "NONE"),
            "zone_type": supply_demand.get("zone_type", "NONE"),
            "zone_high": (
                format_price(supply_demand.get("zone_high"), symbol)
                if supply_demand.get("zone_high") is not None else None
            ),
            "zone_low": (
                format_price(supply_demand.get("zone_low"), symbol)
                if supply_demand.get("zone_low") is not None else None
            ),
            "candle_index": supply_demand.get("candle_index"),
            "impulse_index": supply_demand.get("impulse_index"),
            "impulse_strength": supply_demand.get("impulse_strength", 0),
            "current_price": (
                format_price(supply_demand.get("current_price"), symbol)
                if supply_demand.get("current_price") is not None
                else format_price(current_price, symbol)
            ),
            "price_inside_zone": supply_demand.get(
                "price_inside_zone",
                False,
            ),
            "price_near_zone": supply_demand.get(
                "price_near_zone",
                False,
            ),
            "near_tolerance": (
                round(supply_demand.get("near_tolerance"), 6)
                if supply_demand.get("near_tolerance") is not None
                else None
            ),
            "mitigated": supply_demand.get("mitigated", False),
            "distance_to_zone": (
                round(supply_demand.get("distance_to_zone"), 6)
                if supply_demand.get("distance_to_zone") is not None
                else None
            ),
            "distance_percent": supply_demand.get(
                "distance_percent",
            ),
            "relevance": supply_demand.get(
                "relevance",
                "NONE",
            ),
            "actionable": supply_demand_actionable,
        },
        "trendline": {
            "detected": trendline.get("detected", False),
            "status": trendline.get("status", "NO_TRENDLINE"),
            "direction": trendline.get("direction", "NONE"),
            "trendline_type": trendline.get(
                "trendline_type",
                "NONE",
            ),
            "slope": (
                round(trendline.get("slope"), 6)
                if trendline.get("slope") is not None
                else None
            ),
            "start_index": trendline.get("start_index"),
            "end_index": trendline.get("end_index"),
            "start_price": (
                format_price(
                    trendline.get("start_price"),
                    symbol,
                )
                if trendline.get("start_price") is not None
                else None
            ),
            "end_price": (
                format_price(
                    trendline.get("end_price"),
                    symbol,
                )
                if trendline.get("end_price") is not None
                else None
            ),
            "projected_price": (
                format_price(
                    trendline.get("projected_price"),
                    symbol,
                )
                if trendline.get("projected_price") is not None
                else None
            ),
            "current_price": (
                format_price(
                    trendline.get("current_price"),
                    symbol,
                )
                if trendline.get("current_price") is not None
                else format_price(current_price, symbol)
            ),
            "break_detected": trendline.get(
                "break_detected",
                False,
            ),
            "break_direction": trendline.get(
                "break_direction",
                "NONE",
            ),
            "retest_detected": trendline.get(
                "retest_detected",
                False,
            ),
            "distance_to_trendline": (
                round(
                    trendline.get("distance_to_trendline"),
                    6,
                )
                if trendline.get("distance_to_trendline")
                is not None
                else None
            ),
        },
        "candlestick_pattern": {
            "detected": candlestick.get("detected", False),
            "status": candlestick.get("status", "NO_PATTERN"),
            "direction": candlestick.get("direction", "NONE"),
            "pattern": candlestick.get("pattern", "NONE"),
            "strength": candlestick.get("strength", 0),
            "candle_index": candlestick.get("candle_index"),
            "confirmation_index": candlestick.get(
                "confirmation_index"
            ),
            "current_price": (
                format_price(
                    candlestick.get("current_price"),
                    symbol,
                )
                if candlestick.get("current_price") is not None
                else format_price(current_price, symbol)
            ),
        },
        "chart_pattern": {
            "double_bottom": double_bottom,
            "double_top": double_top,
            "breakout": breakout,
        },
        "trend": trend,
        "rsi": round(rsi, 2) if rsi is not None else None,
        "moving_average": (
            format_price(moving_average, symbol)
            if moving_average is not None
            else None
        ),
        "ema": (
            format_price(ema, symbol)
            if ema is not None
            else None
        ),
        "support": (
            format_price(support, symbol)
            if support is not None
            else None
        ),
        "resistance": (
            format_price(resistance, symbol)
            if resistance is not None
            else None
        ),
        "multi_timeframe": multi_tf,
    }


__all__ = [
    "ENGINE_VERSION",
    "MAXIMUM_CANDLES",
    "MAXIMUM_PRICE_POINTS",
    "MAXIMUM_SYMBOL_LENGTH",
    "MINIMUM_SIGNAL_CONFIDENCE",
    "MINIMUM_SIGNAL_CONFIRMATIONS",
    "generate_signal",
]