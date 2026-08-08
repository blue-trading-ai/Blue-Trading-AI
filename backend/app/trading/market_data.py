from datetime import datetime


# Supported trading symbols
SUPPORTED_SYMBOLS = [
    "XAUUSD",
    "BTCUSD",
    "GBPUSD"
]


def get_market_price(symbol: str):

    """
    Get latest market price.

    Later this will connect to:
    - TradingView API
    - Broker API
    - Real-time market feed
    """

    if symbol not in SUPPORTED_SYMBOLS:
        return {
            "error": "Symbol not supported"
        }


    # Temporary sample data
    # Later replaced with live price
    market_data = {
        "symbol": symbol,
        "price": 0,
        "time": datetime.utcnow()
    }


    return market_data