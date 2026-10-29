import os
import logging
import asyncio
import time
import hmac
import hashlib
import requests
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from backend.services.learning_service import execute_strategy_pipeline

logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

app = FastAPI(
    title="Mahlabahlasele 4.0 Pro Engine",
    description="Multi-Broker Auto-Discovery Telemetry Engine",
    version="4.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BOT_STATE = {
    "is_active": False,
    "lot_size": 0.15,
    "leverage": "20x",
    "risk_pct": 2.5,
    "stop_loss": 1.2,
    "take_profit": 4.0,
    "exchange": "auto-detecting",
    "api_key": "",
    "secret_key": "",
    "is_connected": False,
    "initial_balance": 0.0,
    "current_balance": 0.0,
    "open_positions_count": 0,
    "active_endpoint": ""
}

ACTIVITY_LOGS = []
last_logged_status = ""
PRICE_HISTORY = [80619.84, 80625.00, 80610.50, 80630.20, 80619.84]

def add_log(message: str, level: str = "INFO"):
    global last_logged_status
    if message == last_logged_status:
        return
    last_logged_status = message
    
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = {"time": timestamp, "message": message, "level": level}
    ACTIVITY_LOGS.insert(0, log_entry)
    if len(ACTIVITY_LOGS) > 30:
        ACTIVITY_LOGS.pop()
    print(f"[{timestamp}] [{level}] {message}")

if os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/dashboard", response_class=HTMLResponse)
def serve_dashboard():
    if os.path.exists("frontend/index.html"):
        return FileResponse("frontend/index.html")
    return {"error": "frontend/index.html not found"}

class ApiKeysPayload(BaseModel):
    api_key: str
    secret_key: str

class SettingsPayload(BaseModel):
    lot_size: float
    leverage: str
    risk_pct: float
    stop_loss: float
    take_profit: float

def fetch_real_positions(exchange: str, api_key: str, secret_key: str) -> list:
    clean_key = "".join(api_key.split())
    clean_secret = "".join(secret_key.split())
    
    if exchange == "alpaca":
        try:
            base_url = "https://paper-api.alpaca.markets"
            headers = {
                "APCA-API-KEY-ID": clean_key,
                "APCA-API-SECRET-KEY": clean_secret,
                "accept": "application/json"
            }
            res = requests.get(f"{base_url}/v2/positions", headers=headers, timeout=5)
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            add_log(f"Alpaca positions fetch error: {e}", "DEBUG")
            
    elif exchange == "binance":
        binance_endpoints = ["https://testnet.binance.vision/api", "https://api.binance.com/api"]
        for base_url in binance_endpoints:
            try:
                timestamp = int(time.time() * 1000)
                query_string = f"timestamp={timestamp}&recvWindow=60000"
                signature = hmac.new(clean_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
                headers = {"X-MBX-APIKEY": clean_key, "Accept": "application/json"}
                url = f"{base_url}/v3/openOrders?{query_string}&signature={signature}"
                res = requests.get(url, headers=headers, timeout=5)
                if res.status_code == 200:
                    return res.json()
            except Exception as e:
                pass

    elif exchange == "bybit":
        try:
            base_url = "https://api-testnet.bybit.com"
            timestamp = str(int(time.time() * 1000))
            recv_window = "5000"
            query_params = "category=linear&settleCoin=USDT"
            payload_str = f"{timestamp}{clean_key}{recv_window}{query_params}"
            signature = hmac.new(clean_secret.encode('utf-8'), payload_str.encode('utf-8'), hashlib.sha256).hexdigest()
            headers = {
                "X-BAPI-API-KEY": clean_key,
                "X-BAPI-SIGN": signature,
                "X-BAPI-TIMESTAMP": timestamp,
                "X-BAPI-RECV-WINDOW": recv_window
            }
            res = requests.get(f"{base_url}/v5/position/list?{query_params}", headers=headers, timeout=5)
            if res.status_code == 200:
                list_data = res.json().get("result", {}).get("list", [])
                return [p for p in list_data if float(p.get("size", 0.0)) > 0]
        except Exception as e:
            pass
            
    return []

def auto_detect_and_query_broker(api_key: str, secret_key: str):
    clean_key = "".join(api_key.split())
    clean_secret = "".join(secret_key.split())
    
    binance_endpoints = ["https://testnet.binance.vision/api", "https://api.binance.com/api"]
    for base_url in binance_endpoints:
        try:
            add_log(f"Probing Binance endpoint: {base_url}", "INFO")
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
                add_log(f"Auto-Discovery successful: Binance! Balance: ${total_usdt:,.2f}", "SUCCESS")
                real_pos = fetch_real_positions("binance", clean_key, clean_secret)
                return "binance", float(total_usdt), len(real_pos)
            else:
                add_log(f"Binance probe rejected: {res.text}", "WARNING")
        except Exception as e:
            add_log(f"Binance probe exception: {e}", "DEBUG")

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
                add_log(f"Auto-Discovery successful: Bybit! Equity: ${total_equity:,.2f}", "SUCCESS")
                real_pos = fetch_real_positions("bybit", clean_key, clean_secret)
                return "bybit", total_equity, len(real_pos)
    except Exception as e:
        add_log(f"Bybit probe exception: {e}", "DEBUG")

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
            add_log(f"Auto-Discovery successful: Alpaca! Equity: ${equity:,.2f}", "SUCCESS")
            real_pos = fetch_real_positions("alpaca", clean_key, clean_secret)
            return "alpaca", equity, len(real_pos)
    except Exception as e:
        add_log(f"Alpaca probe exception: {e}", "DEBUG")

    add_log("Broker auto-discovery failed across all adapters. Invalid credentials or network error.", "ERROR")
    return None, 0.0, 0

@app.get("/")
def read_root():
    return {
        "status": "online",
        "bot": "Mahlabahlasele 4.0 Pro",
        "bot_active": BOT_STATE["is_active"]
    }

@app.get("/api/status")
def get_bot_status():
    if not BOT_STATE["is_connected"]:
        return {
            "active": False,
            "exchange": BOT_STATE["exchange"],
            "has_keys": False,
            "balance": "...",
            "pnl": "...",
            "positions_count": "...",
            "settings": {
                "lot_size": BOT_STATE["lot_size"],
                "leverage": BOT_STATE["leverage"],
                "risk_pct": BOT_STATE["risk_pct"],
                "stop_loss": BOT_STATE["stop_loss"],
                "take_profit": BOT_STATE["take_profit"]
            }
        }

    detected_exchange, current_balance, positions_count = auto_detect_and_query_broker(
        BOT_STATE["api_key"], 
        BOT_STATE["secret_key"]
    )
    
    if detected_exchange:
        BOT_STATE["current_balance"] = current_balance
        BOT_STATE["open_positions_count"] = positions_count

    calculated_pnl = BOT_STATE["current_balance"] - BOT_STATE["initial_balance"]
    pnl_str = f"+${calculated_pnl:,.2f}" if calculated_pnl >= 0 else f"-${abs(calculated_pnl):,.2f}"

    return {
        "active": BOT_STATE["is_active"],
        "exchange": BOT_STATE["exchange"],
        "has_keys": True,
        "balance": f"${BOT_STATE['current_balance']:,.2f}",
        "pnl": pnl_str,
        "positions_count": BOT_STATE["open_positions_count"],
        "settings": {
            "lot_size": BOT_STATE["lot_size"],
            "leverage": BOT_STATE["leverage"],
            "risk_pct": BOT_STATE["risk_pct"],
            "stop_loss": BOT_STATE["stop_loss"],
            "take_profit": BOT_STATE["take_profit"]
        }
    }

@app.get("/api/logs")
def get_activity_logs():
    return {"logs": ACTIVITY_LOGS}

@app.post("/api/config")
def save_api_keys(payload: ApiKeysPayload):
    if not payload.api_key or not payload.secret_key:
        raise HTTPException(status_code=400, detail="API Key and Secret Key are required.")
    
    add_log("Initiating Multi-Broker Auto-Discovery...", "INFO")
    detected_exchange, balance, positions_count = auto_detect_and_query_broker(payload.api_key, payload.secret_key)
    
    if detected_exchange:
        BOT_STATE["api_key"] = "".join(payload.api_key.split())
        BOT_STATE["secret_key"] = "".join(payload.secret_key.split())
        BOT_STATE["exchange"] = detected_exchange
        BOT_STATE["is_connected"] = True
        BOT_STATE["initial_balance"] = balance
        BOT_STATE["current_balance"] = balance
        BOT_STATE["open_positions_count"] = positions_count
        
        add_log(f"Connected to {detected_exchange.upper()}. True Balance: ${balance:,.2f}", "SUCCESS")
        return {"status": "success", "message": f"Successfully auto-discovered and connected to {detected_exchange.upper()}."}
    else:
        BOT_STATE["is_connected"] = False
        add_log("Auto-Discovery failed: Credentials rejected by all broker adapters.", "ERROR")
        raise HTTPException(status_code=400, detail="Authentication failed. Check your API credentials or network connection.")

@app.post("/api/bot/toggle")
def toggle_auto_trading():
    if not BOT_STATE["is_connected"]:
        add_log("Activation blocked: API connection not established.", "ERROR")
        raise HTTPException(status_code=400, detail="Cannot activate. Connect valid API keys first.")
    
    if BOT_STATE["current_balance"] <= 0:
        add_log("Trading restricted: Account balance is $0.00. Fund your broker account to trade.", "WARNING")
        raise HTTPException(status_code=400, detail="Trading restricted. Account balance must be greater than $0.00.")

    BOT_STATE["is_active"] = not BOT_STATE["is_active"]
    status_str = "ACTIVE" if BOT_STATE["is_active"] else "INACTIVE"
    add_log(f"AI Automated Trading Engine state changed: {status_str}", "WARNING" if BOT_STATE["is_active"] else "INFO")
    return {"status": "success", "bot_active": BOT_STATE["is_active"], "message": f"Bot is now {status_str}"}

@app.post("/api/settings")
def update_settings(payload: SettingsPayload):
    BOT_STATE["lot_size"] = payload.lot_size
    BOT_STATE["leverage"] = payload.leverage
    BOT_STATE["risk_pct"] = payload.risk_pct
    BOT_STATE["stop_loss"] = payload.stop_loss
    BOT_STATE["take_profit"] = payload.take_profit
        
    add_log(f"Risk parameters updated: Lot={payload.lot_size}, Lev={payload.leverage}, Risk={payload.risk_pct}%", "INFO")
    return {"status": "success", "message": "Settings updated"}

@app.get("/api/market/snapshot")
def market_snapshot():
    current_price = PRICE_HISTORY[-1]
    return {
        "symbol": "BTC/USDT",
        "ticker": {
            "price": current_price,
            "last": current_price
        }
    }

@app.get("/api/positions")
def get_positions():
    if not BOT_STATE["is_connected"]:
        return {"positions": []}
    
    real_pos = fetch_real_positions(BOT_STATE["exchange"], BOT_STATE["api_key"], BOT_STATE["secret_key"])
    
    positions_list = []
    for pos in real_pos:
        positions_list.append({
            "symbol": pos.get("symbol", "BTC/USDT"),
            "type": pos.get("side", "LONG").upper(),
            "amount": float(pos.get("qty", pos.get("size", BOT_STATE["lot_size"]))),
            "pnl": f"${float(pos.get('unrealized_pl', 0.0)):,.2f}",
            "status": "OPEN"
        })
        
    return {"positions": positions_list}

async def background_trading_engine():
    while True:
        await asyncio.sleep(15)
        if BOT_STATE["is_connected"]:
            detected_exchange, current_bal, pos_count = auto_detect_and_query_broker(BOT_STATE["api_key"], BOT_STATE["secret_key"])
            if detected_exchange:
                BOT_STATE["current_balance"] = current_bal
                BOT_STATE["open_positions_count"] = pos_count
                
            if BOT_STATE["is_active"] and BOT_STATE["current_balance"] > 0:
                import random
                fluctuation = round(random.uniform(-5.0, 5.0), 2)
                new_price = PRICE_HISTORY[-1] + fluctuation
                PRICE_HISTORY.append(new_price)
                if len(PRICE_HISTORY) > 20:
                    PRICE_HISTORY.pop(0)
                
                decision = execute_strategy_pipeline(
                    PRICE_HISTORY, 
                    BOT_STATE["current_balance"], 
                    BOT_STATE["risk_pct"],
                    BOT_STATE["exchange"]
                )
                
                if decision["action"] in ["BUY", "SELL"]:
                    add_log(f"Trade Signal Executed ({decision['action']}): {decision['reason']}", "SUCCESS")
                else:
                    add_log(f"Strategy Evaluated: {decision['reason']}", "INFO")

@app.on_event("startup")
async def startup_event():
    add_log("Mahlabahlasele 4.0 Pro Engine initialized with Multi-Broker Auto-Discovery.", "SUCCESS")
    asyncio.create_task(background_trading_engine())
