import numpy as np

def calculate_fair_value_gaps(prices: list, threshold: float = 0.001):
    """
    Identifies Fair Value Gaps (FVG) from recent price action history.
    An FVG occurs when there is an imbalance (a large gap between candle 1's high/low and candle 3's low/high).
    """
    if len(prices) < 3:
        return "NEUTRAL", 0.0

    # Using the last 3 candles
    c1, c2, c3 = prices[-3], prices[-2], prices[-1]
    
    # Bullish FVG: Low of candle 3 is higher than high of candle 1
    # (Simplified for closing prices/tick sequences in simulation)
    momentum = c3 - c1
    
    if momentum > (c1 * threshold):
        return "BULLISH_FVG", momentum
    elif momentum < -(c1 * threshold):
        return "BEARISH_FVG", momentum
        
    return "NEUTRAL", 0.0

def evaluate_advanced_strategy(price_history: list, current_balance: float, risk_pct: float):
    """
    Evaluates market conditions using institutional price action logic 
    and calculates position sizing based on risk percentage.
    """
    if len(price_history) < 5:
        return {"signal": "HOLD", "size": 0.0}

    signal, strength = calculate_fair_value_gaps(price_history)
    risk_capital = current_balance * (risk_pct / 100.0)

    if signal == "BULLISH_FVG":
        return {
            "signal": "BUY",
            "confidence": "HIGH",
            "risk_allocated": risk_capital,
            "reason": "Bullish Fair Value Gap imbalance detected."
        }
    elif signal == "BEARISH_FVG":
        return {
            "signal": "SELL",
            "confidence": "HIGH",
            "risk_allocated": risk_capital,
            "reason": "Bearish Fair Value Gap imbalance detected."
        }
        
    return {"signal": "HOLD", "confidence": "LOW", "risk_allocated": 0.0, "reason": "Consolidation / No FVG."}
