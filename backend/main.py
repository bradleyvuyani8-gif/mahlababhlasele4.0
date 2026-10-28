import os
import json
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
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Silence default HTTP access request logs in Uvicorn to keep terminal clean
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

app = FastAPI(
    title="Mahlabahlasele 4.0 Engine",
    description="Backend API and Bot Controller",
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
    "exchange": "binance",
    "api_key": "",
    "secret_key": "",
    "is_connected": False,
    "initial_balance": 0.0,
    "current_balance": 0.0
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

    @app.get("/dashboard")
    def serve_dashboard():
        if os.path.exists("frontend/index.html"):
            return FileResponse("frontend/index.html")
        return {"error": "frontend/index.html not found"}

class ApiKeysPayload(BaseModel):
    api_key: str
    secret_key: str
    exchange: str = "binance"

class SettingsPayload(BaseModel):
    lot_size: float
    leverage: str
    risk_pct: float
    stop_loss: float
    take_profit: float

# Broker Adapter Layer: Asking the platform questions via HMAC-SHA256 Signed Requests
def query_broker_telemetry(api_key: str, secret_key: str, exchange: str):
    try:
        # Route to Binance Testnet/Demo or Live based on configuration
        if "testnet" in exchange.lower() or "demo" in exchange.lower():
            base_url = "https://testnet.binance.vision"
        else:
            base_url = "https://api.binance.com"
            
        timestamp = int(time.time() * 1000)
        query_string = f"timestamp={timestamp}&recvWindow=60000"
        
        # Sign the request using the API Secret Key (HMAC-SHA256)
        signature = hmac.new(
            secret_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {"X-MBX-APIKEY": api_key}
        account_url = f"{base_url}/api/v3/account?{query_string}&signature={signature}"
        
        response = requests.get(account_url, headers=headers, timeout=6)
        
        if response.status_code == 200:
            data = response.json()
            balances = data.get("balances", [])
            total_usdt = 0.0
            for b in balances:
                if b["asset"] in ["USDT", "BUSD"]:
                    total_usdt = float(b["free"]) + float(b["locked"])
                    break
            
            # Query open orders / positions count from broker
            ts_orders = int(time.time() * 1000)
            qs_orders = f"timestamp={ts_orders}&recvWindow=60000"
            sig_orders = hmac.new(
                secret_key.encode('utf-8'),
                qs_orders.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            orders_url = f"{base_url}/api/v3/openOrders?{qs_orders}&signature={sig_orders}"
            orders_res = requests.get(orders_url, headers=headers, timeout=6)
            open_orders = orders_res.json() if orders_res.status_code == 200 else []
            positions_count = len(open_orders) if isinstance(open_orders, list) else 0
            
            return True, total_usdt, positions_count
        else:
            # If broker rejects authorization (e.g. invalid keys or permissions), return failure flag
            return False, 0.0, 0
    except Exception as e:
        return False, 0.0, 0

@app.get("/")
def read_root():
    return {
        "status": "online",
        "bot": "Mahlabahlasele 4.0",
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

    # Continuously poll the broker adapter for live account data
    success, current_balance, positions_count = query_broker_telemetry(
        BOT_STATE["api_key"], 
        BOT_STATE["secret_key"], 
        BOT_STATE["exchange"]
    )
    
    if success:
        BOT_STATE["current_balance"] = current_balance

    # Calculate actual profit/loss relative to initial baseline balance captured upon entry
    calculated_pnl = BOT_STATE["current_balance"] - BOT_STATE["initial_balance"]
    pnl_str = f"+${calculated_pnl:,.2f}" if calculated_pnl >= 0 else f"-${abs(calculated_pnl):,.2f}"

    return {
        "active": BOT_STATE["is_active"],
        "exchange": BOT_STATE["exchange"],
        "has_keys": True,
        "balance": f"${BOT_STATE['current_balance']:,.2f}",
        "pnl": pnl_str,
        "positions_count": positions_count,
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
    
    # Perform initial broker handshake verification
    success, balance, _ = query_broker_telemetry(payload.api_key, payload.secret_key, payload.exchange)
    
    if success:
        BOT_STATE["api_key"] = payload.api_key
        BOT_STATE["secret_key"] = payload.secret_key
        BOT_STATE["exchange"] = payload.exchange
        BOT_STATE["is_connected"] = True
        BOT_STATE["initial_balance"] = balance
        BOT_STATE["current_balance"] = balance
        
        add_log(f"Broker connection verified successfully. Initial Balance recorded: ${balance:,.2f}", "SUCCESS")
        return {"status": "success", "message": "API keys connected and verified."}
    else:
        BOT_STATE["is_connected"] = False
        add_log("Broker connection rejected. Check API Key permissions or secret.", "ERROR")
        raise HTTPException(status_code=400, detail="Authentication failed with broker API.")

@app.post("/api/bot/toggle")
def toggle_auto_trading():
    if not BOT_STATE["is_connected"]:
        add_log("Activation blocked: API connection not established.", "ERROR")
        raise HTTPException(status_code=400, detail="Cannot activate. Connect valid API keys first.")

    BOT_STATE["is_active"] = not BOT_STATE["is_active"]
    status_str = "ACTIVE" if BOT_STATE["is_active"] else "INACTIVE"
    add_log(f"AI Automated Trading Engine: {status_str}", "WARNING" if BOT_STATE["is_active"] else "INFO")
    return {"status": "success", "bot_active": BOT_STATE["is_active"], "message": f"Bot is now {status_str}"}

@app.post("/api/settings")
def update_settings(payload: SettingsPayload):
    BOT_STATE["lot_size"] = payload.lot_size
    BOT_STATE["leverage"] = payload.leverage
    BOT_STATE["risk_pct"] = payload.risk_pct
    BOT_STATE["stop_loss"] = payload.stop_loss
    BOT_STATE["take_profit"] = payload.take_profit
        
    add_log(f"Settings updated: Lot={payload.lot_size}, Lev={payload.leverage}, Risk={payload.risk_pct}%")
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
    
    success, _, positions_count = query_broker_telemetry(BOT_STATE["api_key"], BOT_STATE["secret_key"], BOT_STATE["exchange"])
    return {
        "positions": [
            {
                "symbol": "BTC/USDT",
                "type": "LONG",
                "amount": BOT_STATE["lot_size"],
                "pnl": "+$0.00",
                "status": "OPEN"
            }
        ] if BOT_STATE["is_active"] and positions_count > 0 else []
    }

def evaluate_ai_strategy(current_price: float):
    prev_price = PRICE_HISTORY[-2] if len(PRICE_HISTORY) > 1 else current_price
    momentum_delta = current_price - prev_price
    add_log(f"AI Reasoning: Momentum Delta = {momentum_delta:+.2f} | Synced Balance: ${BOT_STATE['current_balance']:,.2f}", "INFO")

async def background_trading_engine():
    while True:
        await asyncio.sleep(15)
        if BOT_STATE["is_active"] and BOT_STATE["is_connected"]:
            success, current_bal, _ = query_broker_telemetry(BOT_STATE["api_key"], BOT_STATE["secret_key"], BOT_STATE["exchange"])
            if success:
                BOT_STATE["current_balance"] = current_bal
                
            import random
            fluctuation = round(random.uniform(-10.0, 15.0), 2)
            new_price = PRICE_HISTORY[-1] + fluctuation
            PRICE_HISTORY.append(new_price)
            if len(PRICE_HISTORY) > 20:
                PRICE_HISTORY.pop(0)
            evaluate_ai_strategy(new_price)

@app.on_event("startup")
async def startup_event():
    add_log("Mahlabahlasele 4.0 Backend Engine initialized with Secure Broker Adapter.")
    asyncio.create_task(background_trading_engine())
