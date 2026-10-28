import ccxt

exchange = ccxt.binance({
    "enableRateLimit": True
})


async def get_market_snapshot(symbol="BTC/USDT"):
    ticker = exchange.fetch_ticker(symbol)

    return {
        "symbol": symbol,
        "last": ticker["last"],
        "high": ticker["high"],
        "low": ticker["low"],
        "volume": ticker["baseVolume"]
    }
