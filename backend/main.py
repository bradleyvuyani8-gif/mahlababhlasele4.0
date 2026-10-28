import asyncio
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI(
    title="Mahlabahlasele4.0 Trading Bot",
    description="Autonomous crypto trading and telemetry server running on Termux",
    version="4.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")

    @app.get("/dashboard")
    def serve_dashboard():
        if os.path.exists("frontend/index.html"):
            return FileResponse("frontend/index.html")
        return {"error": "index.html not found"}

try:
    from backend.api.market import router as market_router
    app.include_router(market_router, prefix="/api/market", tags=["Market"])
except ImportError:
    market_router = None

try:
    from backend.services.exchange_service import get_market_snapshot
    from backend.services.telemetry_service import store_snapshot
except ImportError:
    async def get_market_snapshot():
        return {"symbol": "BTC/USDT", "ticker": {"price": 0.0}}
    def store_snapshot(snap):
        pass

@app.get("/")
def read_root():
    return {
        "status": "online",
        "bot": "Mahlabahlasele4.0",
        "environment": "Termux Android"
    }

async def market_loop():
    try:
        snapshot = await get_market_snapshot()
        if snapshot and isinstance(snapshot, dict):
            ticker = snapshot.get("ticker", {})
            print(f"Market loop data fetched successfully: {ticker}")
            store_snapshot(snapshot)
    except Exception as e:
        print(f"Error in market loop: {e}")

@app.on_event("startup")
async def startup_event():
    await market_loop()
