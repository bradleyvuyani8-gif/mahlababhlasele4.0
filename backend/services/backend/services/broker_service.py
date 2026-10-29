import time
import hmac
import hashlib
import requests

def fetch_exchange_data(exchange: str, api_key: str, secret_key: str, current_balance: float, open_positions_count: int):
    clean_key = "".join(api_key.split())
    clean_secret = "".join(secret_key.split())
    
    balance = current_balance
    positions_count = open_positions_count

    if exchange == "alpaca":
        try:
            base_url = "https://paper-api.alpaca.markets"
            headers = {
                "APCA-API-KEY-ID": clean_key,
                "APCA-API-SECRET-KEY": clean_secret,
                "accept": "application/json"
            }
            res = requests.get(f"{base_url}/v2/account", headers=headers, timeout=5)
            if res.status_code == 200:
                balance = float(res.json().get("equity", balance))
                
            pos_res = requests.get(f"{base_url}/v2/positions", headers=headers, timeout=5)
            if pos_res.status_code == 200:
                positions_count = len(pos_res.json())
        except Exception:
            pass

    elif exchange == "binance":
        binance_endpoints = ["https://testnet.binance.vision/api", "https://api.binance.com/api"]
        for base_url in binance_endpoints:
            try:
                timestamp = int(time.time() * 1000)
                query_string = f"timestamp={timestamp}&recvWindow=60000"
                signature = hmac.new(clean_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
                headers = {"X-MBX-APIKEY": clean_key, "Accept": "application/json"}
                url = f"{base_url}/v3/account?{query_string}&signature={signature}"
                res = requests.get(url, headers=headers, timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    balances = data.get("balances", [])
                    balance = sum(float(b.get("free", 0.0)) + float(b.get("locked", 0.0)) for b in balances if b.get("asset", "").upper() in ["USDT", "BUSD", "USDC", "USD"])
                    break
            except Exception:
                pass

    elif exchange == "bybit":
        try:
            base_url = "https://api-testnet.bybit.com"
            timestamp = str(int(time.time() * 1000))
            recv_window = "5000"
            payload_str = f"{timestamp}{clean_key}{recv_window}"
            signature = hmac.new(clean_secret.encode('utf-8'), payload_str.encode('utf-8'), hashlib.sha256).hexdigest()
            headers = {
                "X-BAPI-API-KEY": clean_key,
                "X-BAPI-SIGN": signature,
                "X-BAPI-TIMESTAMP": timestamp,
                "X-BAPI-RECV-WINDOW": recv_window,
                "Content-Type": "application/json"
            }
            res = requests.get(f"{base_url}/v5/account/wallet-balance?accountType=UNIFIED", headers=headers, timeout=5)
            if res.status_code == 200:
                result = res.json().get("result", {}).get("list", [])
                if result:
                    balance = float(result[0].get("totalEquity", balance))
        except Exception:
            pass

    return balance, positions_count

def auto_detect_and_query_broker(api_key: str, secret_key: str):
    clean_key = "".join(api_key.split())
    clean_secret = "".join(secret_key.split())
    
    binance_endpoints = ["https://testnet.binance.vision/api", "https://api.binance.com/api"]
    for base_url in binance_endpoints:
        try:
            time_res = requests.get(f"{base_url}/v3/time", timeout=3)
            server_time = int(time_res.json().get("serverTime", time.time() * 1000)) if time_res.status_code == 200 else int(time.time() * 1000)
            
            timestamp = server_time
            query_string = f"timestamp={timestamp}&recvWindow=60000"
            signature = hmac.new(clean_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
            headers = {"X-MBX-APIKEY": clean_key, "Accept": "application/json"}
            url = f"{base_url}/v3/account?{query_string}&signature={signature}"
            
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                data = res.json()
                balances = data.get("balances", [])
                total_usdt = sum(float(b.get("free", 0.0)) + float(b.get("locked", 0.0)) for b in balances if b.get("asset", "").upper() in ["USDT", "BUSD", "USDC", "USD"])
                return "binance", float(total_usdt), 0
        except Exception:
            pass

    try:
        base_url = "https://api-testnet.bybit.com"
        timestamp = str(int(time.time() * 1000))
        recv_window = "5000"
        payload_str = f"{timestamp}{clean_key}{recv_window}"
        signature = hmac.new(clean_secret.encode('utf-8'), payload_str.encode('utf-8'), hashlib.sha256).hexdigest()
        headers = {
            "X-BAPI-API-KEY": clean_key,
            "X-BAPI-SIGN": signature,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": recv_window,
            "Content-Type": "application/json"
        }
        res = requests.get(f"{base_url}/v5/account/wallet-balance?accountType=UNIFIED", headers=headers, timeout=5)
        if res.status_code == 200:
            result = res.json().get("result", {}).get("list", [])
            if result:
                total_equity = float(result[0].get("totalEquity", 0.0))
                return "bybit", total_equity, 0
    except Exception:
        pass

    try:
        base_url = "https://paper-api.alpaca.markets"
        headers = {
            "APCA-API-KEY-ID": clean_key,
            "APCA-API-SECRET-KEY": clean_secret,
            "accept": "application/json"
        }
        res = requests.get(f"{base_url}/v2/account", headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            equity = float(data.get("equity", 0.0))
            return "alpaca", equity, 0
    except Exception:
        pass

    return None, 0.0, 0
