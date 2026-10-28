import asyncio

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import WebSocket

from backend.database import initialize_database
from backend.websocket_manager import manager

from backend.api.health import router as health_router
from backend.api.market import router as market_router

from backend.services.exchange_service import get_market_snapshot
from backend.services.telemetry_service import store_snapshot

app = FastAPI(title="Mahlabahlasele 4.0")


initialize_database()

app.include_router(health_router)
app.include_router(market_router)

app.mount(
    "/static",
    StaticFiles(directory="frontend"),
    name="static"
)


@app.get("/")
async def home():
    return FileResponse("frontend/index.html")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):

    await manager.connect(websocket)

    try:
        while True:
            await asyncio.sleep(30)
    except:
        manager.disconnect(websocket)


@app.on_event("startup")
async def startup():

    async def market_loop():

        while True:

            snapshot = await get_market_snapshot()

            store_snapshot(snapshot)

            await manager.broadcast(snapshot)

            await asyncio.sleep(10)

    asyncio.create_task(market_loop())
