import json
import os

class PersistentMemory:
    def __init__(self, filename="mahlabahlasele_memory.json"):
        shared_dir = os.path.expanduser("~/storage/shared/Download")
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
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading memory: {e}")
        return {
            "total_trades": 0,
            "successful_trades": 0,
            "failed_trades": 0,
            "mistakes_log": [],
            "learned_weights": {}
        }

    def save_memory(self):
        try:
            with open(self.filepath, "w") as f:
                json.dump(self.memory, f, indent=4)
        except Exception as e:
            print(f"Error saving memory: {e}")

    def record_trade_outcome(self, trade_type, pnl, market_conditions):
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

bot_memory = PersistentMemory()

def evaluate_memory_guardrail(current_market_data):
    mistakes_log = bot_memory.memory.get("mistakes_log", [])
    current_trend = current_market_data.get("trend", "neutral")
    current_volatility = current_market_data.get("volatility", "normal")
    
    for mistake in mistakes_log:
        past_conditions = mistake.get("conditions", {})
        if (past_conditions.get("trend") == current_trend and 
            past_conditions.get("volatility") == current_volatility):
            return "HOLD"
    return "EXECUTE"

def execute_strategy_pipeline(price_history: list, current_balance: float, risk_pct: float, exchange: str):
    if len(price_history) < 3:
        return {"action": "HOLD", "reason": "Insufficient market data points."}
    
    market_snapshot = {"trend": "neutral", "volatility": "normal"}
    if evaluate_memory_guardrail(market_snapshot) == "HOLD":
        return {"action": "HOLD", "reason": "Blocked by persistent memory guardrail."}
        
    allocated_risk = current_balance * (risk_pct / 100.0)
    c1, c2, c3 = price_history[-3], price_history[-2], price_history[-1]
    momentum = c3 - c1
    
    if momentum > (c1 * 0.0001):
        return {
            "action": "BUY",
            "symbol": "BTC/USDT",
            "allocated_risk": allocated_risk,
            "reason": f"Bullish momentum detected on {exchange.upper()}."
        }
    elif momentum < -(c1 * 0.0001):
        return {
            "action": "SELL",
            "symbol": "BTC/USDT",
            "allocated_risk": allocated_risk,
            "reason": f"Bearish momentum detected on {exchange.upper()}."
        }
        
    return {"action": "HOLD", "reason": "Consolidation detected."}
