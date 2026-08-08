from app.trading.analysis import analyze_market

from app.trading.risk import (
    calculate_stop_loss,
    calculate_take_profit_1,
    calculate_take_profit_2,
    calculate_risk_reward
)



def generate_signal(
    symbol: str,
    prices: list
):

    analysis = analyze_market(
        symbol,
        prices
    )


    if "error" in analysis:

        return analysis



    current_price = prices[-1]


    trend = analysis["trend"]

    rsi = analysis["rsi"]

    support = analysis["support"]

    resistance = analysis["resistance"]

    moving_average = analysis.get(
        "moving_average"
    )

    ema = analysis.get(
        "ema"
    )



    signal = "NO TRADE"

    confidence = 0



    # =========================
    # BUY ANALYSIS
    # =========================

    if trend == "UPTREND":

        confidence += 30



    if rsi and 50 <= rsi < 70:

        confidence += 20



    if ema and moving_average:

        if ema > moving_average:

            confidence += 20



    if current_price > support:

        confidence += 15





    # =========================
    # SELL ANALYSIS
    # =========================

    sell_confidence = 0



    if trend == "DOWNTREND":

        sell_confidence += 30



    if rsi and 30 < rsi <= 50:

        sell_confidence += 20



    if ema and moving_average:

        if ema < moving_average:

            sell_confidence += 20



    if current_price < resistance:

        sell_confidence += 15





    # =========================
    # FINAL SIGNAL
    # =========================

    if confidence >= 80:

        signal = "STRONG BUY"



    elif confidence >= 60:

        signal = "BUY"



    elif sell_confidence >= 80:

        signal = "STRONG SELL"

        confidence = sell_confidence



    elif sell_confidence >= 60:

        signal = "SELL"

        confidence = sell_confidence



    else:

        signal = "NO TRADE"

        confidence = max(
            confidence,
            sell_confidence
        )




    entry = current_price



    # =========================
    # RISK MANAGEMENT
    # =========================

    if signal != "NO TRADE":


        direction = (
            "BUY"
            if "BUY" in signal
            else "SELL"
        )



        stop_loss = calculate_stop_loss(
            entry,
            direction,
            pips=150,
            symbol=symbol
        )



        take_profit_1 = calculate_take_profit_1(
            entry,
            direction,
            pips=100,
            symbol=symbol
        )



        take_profit_2 = calculate_take_profit_2(
            entry,
            direction,
            pips=300,
            symbol=symbol
        )



        risk_tp1 = calculate_risk_reward(
            entry,
            stop_loss,
            take_profit_1
        )



        risk_tp2 = calculate_risk_reward(
            entry,
            stop_loss,
            take_profit_2
        )



    else:


        stop_loss = None

        take_profit_1 = None

        take_profit_2 = None


        risk_tp1 = None

        risk_tp2 = None





    return {


        "symbol": symbol,


        "signal": signal,


        "confidence": confidence,


        "entry_price": round(
            entry,
            5
        ),



        "stop_loss": stop_loss,


        "take_profit_1": take_profit_1,


        "take_profit_2": take_profit_2,



        "risk_management": {

            "tp1": risk_tp1,

            "tp2": risk_tp2

        },


        "trend": trend,


        "rsi": rsi,


        "moving_average": moving_average,


        "ema": ema,


        "support": support,


        "resistance": resistance

    }