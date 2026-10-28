# REMOVE: import ccxt
from backend.services.custom_exchange import SimpleExchangeClient

class ExchangeService:
    def __init__(self):
        # Initialize our lightweight alternative client
        self.client = SimpleExchangeClient("binance")

    def get_market_snapshot(self, symbol: str):
        # Re-map the method calls your FastAPI routes expect
        ticker = self.client.fetch_ticker(symbol)
        order_book = self.client.fetch_order_book(symbol)
        
        return {
            "ticker": ticker,
            "order_book": order_book
        }

# Global helper function expected by backend/api/market.py
def get_market_snapshot(symbol: str = "BTC/USDT"):
    service = ExchangeService()
    return service.get_market_snapshot(symbol)
