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
    "exchange": "",
    "api_key": "",
    "secret_key": "",
    "is_connected": False,
    "initial_balance": 0.0,
    "current_balance": 0.0,
    "open_positions_count": 0
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

def fetch_exchange_data(exchange: str, api_key: str, secret_key: str):
    """Fetches live balance and position count directly for the active exchange without re-probing."""
    clean_key = "".join(api_key.split())
    clean_secret = "".join(secret_key.split())
    
    balance = BOT_STATE["current_balance"]
    positions_count = 0

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
        except Exception as e:
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
            except Exception as e:
                pass

    elif exchange == "bybit":
        try:
            base_url = "https://api-testnet.bybit.com"
            timestamp = str(int(time.time() * 1000))
            recv_window = "5000"
            payload_str = f"{timestamp}{clean_key}{recv_
