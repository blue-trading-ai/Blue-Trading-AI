def bullish_engulfing(candles):

    if len(candles) < 2:
        return False

    prev = candles[-2]
    curr = candles[-1]

    prev_open = float(prev["open"])
    prev_close = float(prev["close"])

    curr_open = float(curr["open"])
    curr_close = float(curr["close"])

    return (
        prev_close < prev_open
        and curr_close > curr_open
        and curr_open <= prev_close
        and curr_close >= prev_open
    )


def bearish_engulfing(candles):

    if len(candles) < 2:
        return False

    prev = candles[-2]
    curr = candles[-1]

    prev_open = float(prev["open"])
    prev_close = float(prev["close"])

    curr_open = float(curr["open"])
    curr_close = float(curr["close"])

    return (
        prev_close > prev_open
        and curr_close < curr_open
        and curr_open >= prev_close
        and curr_close <= prev_open
    )


def hammer(candle):

    high = float(candle["high"])
    low = float(candle["low"])
    open_price = float(candle["open"])
    close = float(candle["close"])

    body = abs(close - open_price)

    lower_shadow = min(open_price, close) - low
    upper_shadow = high - max(open_price, close)

    return (
        lower_shadow > body * 2
        and upper_shadow < body
    )


def shooting_star(candle):

    high = float(candle["high"])
    low = float(candle["low"])
    open_price = float(candle["open"])
    close = float(candle["close"])

    body = abs(close - open_price)

    upper_shadow = high - max(open_price, close)
    lower_shadow = min(open_price, close) - low

    return (
        upper_shadow > body * 2
        and lower_shadow < body
    )


def doji(candle):

    open_price = float(candle["open"])
    close = float(candle["close"])

    return abs(open_price - close) < 0.05