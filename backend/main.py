import os
import json
import time
import requests
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse

app = FastAPI()

# ==========================================
# 1. PERSISTENT SHARED STORAGE MEMORY
# ==========================================
class PersistentMemory:
    def __init__(self, filename="mahlabahlasele_memory.json"):
        # Points directly to the Android Download folder via Termux shared storage
        shared_dir = os.path.expanduser("~/storage/shared/Download")
        
        # Fallback to local termux directory if shared storage isn't set up yet
        if not os.path.exists(shared_dir):
            shared_dir = "data"
            
        self.filepath = os.path.join(shared_dir, filename)
        self._ensure_directory()
        self.memory = self.load_memory()

    def _ensure_directory(self):
        directory = os.path.dirname(self.filepath)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

    def load_memory(self):
        """Loads past learning data and trade outcomes from shared storage."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading memory: {e}")
                
        # Default baseline memory structure if file doesn't exist
        return {
            "total_trades": 0,
            "successful_trades": 0,
            "failed_trades": 0,
            "mistakes_log": [],
            "learned_weights": {}
        }

    def save_memory(self):
        """Writes learning state directly to your phone's file manager."""
        try:
            with open(self.filepath, "w") as f:
                json.dump(self.memory, f, indent=4)
        except Exception as e:
            print(f"Error saving memory: {e}")

    def record_trade_outcome(self, trade_type, pnl, market_conditions):
        """Logs a win or loss, updating the bot's historical record."""
        self.memory["total_trades"] += 1
        
        if pnl > 0:
            self.memory["successful_trades"] += 1
        else:
            self.memory["failed_trades"] += 1
            self.memory["mistakes_log"].append({
                "trade_type": trade_type,
                "pnl": pnl,
                "conditions": market_conditions
            })
            
        self.save_memory()

# Initialize persistent memory instance
bot_memory = PersistentMemory()

# ==========================================
# 2. LIVE ALPACA POSITION FETCHER
# ==========================================
def fetch_live_alpaca_positions(api_key: str, api_secret: str, base_url: str = "https://paper-api.alpaca.markets") -> list:
    """
    Queries Alpaca REST API directly for real open positions.
    Additive implementation to replace simulation data safely.
    """
    if not api_key or not api_secret or "mock" in api_key.lower():
        return []
        
    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": api_secret
    }
    
    try:
        response = requests.get(f"{base_url}/v2/positions", headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching live Alpaca positions: {e}")
        
    return []

# ==========================================
# 3. GLOBAL TELEMETRY & ENGINE STATE
# ==========================================
telemetry_state = {
    "engine_state": "ACTIVE",
    "active_exchange": "ALPACA",
    "live_balance": 100000.00,
    "open_positions": 0,
    "active_trades_pnl": 0.00,
    "current_price": 80598.81,
    "ai_signal": "Awaiting Connection",
    "telemetry_status": "Connected"
}

# Credentials configuration (Update these or plug in your live keys generated from Alpaca dashboard)
ACTIVE_API_KEY = os.environ.get("APCA_API_KEY_ID", "YOUR_ALPACA_API_KEY")
ACTIVE_API_SECRET = os.environ.get("APCA_API_SECRET_KEY", "YOUR_ALPACA_SECRET_KEY")
ALPACA_BASE_URL = "https://paper-api.alpaca.markets"

# ==========================================
# 4. BACKGROUND TRADING & POLLING LOOP
# ==========================================
def background_trading_engine():
    """Background worker loop updating telemetry and pulling live Alpaca positions."""
    while True:
        try:
            # 1. Fetch real open positions count from Alpaca API
            live_positions = fetch_live_alpaca_positions(ACTIVE_API_KEY, ACTIVE_API_SECRET, ALPACA_BASE_URL)
            telemetry_state["open_positions"] = len(live_positions)
            
            # If positions exist, calculate total live PnL if available from response
            if live_positions:
                total_pnl = sum(float(pos.get("unrealized_pl", 0.0)) for pos in live_positions)
                telemetry_state["active_trades_pnl"] = round(total_pnl, 2)
            else:
                telemetry_state["active_trades_pnl"] = 0.00
                
            telemetry_state["ai_signal"] = "Market Monitored - Live Sync OK"
        except Exception as e:
            print(f"Background engine loop error: {e}")
            telemetry_state["ai_signal"] = "Sync Error / Retrying"
            
        time.sleep(10)

@app.on_event("startup")
def startup_event():
    import threading
    engine_thread = threading.Thread(target=background_trading_engine, daemon=True)
    engine_thread.start()

# ==========================================
# 5. DASHBOARD & API ENDPOINTS
# ==========================================
@app.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Mahlabahlasele Control Panel</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ background: #0f172a; color: #f8fafc; font-family: sans-serif; padding: 15px; margin: 0; }}
            .card {{ background: #1e293b; padding: 15px; border-radius: 8px; margin-bottom: 12px; }}
            h2 {{ color: #38bdf8; font-size: 1.2rem; margin-top: 0; }}
            .metric {{ display: flex; justify-content: space-between; margin: 8px 0; border-bottom: 1px solid #334155; padding-bottom: 6px; }}
        </style>
    </head>
    <body>
        <h2>MAHLABAHLASELE ENGINE</h2>
        <div class="card">
            <div class="metric"><span>Engine State:</span> <strong>{telemetry_state['engine_state']}</strong></div>
            <div class="metric"><span>Active Exchange:</span> <strong>{telemetry_state['active_exchange']}</strong></div>
            <div class="metric"><span>Live Balance:</span> <strong>${telemetry_state['live_balance']:,.2f}</strong></div>
            <div class="metric"><span>Open Positions:</span> <strong>{telemetry_state['open_positions']}</strong></div>
            <div class="metric"><span>Active Trades PnL:</span> <strong>${telemetry_state['active_trades_pnl']:,.2f}</strong></div>
        </div>
        <div class="card">
            <h2>MARKET VIEW (BTC/USDT)</h2>
            <div class="metric"><span>Current Price:</span> <strong>${telemetry_state['current_price']:,.2f}</strong></div>
            <div class="metric"><span>AI Strategy Signal:</span> <strong>{telemetry_state['ai_signal']}</strong></div>
            <div class="metric"><span>Telemetry Status:</span> <strong style="color: #4ade80;">{telemetry_state['telemetry_status']}</strong></div>
        </div>
        <div class="card">
            <h2>MEMORY SYSTEM</h2>
            <div class="metric"><span>Total Logged Trades:</span> <strong>{bot_memory.memory['total_trades']}</strong></div>
            <div class="metric"><span>Storage Path:</span> <small>{bot_memory.filepath}</small></div>
        </div>
    </body>
    </html>
    """

@app.get("/api/telemetry")
def get_telemetry():
    return {
        "telemetry": telemetry_state,
        "memory_stats": {
            "total_trades": bot_memory.memory["total_trades"],
            "successful_trades": bot_memory.memory["successful_trades"],
            "failed_trades": bot_memory.memory["failed_trades"]
        }
    }
