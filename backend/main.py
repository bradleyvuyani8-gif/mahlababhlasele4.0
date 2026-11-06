from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os

from backend.database import init_db, get_db
from backend.config import RiskParameters
from backend.services.exchange_service import ExchangeService
from backend.services.telemetry_service import TelemetryService

app = FastAPI(title="Mahlabahlasele 4.0", version="4.0.0")

telemetry = TelemetryService()

@app.on_event("startup")
def startup_event():
    init_db()
    # Restore active credentials from DB if present
    with get_db() as conn:
        row = conn.execute("SELECT exchange, api_key, secret_key, testnet FROM api_credentials LIMIT 1").fetchone()
        if row:
            service = ExchangeService(row["exchange"], row["api_key"], row["secret_key"], bool(row["testnet"]))
            telemetry.set_exchange(service)

class CredentialsPayload(BaseModel):
    exchange: str
    api_key: str
    secret_key: str
    testnet: bool = True

@app.post("/api/auth/configure")
def configure_keys(payload: CredentialsPayload):
    service = ExchangeService(payload.exchange, payload.api_key, payload.secret_key, payload.testnet)
    success, balance, error_data = service.fetch_account_data()
    
    if not success:
        raise HTTPException(status_code=400, detail=f"Handshake failed: {error_data}")

    with get_db() as conn:
        conn.execute("DELETE FROM api_credentials")
        conn.execute(
            "INSERT INTO api_credentials (exchange, api_key, secret_key, testnet) VALUES (?, ?, ?, ?)",
            (payload.exchange, payload.api_key, payload.secret_key, int(payload.testnet))
        )
        conn.commit()

    telemetry.set_exchange(service)
    return {"status": "success", "balance": balance, "exchange": payload.exchange.upper()}

@app.get("/api/telemetry")
async def fetch_telemetry():
    return await telemetry.get_live_status()

@app.post("/api/risk/update")
def update_risk(params: RiskParameters):
    with get_db() as conn:
        conn.execute("DELETE FROM risk_settings")
        conn.execute(
            "INSERT INTO risk_settings (id, lot_size, leverage, max_risk_per_trade) VALUES (1, ?, ?, ?)",
            (params.lot_size, params.leverage, params.max_risk_per_trade)
        )
        conn.commit()
    return {"status": "success", "risk_parameters": params.dict()}

# Serve Frontend static files
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(frontend_path, "index.html"))
