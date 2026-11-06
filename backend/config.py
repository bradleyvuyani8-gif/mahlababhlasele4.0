import os
from enum import Enum
from pydantic import BaseModel, Field, field_validator

class ExchangeType(str, Enum):
    BINANCE = "binance"
    BYBIT = "bybit"
    ALPACA = "alpaca"

class AppConfig:
    HOST = "127.0.0.1"
    PORT = 8000
    DB_PATH = os.path.join(os.path.dirname(__file__), "trading_bot.db")
    DEBUG = False

class RiskParameters(BaseModel):
    lot_size: float = Field(..., gt=0.0, description="Lot size must exceed zero.")
    leverage: int = Field(..., ge=1, le=125, description="Leverage multiplier between 1x and 125x.")
    max_risk_per_trade: float = Field(..., gt=0.0, le=10.0, description="Max risk percentage between 0.1% and 10.0%.")

    @field_validator("max_risk_per_trade")
    def validate_risk(cls, v: float) -> float:
        return round(v, 2)
