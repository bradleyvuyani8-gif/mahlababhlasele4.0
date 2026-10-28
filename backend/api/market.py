from fastapi import APIRouter
from backend.services.exchange_service import get_market_snapshot

router = APIRouter()


@router.get("/market")
async def market():

    return await get_market_snapshot()
