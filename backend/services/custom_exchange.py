import httpx

class SimpleExchangeClient:
    def __init__(self, exchange_name="binance"):
        self.exchange_name = exchange_name.lower()
        if self.exchange_name == "binance":
            self.base_url = "https://api.binance.com/api/v3"
        else:
            self.base_url = "https://api.binance.com/api/v3" # fallback default

    def fetch_ticker(self, symbol: str):
        """Alternative to ccxt.fetch_ticker()"""
        url = f"{self.base_url}/ticker/price"
        params = {"symbol": symbol.upper().replace("/", "")}
        
        try:
            response = httpx.get(url, params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            # Standardize output format to match what your app expects
            return {
                "symbol": symbol,
                "price": float(data["price"]),
                "info": data
            }
        except Exception as e:
            print(f"Error fetching ticker via direct REST: {e}")
            return None

    def fetch_order_book(self, symbol: str, limit: int = 5):
        """Alternative to ccxt.fetch_order_book()"""
        url = f"{self.base_url}/depth"
        params = {"symbol": symbol.upper().replace("/", ""), "limit": limit}
        
        try:
            response = httpx.get(url, params=params, timeout=10.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching order book: {e}")
            return None
