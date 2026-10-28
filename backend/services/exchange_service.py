from backend.services.custom_exchange import SimpleExchangeClient

class ExchangeService:
    def __init__(self):
        self.client = SimpleExchangeClient("binance")

    def get_market_snapshot(self, symbol: str = "BTC/USDT"):
        ticker = self.client.fetch_ticker(symbol)
        order_book = self.client.fetch_order_book(symbol)
        
        return {
            "symbol": symbol,
            "ticker": ticker,
            "order_book": order_book
        }

async def get_market_snapshot(symbol: str = "BTC/USDT"):
    service = ExchangeService()
    return service.get_market_snapshot(symbol)
