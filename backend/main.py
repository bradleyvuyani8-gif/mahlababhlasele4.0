import os
import logging
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from backend.services.broker_service import auto_detect_and_query_broker, fetch_exchange_data
from backend.services.learning_service import execute_strategy_pipeline

logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

app = FastAPI(
    title="Mahlabahlasele 4.0 Pro Engine",
    description="Decoupled Modular Trading Architecture",
    version="4.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Manager State
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
    
    timestamp = datetime.now().strftime("%H:%M:%S") if 'datetime' in globals() else "00:00:00"
    from datetime import datetime as dt
    timestamp = dt.now().strftime("%H:%M:%S")
    
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

@app.get("/")
def read_root():
    return {"status": "online", "bot": "Mahlabahlasele 4.0 Manager", "bot_active": BOT_STATE["is_active"]}

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
            "strategy_status": "Awaiting Connection",
            "settings": {
                "lot_size": BOT_STATE["lot_size"],
                "leverage": BOT_STATE["leverage"],
                "risk_pct": BOT_STATE["risk_pct"],
                "stop_loss": BOT_STATE["stop_loss"],
                "take_profit": BOT_STATE["take_profit"]
            }
        }

    calculated_pnl = BOT_STATE["current_balance"] - BOT_STATE["initial_balance"]
    pnl_str = f"+${calculated_pnl:,.2f}" if calculated_pnl >= 0 else f"-${abs(calculated_pnl):,.2f}"
    strategy_text = "Active & Monitoring" if BOT_STATE["is_active"] else "Paused Standby"

    return {
        "active": BOT_STATE["is_active"],
        "exchange": BOT_STATE["exchange"],
        "has_keys": True,
        "balance": f"${BOT_STATE['current_balance']:,.2f}",
        "pnl": pnl_str,
        "positions_count": BOT_STATE["open_positions_count"],
        "strategy_status": strategy_text,
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
    
    add_log("Manager initiating Multi-Broker Auto-Discovery...", "INFO")
    detected_exchange, balance, _ = auto_detect_and_query_broker(payload.api_key, payload.secret_key)
    
    if detected_exchange:
        BOT_STATE["api_key"] = "".join(payload.api_key.split())
        BOT_STATE["secret_key"] = "".join(payload.secret_key.split())
        BOT_STATE["exchange"] = detected_exchange
        BOT_STATE["is_connected"] = True
        BOT_STATE["initial_balance"] = balance
        BOT_STATE["current_balance"] = balance
        BOT_STATE["open_positions_count"] = 0
        
        add_log(f"Manager connected to {detected_exchange.upper()}. Balance: ${balance:,.2f}", "SUCCESS")
        return {"status": "success", "message": f"Successfully connected to {detected_exchange.upper()}."}
    else:
        BOT_STATE["is_connected"] = False
        add_log("Manager authentication failed across all adapters.", "ERROR")
        raise HTTPException(status_code=400, detail="Authentication failed. Check your API credentials.")

@app.post("/api/bot/toggle")
def toggle_auto_trading():
    if not BOT_STATE["is_connected"]:
        raise HTTPException(status_code=400, detail="Connect valid API keys first.")
    
    BOT_STATE["is_active"] = not BOT_STATE["is_active"]
    status_str = "ACTIVE" if BOT_STATE["is_active"] else "INACTIVE"
    add_log(f"Trading Engine state changed: {status_str}", "WARNING" if BOT_STATE["is_active"] else "INFO")
    return {"status": "success", "bot_active": BOT_STATE["is_active"], "message": f"Bot is now {status_str}"}

@app.post("/api/settings")
def update_settings(payload: SettingsPayload):
    BOT_STATE["lot_size"] = payload.lot_size
    BOT_STATE["leverage"] = payload.leverage
    BOT_STATE["risk_pct"] = payload.risk_pct
    BOT_STATE["stop_loss"] = payload.stop_loss
    BOT_STATE["take_profit"] = payload.take_profit
    add_log("Risk parameters updated by manager.", "INFO")
    return {"status": "success", "message": "Settings updated"}

@app.get("/api/market/snapshot")
def market_snapshot():
    current_price = PRICE_HISTORY[-1]
    return {"symbol": "BTC/USDT", "ticker": {"price": current_price, "last": current_price}}

@app.get("/api/positions")
def get_positions():
    if not BOT_STATE["is_connected"]:
        return {"positions": []}
    return {
        "positions": [
            {
                "symbol": "BTC/USDT",
                "type": "LONG",
                "amount": BOT_STATE["lot_size"],
                "pnl": f"${(BOT_STATE['current_balance'] - BOT_STATE['initial_balance']):,.2f}",
                "status": "OPEN"
            }
        ] if BOT_STATE["open_positions_count"] > 0 else []
    }

async def background_manager_loop():
    while True:
        await asyncio.sleep(15)
        if BOT_STATE["is_connected"]:
            # Delegate data fetching to broker_service
            current_bal, pos_count = fetch_exchange_data(
                BOT_STATE["exchange"], 
                BOT_STATE["api_key"], 
                BOT_STATE["secret_key"],
                BOT_STATE["current_balance"],
                BOT_STATE["open_positions_count"]
            )
            BOT_STATE["current_balance"] = current_bal
            BOT_STATE["open_positions_count"] = pos_count
            
            # If active, delegate decision making to learning_service
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
                    BOT_STATE["open_positions_count"] += 1
                    add_log(f"Strategy Triggered Trade ({decision['action']}): {decision['reason']}", "SUCCESS")
                else:
                    add_log(f"Strategy Status: {decision['reason']}", "INFO")

@app.on_event("startup")
async def startup_event():
    add_log("Mahlabahlasele 4.0 Manager online. Services linked successfully.", "SUCCESS")
    asyncio.create_task(background_manager_loop())
