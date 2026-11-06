import hmac
import hashlib
import time
import requests
from typing import Dict, Any, Tuple

class ExchangeService:
    def __init__(self, exchange: str, api_key: str, secret_key: str, testnet: bool = True):
        self.exchange = exchange.lower().strip()
        self.api_key = api_key.strip()
        self.secret_key = secret_key.strip()
        self.testnet = testnet

    def _get_base_url(self) -> str:
        if self.exchange == "binance":
            return "https://testnet.binance.vision" if self.testnet else "https://api.binance.com"
        elif self.exchange == "bybit":
            return "https://api-testnet.bybit.com" if self.testnet else "https://api.bybit.com"
        elif self.exchange == "alpaca":
            return "https://paper-api.alpaca.markets" if self.testnet else "https://api.alpaca.markets"
        raise ValueError(f"Unknown exchange: {self.exchange}")

    def _sign_binance(self, query_params: Dict[str, Any]) -> str:
        query_string = "&".join([f"{k}={v}" for k, v in sorted(query_params.items())])
        return hmac.new(
            self.secret_key.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def fetch_account_data(self) -> Tuple[bool, float, Dict[str, Any]]:
        base_url = self._get_base_url()

        if self.exchange == "binance":
            url = f"{base_url}/api/v3/account"
            params: Dict[str, Any] = {"timestamp": int(time.time() * 1000)}
            params["signature"] = self._sign_binance(params)
            headers = {"X-MBX-APIKEY": self.api_key}

            try:
                res = requests.get(url, headers=headers, params=params, timeout=8)
                if res.status_code == 200:
                    data = res.json()
                    total_balance = sum(
                        float(asset["free"]) + float(asset["locked"])
                        for asset in data.get("balances", [])
                        if float(asset["free"]) > 0 or float(asset["locked"]) > 0
                    )
                    return True, total_balance, data
                return False, 0.0, {"error": res.json(), "status_code": res.status_code}
            except Exception as e:
                return False, 0.0, {"error": str(e)}

        elif self.exchange == "bybit":
            url = f"{base_url}/v5/account/wallet-balance"
            timestamp = str(int(time.time() * 1000))
            recv_window = "5000"
            query_string = "accountType=UNIFIED"
            
            param_str = timestamp + self.api_key + recv_window + query_string
            signature = hmac.new(
                self.secret_key.encode("utf-8"),
                param_str.encode("utf-8"),
                hashlib.sha256
            ).hexdigest()

            headers = {
                "X-BAPI-API-KEY": self.api_key,
                "X-BAPI-SIGN": signature,
                "X-BAPI-TIMESTAMP": timestamp,
                "X-BAPI-RECV-WINDOW": recv_window
            }

            try:
                res = requests.get(f"{url}?{query_string}", headers=headers, timeout=8)
                if res.status_code == 200:
                    data = res.json()
                    if data.get("retCode") == 0:
                        coins = data.get("result", {}).get("list", [{}])[0].get("coin", [])
                        total_balance = sum(float(c.get("equity", 0.0)) for c in coins)
                        return True, total_balance, data
                    return False, 0.0, {"error": data.get("retMsg", "Bybit error")}
                return False, 0.0, {"error": res.text, "status_code": res.status_code}
            except Exception as e:
                return False, 0.0, {"error": str(e)}

        elif self.exchange == "alpaca":
            url = f"{base_url}/v2/account"
            headers = {
                "APCA-API-KEY-ID": self.api_key,
                "APCA-API-SECRET-KEY": self.secret_key
            }
            try:
                res = requests.get(url, headers=headers, timeout=8)
                if res.status_code == 200:
                    data = res.json()
                    equity = float(data.get("equity", 0.0))
                    return True, equity, data
                return False, 0.0, {"error": res.json(), "status_code": res.status_code}
            except Exception as e:
                return False, 0.0, {"error": str(e)}

        return False, 0.0, {"error": "Unsupported exchange adapter"}
