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
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

app = FastAPI(
    title="Mahlabahlasele 4.0 Pro Engine",
    description="Multi-Broker True-Balance Telemetry & Frontend Synchronization Engine",
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

HTML_DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mahlabahlasele 4.0 Pro Dashboard</title>
    <style>
        body { background-color: #0f172a; color: #f8fafc; font-family: monospace; padding: 20px; margin: 0; }
        .container { max-width: 600px; margin: auto; background: #1e293b; padding: 20px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.5); }
        h2 { color: #38bdf8; text-align: center; }
        .card { background: #0f172a; padding: 15px; margin-bottom: 15px; border-radius: 6px; border: 1px solid #334155; }
        .label { color: #94a3b8; font-size: 0.9em; }
        .value { font-size: 1.2em; font-weight: bold; color: #34d399; }
        input, select { width: 100%; padding: 10px; margin-top: 5px; margin-bottom: 10px; background: #1e293b; border: 1px solid #475569; color: white; border-radius: 4px; box-sizing: border-box; }
        button { width: 100%; padding: 12px; background: #0284c7; color: white; border: none; font-weight: bold; border-radius: 4px; cursor: pointer; }
        button:hover { background: #0ea5e9; }
        .log-box { background: #000; padding: 10px; height: 120px; overflow-y: scroll; font-size: 0.8em; border-radius: 4px; color: #a3e635; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Mahlabahlasele 4.0 Pro Engine</h2>
        
        <div class="card">
            <h3>Broker Configuration</h3>
            <label class="label">Select Exchange</label>
            <select id="exchange">
                <option value="binance">Binance / Binance Testnet</option>
                <option value="bybit">Bybit Unified Testnet</option>
                <option value="alpaca">Alpaca Paper Trading</option>
            </select>
            <label class="label">API Key</label>
            <input type="password" id="apiKey" placeholder="Enter API Key">
            <label class="label">Secret Key</label>
            <input type="password" id="secretKey" placeholder="Enter Secret Key">
            <button onclick="saveKeys()">Save & Authorize Keys</button>
        </div>

        <div class="card">
            <h3>Bot Control Panel</h3>
            <div>Engine State: <span id="engineState" style="color: #facc15;">READY (IDLE)</span></div>
            <div>Active Exchange: <span id="activeExchange">Binance</span></div>
            <div>Live Account Balance: <span id="liveBalance" class="value">$0.00</span></div>
            <div>Open Positions: <span id="openPositions">0</span></div>
            <div>Active Trades PnL: <span id="activePnl" style="color: #38bdf8;">+$0.00</span></div>
            <br>
            <button onclick="toggleBot()" style="background: #16a34a;" id="toggleBtn">ACTIVATE AUTOMATED TRADING</button>
        </div>

        <div class="card">
            <h3>Live Engine Activity Log</h3>
            <div id="logBox" class="log-box">Initializing telemetry feed...</div>
        </div>
    </div>

    <script>
        async function fetchStatus() {
            try {
                let res = await fetch('/api/status');
                let data = await res.json();
                document.getElementById('activeExchange').innerText = data.exchange.toUpperCase();
                document.getElementById('liveBalance').innerText = data.balance;
                document.getElementById('activePnl').innerText = data.pnl;
                document.getElementById('openPositions').innerText = data.positions_count;
                
                let stateEl = document.getElementById('engineState');
                let toggleBtn = document.getElementById('toggleBtn');
                if (data.active) {
                    stateEl.innerText = "ACTIVE (RUNNING)";
                    stateEl.style.color = "#4ade80";
                    toggleBtn.innerText = "DEACTIVATE TRADING";
                    toggleBtn.style.background = "#dc2626";
                } else {
                    stateEl.innerText = "READY (IDLE)";
                    stateEl.style.color = "#facc15";
                    toggleBtn.innerText = "ACTIVATE AUTOMATED TRADING";
                    toggleBtn.style.background = "#16a34a";
                }
            } catch (e) {
                console.error("Status fetch error:", e);
            }
        }

        async function fetchLogs() {
            try {
                let res = await fetch('/api/logs');
                let data = await res.json();
                let logHtml = "";
                data.logs.forEach(l => {
                    logHtml += `[${l.time}] [${l.level}] ${l.message}<br>`;
                });
                document.getElementById('logBox').innerHTML = logHtml;
            } catch (e) {
                console.error("Logs fetch error:", e);
            }
        }

        async function saveKeys() {
            let exchange = document.getElementById('exchange').value;
            let api_key = document.getElementById('apiKey').value;
            let secret_key = document.getElementById('secretKey').value;

            let res = await fetch('/api/config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({exchange, api_key, secret_key})
            });
            let data = await res.json();
            alert(data.message || "Configuration saved successfully.");
            fetchStatus();
        }

        async function toggleBot() {
            let res = await fetch('/api/bot/toggle', {method: 'POST'});
            let data = await res.json();
            if(!res.ok) {
                alert(data.detail || "Failed to toggle bot state.");
            }
            fetchStatus();
        }

        setInterval(fetchStatus, 2000);
        setInterval(fetchLogs, 2500);
        fetchStatus();
        fetchLogs();
    </script>
</body>
</html>
"""

if os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/dashboard", response_class=HTMLResponse)
def serve_dashboard():
    if os.path.exists("frontend/index.html"):
        return FileResponse("frontend/index.html")
    return HTMLResponse(content=HTML_DASHBOARD_TEMPLATE)

class ApiKeysPayload(BaseModel):
    api_key: str
    secret_key: str
    exchange: str = "binance"

class SettingsPayload(BaseModel):
    lot_size: float
    leverage: str
    risk_pct:
