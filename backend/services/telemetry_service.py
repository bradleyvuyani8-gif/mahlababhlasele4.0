import asyncio
from typing import Dict, Any, Optional
from backend.services.exchange_service import ExchangeService

class TelemetryService:
    def __init__(self):
        self.active_exchange_service: Optional[ExchangeService] = None

    def set_exchange(self, service: ExchangeService):
        self.active_exchange_service = service

    async def get_live_status(self) -> Dict[str, Any]:
        if not self.active_exchange_service:
            return {
                "status": "IDLE",
                "telemetry_status": "Disconnected",
                "balance": 0.0,
                "message": "API keys not configured."
            }

        success, balance, raw_data = await asyncio.to_thread(
            self.active_exchange_service.fetch_account_data
        )

        if success:
            return {
                "status": "ACTIVE",
                "telemetry_status": "Connected",
                "balance": balance,
                "exchange": self.active_exchange_service.exchange.upper(),
                "details": raw_data
            }
        else:
            return {
                "status": "ERROR",
                "telemetry_status": "Authentication Failed",
                "balance": 0.0,
                "message": raw_data.get("error", "Handshake rejected.")
            }
