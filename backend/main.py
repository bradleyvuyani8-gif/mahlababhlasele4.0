import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Initialize FastAPI application
app = FastAPI(
    title="Mahlabahlasele4.0 Trading Bot",
    description="Autonomous crypto trading and telemetry server running on Termux",
    version="4.0"
)

# Enable CORS for local web terminal and frontend supervision
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import internal api routers or telemetry services safely
try:
    from backend.api.market import router as market_router
    app.include_router(market_router, prefix="/api/market", tags=["Market"])
except ImportError:
    market_router = None

try:
    from backend.services.exchange_service import get_market_snapshot
    from backend.services.telemetry_service import store_snapshot
except ImportError:
    # Fallback placeholders if modules aren't fully linked yet
    async def get_market_snapshot():
        return {"symbol": "BTC/USDT", "price": 0.0}
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
    """
    Background worker loop to fetch market snapshots and feed telemetry.
    The 'await' keyword is mandatory here because get_market_snapshot is async.
    """
    try:
        # Await the coroutine to safely unpack the dictionary snapshot
        snapshot = await get_market_snapshot()
        
        if snapshot and isinstance(snapshot, dict):
            store_snapshot(snapshot)
    except Exception as e:
        print(f"Error in market loop: {e}")


@app.on_event("startup")
async def startup_event():
    # Trigger initial market loop test on startup
    await market_loop()
