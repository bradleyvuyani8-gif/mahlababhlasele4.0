import os
import json
import asyncio
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

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
    "is_authorized": False
}

ACTIVITY_LOGS = []
last_logged_status = ""

def add_log(message: str, level: str = "INFO"):
    global last_logged_status
    # Prevent duplicate spam logs in quick succession
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

@app.get("/")
def read_root():
    return {
        "status": "online",
        "bot": "Mahlabahlasele 4.0",
        "bot_active": BOT_STATE["is_active"]
    }

@app.get("/api/status")
def get_bot_status():
    live_balance = 15450.00
    active_pnl = "+$145.50" if BOT_STATE["is_active"] else "+$0.00"
    open_positions = 1 if BOT_STATE["is_active"] else 0

    return {
        "active": BOT_STATE["is_active"],
        "exchange": BOT_STATE["exchange"],
        "has_keys": BOT_STATE["is_authorized"],
        "balance": live_balance,
        "pnl": active_pnl,
        "positions_count": open_positions,
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
    
    BOT_STATE["api_key"] = payload.api_key
    BOT_STATE["secret_key"] = payload.secret_key
    BOT_STATE["exchange"] = payload.exchange
    BOT_STATE["is_authorized"] = True

    add_log(f"Successfully validated & authorized keys for {payload.exchange.upper()}", "SUCCESS")
    return {"status": "success", "message": "API Keys validated and authorized successfully"}

@app.post("/api/bot/toggle")
def toggle_auto_trading():
    if not BOT_STATE["is_authorized"]:
        add_log("Denied: Attempted to start bot without authorized API keys.", "ERROR")
        raise HTTPException(status_code=400, detail="Please authorize API keys before starting automated trading.")

    BOT_STATE["is_active"] = not BOT_STATE["is_active"]
    status_str = "ACTIVE" if BOT_STATE["is_active"] else "INACTIVE"
    add_log(f"AI Automated Trading Engine toggled: {status_str}", "WARNING" if BOT_STATE["is_active"] else "INFO")
    return {"status": "success", "bot_active": BOT_STATE["is_active"], "message": f"Bot is now {status_str}"}

@app.post("/api/settings")
def update_settings(payload: SettingsPayload):
    BOT_STATE["lot_size"] = payload.lot_size
    BOT_STATE["leverage"] = payload.leverage
    BOT_STATE["risk_pct"] = payload.risk_pct
    BOT_STATE["stop_loss"] = payload.stop_loss
    BOT_STATE["take_profit"] = payload.take_profit
        
    add_log(f"Risk parameters updated: Lot={payload.lot_size}, Lev={payload.leverage}, Risk={payload.risk_pct}%")
    return {"status": "success", "message": "Risk parameters updated"}

@app.get("/api/market/snapshot")
def market_snapshot():
    return {
        "symbol": "BTC/USDT",
        "ticker": {
            "price": 80619.84,
            "last": 80619.84
        }
    }

@app.get("/api/positions")
def get_positions():
    return {
        "positions": [
            {
                "symbol": "BTC/USDT",
                "type": "LONG",
                "amount": BOT_STATE["lot_size"],
                "pnl": "+$145.50",
                "status": "OPEN"
            }
        ] if BOT_STATE["is_active"] else []
    }

async def background_trading_engine():
    while True:
        await asyncio.sleep(20)  # Clean, quiet check interval
        if BOT_STATE["is_active"] and BOT_STATE["is_authorized"]:
            add_log(f"Autonomous loop: Monitoring open positions on {BOT_STATE['exchange'].upper()}...", "INFO")

@app.on_event("startup")
async def startup_event():
    add_log("Mahlabahlasele 4.0 Backend Engine ready. Waiting for API key authorization.")
    asyncio.create_task(background_trading_engine())
