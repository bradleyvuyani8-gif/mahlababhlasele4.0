"""
Mahlabahlasele 4.0 - backend

Run from the repo root (the folder that contains backend/ and frontend/):
    uvicorn backend.main:app --host 127.0.0.1 --port 8000

Endpoints
    GET  /dashboard      the dashboard page (frontend/index.html)
    GET  /api/status     live data the dashboard polls every 2 seconds
    POST /api/keys       choose exchange + mode (paper / testnet / live), save keys
    POST /api/risk       update lot size, leverage, max risk per trade
    POST /api/engine     start or stop automated trading

Modes
    paper   simulated money, no keys needed (default, safe)
    testnet exchange sandbox with fake money (needs testnet keys)
    live    real money (needs real keys)
"""

import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path

import ccxt
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
INDEX_FILE = BASE_DIR / "frontend" / "index.html"

SYMBOL = "BTC/USDT"
ALLOWED_EXCHANGES = ("binance", "bybit")
PAPER_START_BALANCE = 1000.0
LOOP_SECONDS = 3
CANDLE_REFRESH_SECONDS = 30
BALANCE_REFRESH_SECONDS = 15
COOLDOWN_SECONDS = 60

# ---------------------------------------------------------------------------
# Shared state (lives in memory; API keys are never written to disk or logs)
# ---------------------------------------------------------------------------

state = {
    "exchange": "binance",
    "mode": "paper",
    "connected": False,
    "engine_on": False,
    "price": None,
    "signal": "Waiting for data",
    "atr": None,
    "paper_balance": PAPER_START_BALANCE,
    "live_balance": None,
    "position": None,
    "realized_pnl": 0.0,
    "lot": 0.15,
    "leverage": 20,
    "risk": 2.5,
    "last_update": None,
    "last_error": None,
    "cooldown_until": 0.0,
    "logs": [],
}

clients = {"public": None, "trade": None}
timers = {"candles": 0.0, "balance": 0.0}


def log(message):
    stamp = time.strftime("%H:%M:%S")
    state["logs"].append(stamp + "  " + message)
    state["logs"] = state["logs"][-30:]
    print(stamp, message, flush=True)


def fail(message, status=400):
    return JSONResponse({"ok": False, "error": message}, status_code=status)


# ---------------------------------------------------------------------------
# Exchange helpers (ccxt is synchronous, so these run in a worker thread)
# ---------------------------------------------------------------------------


def make_exchange(name, key=None, secret=None, sandbox=False):
    exchange_class = getattr(ccxt, name)
    config = {"enableRateLimit": True}
    if key and secret:
        config["apiKey"] = key
        config["secret"] = secret
    exchange = exchange_class(config)
    if sandbox:
        exchange.set_sandbox_mode(True)
    return exchange


def fetch_price_sync():
    ticker = clients["public"].fetch_ticker(SYMBOL)
    price = ticker.get("last") or ticker.get("close")
    if price is None:
        price = (ticker.get("info") or {}).get("price")
    return float(price) if price is not None else None


def fetch_candles_sync():
    return clients["public"].fetch_ohlcv(SYMBOL, "1h", limit=60)


def fetch_usdt_balance_sync(exchange):
    balance = exchange.fetch_balance()
    total = balance.get("total") or {}
    return float(total.get("USDT") or 0.0)


def analyse(candles):
    """Simple trend read: fast vs slow moving average, plus ATR for stop size."""
    if not candles or len(candles) < 31:
        return "Waiting for data", None
    closes = [c[4] for c in candles]
    fast = sum(closes[-10:]) / 10
    slow = sum(closes[-30:]) / 30
    last = closes[-1]

    true_ranges = []
    for i in range(len(candles) - 14, len(candles)):
        high = candles[i][2]
        low = candles[i][3]
        prev_close = candles[i - 1][4]
        true_ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    atr = sum(true_ranges) / len(true_ranges)

    if fast > slow and last > fast:
        return "Bullish Momentum", atr
    if fast < slow and last < fast:
        return "Bearish Momentum", atr
    return "Neutral", atr


def current_balance():
    if state["mode"] == "paper":
        return state["paper_balance"]
    return state["live_balance"] or 0.0


def active_pnl():
    position = state["position"]
    if position and state["price"]:
        return (state["price"] - position["entry"]) * position["qty"]
    return 0.0


# ---------------------------------------------------------------------------
# Trading logic (long only, ATR stop, 2R target)
# ---------------------------------------------------------------------------


async def open_position(price):
    balance = current_balance()
    if balance <= 0 or not state["atr"]:
        return

    stop_distance = 1.5 * state["atr"]
    risk_amount = balance * state["risk"] / 100.0
    qty = min(state["lot"], risk_amount / stop_distance)

    leverage = state["leverage"] if state["mode"] == "paper" else 1
    max_notional = balance * 0.95 * leverage
    qty = min(qty, max_notional / price)

    trade = clients["trade"]
    if state["mode"] == "paper":
        qty = round(qty, 6)
    else:
        qty = float(trade.amount_to_precision(SYMBOL, qty))
    if qty <= 0:
        log("Skipped entry: calculated size is zero.")
        state["cooldown_until"] = time.time() + COOLDOWN_SECONDS
        return

    if state["mode"] != "paper":
        await asyncio.to_thread(trade.create_order, SYMBOL, "market", "buy", qty)

    state["position"] = {
        "side": "long",
        "qty": qty,
        "entry": price,
        "stop": price - stop_distance,
        "take": price + 2 * stop_distance,
    }
    log("Opened long %s BTC at %.2f (stop %.2f, target %.2f) [%s]" % (
        qty, price, price - stop_distance, price + 2 * stop_distance, state["mode"]))


async def close_position(price, reason):
    position = state["position"]
    if not position:
        return
    if state["mode"] != "paper":
        await asyncio.to_thread(
            clients["trade"].create_order, SYMBOL, "market", "sell", position["qty"])

    pnl = (price - position["entry"]) * position["qty"]
    if state["mode"] == "paper":
        state["paper_balance"] += pnl
    state["realized_pnl"] += pnl
    state["position"] = None
    state["cooldown_until"] = time.time() + COOLDOWN_SECONDS
    log("Closed long at %.2f (%s). PnL %+.2f" % (price, reason, pnl))


async def engine_step():
    price = state["price"]
    if price is None:
        return

    position = state["position"]
    if position:
        # Open positions are always protected, even if the engine is switched off.
        if price <= position["stop"]:
            await close_position(price, "stop loss")
        elif price >= position["take"]:
            await close_position(price, "take profit")
        return

    if not state["engine_on"]:
        return
    if time.time() < state["cooldown_until"]:
        return
    if state["signal"] == "Bullish Momentum":
        await open_position(price)


# ---------------------------------------------------------------------------
# Background worker: keeps the dashboard data live
# ---------------------------------------------------------------------------


async def worker():
    while True:
        try:
            price = await asyncio.to_thread(fetch_price_sync)
            if price is not None:
                state["price"] = price
                state["connected"] = True
                state["last_update"] = time.time()
                state["last_error"] = None
        except Exception as error:
            state["connected"] = False
            state["last_error"] = "Price feed: " + type(error).__name__
            print("Price feed error:", error, flush=True)

        now = time.time()

        if now - timers["candles"] > CANDLE_REFRESH_SECONDS:
            try:
                candles = await asyncio.to_thread(fetch_candles_sync)
                state["signal"], state["atr"] = analyse(candles)
                timers["candles"] = now
            except Exception as error:
                print("Candle error:", error, flush=True)

        if clients["trade"] and now - timers["balance"] > BALANCE_REFRESH_SECONDS:
            try:
                state["live_balance"] = await asyncio.to_thread(
                    fetch_usdt_balance_sync, clients["trade"])
                timers["balance"] = now
            except Exception as error:
                state["last_error"] = "Balance: " + type(error).__name__
                print("Balance error:", error, flush=True)

        try:
            await engine_step()
        except Exception as error:
            state["last_error"] = "Engine: " + type(error).__name__
            log("Engine error: " + type(error).__name__ + " - " + str(error)[:120])
            state["cooldown_until"] = time.time() + COOLDOWN_SECONDS

        await asyncio.sleep(LOOP_SECONDS)


@asynccontextmanager
async def lifespan(app):
    clients["public"] = make_exchange(state["exchange"])
    task = asyncio.create_task(worker())
    log("Server started. Mode: paper. Engine: inactive.")
    yield
    task.cancel()


app = FastAPI(title="Mahlabahlasele 4.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class KeysIn(BaseModel):
    exchange: str = "binance"
    mode: str = "paper"
    api_key: str = ""
    secret: str = ""
    confirm_live: bool = False


class RiskIn(BaseModel):
    lot: float
    leverage: int
    risk: float


class EngineIn(BaseModel):
    enabled: bool


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/")
async def root():
    return RedirectResponse("/dashboard")


@app.get("/dashboard")
async def dashboard():
    if not INDEX_FILE.exists():
        return Response("frontend/index.html not found", status_code=404)
    return FileResponse(INDEX_FILE)


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


@app.get("/api/status")
async def status():
    position = state["position"]
    return {
        "engine": "ACTIVE" if state["engine_on"] else "INACTIVE",
        "engine_on": state["engine_on"],
        "exchange": state["exchange"],
        "mode": state["mode"],
        "connected": state["connected"],
        "balance": current_balance(),
        "open_positions": 1 if position else 0,
        "position": position,
        "active_pnl": active_pnl(),
        "realized_pnl": state["realized_pnl"],
        "pair": SYMBOL,
        "price": state["price"],
        "signal": state["signal"],
        "lot": state["lot"],
        "leverage": state["leverage"],
        "risk": state["risk"],
        "last_update": state["last_update"],
        "last_error": state["last_error"],
        "logs": state["logs"][-12:],
    }


@app.post("/api/keys")
async def save_keys(body: KeysIn):
    name = body.exchange.lower()
    mode = body.mode.lower()

    if name not in ALLOWED_EXCHANGES:
        return fail("Unsupported exchange.")
    if mode not in ("paper", "testnet", "live"):
        return fail("Mode must be paper, testnet or live.")
    if mode == "live" and not body.confirm_live:
        return fail("Live mode needs confirmation.")
    if state["position"]:
        return fail("Wait for the open position to close before switching accounts.")

    state["engine_on"] = False

    if mode == "paper":
        clients["public"] = make_exchange(name)
        clients["trade"] = None
        state.update(exchange=name, mode="paper", live_balance=None)
        timers["candles"] = 0.0
        log("Switched to paper trading on " + name + ".")
        return {"ok": True, "message": "Paper trading ready. Simulated balance in use."}

    if not body.api_key.strip() or not body.secret.strip():
        return fail("Enter both the API key and the secret key.")

    try:
        trade = make_exchange(
            name, body.api_key.strip(), body.secret.strip(), sandbox=(mode == "testnet"))
        balance = await asyncio.to_thread(fetch_usdt_balance_sync, trade)
        await asyncio.to_thread(trade.load_markets)
    except Exception as error:
        return fail("Authorization failed (" + type(error).__name__ + "). Check the keys, "
                    "the mode, and that trading is enabled on the key.")

    clients["public"] = make_exchange(name)
    clients["trade"] = trade
    state.update(exchange=name, mode=mode, live_balance=balance)
    timers["candles"] = 0.0
    timers["balance"] = time.time()
    log("Keys authorized on %s (%s). Balance %.2f USDT." % (name, mode, balance))
    return {"ok": True, "message": "Keys authorized. Balance loaded from the exchange."}


@app.post("/api/risk")
async def update_risk(body: RiskIn):
    if not (0.0001 <= body.lot <= 1.0):
        return fail("Lot size must be between 0.0001 and 1 BTC.")
    if not (1 <= body.leverage <= 125):
        return fail("Leverage must be between 1 and 125.")
    if not (0.1 <= body.risk <= 10.0):
        return fail("Max risk per trade must be between 0.1 and 10 percent.")
    state.update(lot=body.lot, leverage=body.leverage, risk=body.risk)
    log("Risk updated: lot %s BTC, leverage %sx, risk %s%%." % (body.lot, body.leverage, body.risk))
    return {"ok": True, "message": "Risk parameters updated."}


@app.post("/api/engine")
async def set_engine(body: EngineIn):
    if body.enabled:
        if state["mode"] != "paper" and not clients["trade"]:
            return fail("Authorize your keys before starting.")
        if state["price"] is None:
            return fail("No market data yet. Try again in a few seconds.")
    state["engine_on"] = body.enabled
    log("Automated trading " + ("STARTED" if body.enabled else "STOPPED") + " [" + state["mode"] + "].")
    return {"ok": True, "message": "Engine " + ("started." if body.enabled else "stopped.")}
