"""
strategy/trailing_stop.py - Trailing stop manager
"""
import os
from loguru import logger
from src.utils.telegram import notify_trailing_stop_update
from dotenv import load_dotenv

load_dotenv()


class TrailingStopManager:
    def __init__(self):
        self.enabled = os.getenv("TRAILING_STOP", "true").lower() == "true"
        self.trail_pct = float(os.getenv("TRAILING_STOP_PERCENT", 1.5)) / 100
        # Track highest/lowest price per position
        # { symbol: { "side": "buy"/"sell", "peak": float, "current_sl": float } }
        self.positions = {}

    def register(self, symbol: str, side: str, entry: float, initial_sl: float):
        """Register a new position for trailing"""
        self.positions[symbol] = {
            "side": side,
            "peak": entry,
            "current_sl": initial_sl,
            "entry": entry
        }
        logger.info(f"Trailing stop registered: {symbol} {side} entry={entry} sl={initial_sl}")

    def update(self, symbol: str, current_price: float, client) -> float | None:
        """
        Update trailing stop based on current price.
        Returns new SL price if updated, else None.
        """
        if not self.enabled or symbol not in self.positions:
            return None

        pos = self.positions[symbol]
        side = pos["side"]
        peak = pos["peak"]
        current_sl = pos["current_sl"]

        if side == "buy":
            # Price moved up → trail SL up
            if current_price > peak:
                new_peak = current_price
                new_sl = round(current_price * (1 - self.trail_pct), 4)

                if new_sl > current_sl:
                    self.positions[symbol]["peak"] = new_peak
                    self.positions[symbol]["current_sl"] = new_sl
                    logger.info(f"Trailing SL updated: {symbol} SL {current_sl} → {new_sl}")
                    notify_trailing_stop_update(symbol, new_sl)

                    # Update on exchange
                    try:
                        client.set_stop_loss_take_profit(symbol, "buy", new_sl, None)
                    except Exception as e:
                        logger.error(f"Failed to update SL on exchange: {e}")

                    return new_sl

        elif side == "sell":
            # Price moved down → trail SL down
            if current_price < peak:
                new_peak = current_price
                new_sl = round(current_price * (1 + self.trail_pct), 4)

                if new_sl < current_sl:
                    self.positions[symbol]["peak"] = new_peak
                    self.positions[symbol]["current_sl"] = new_sl
                    logger.info(f"Trailing SL updated: {symbol} SL {current_sl} → {new_sl}")
                    notify_trailing_stop_update(symbol, new_sl)

                    try:
                        client.set_stop_loss_take_profit(symbol, "sell", new_sl, None)
                    except Exception as e:
                        logger.error(f"Failed to update SL on exchange: {e}")

                    return new_sl

        return None

    def remove(self, symbol: str):
        """Remove position from trailing manager"""
        if symbol in self.positions:
            del self.positions[symbol]
            logger.info(f"Trailing stop removed: {symbol}")

    def check_sl_hit(self, symbol: str, current_price: float) -> bool:
        """Check if SL has been hit"""
        if symbol not in self.positions:
            return False
        pos = self.positions[symbol]
        if pos["side"] == "buy" and current_price <= pos["current_sl"]:
            return True
        if pos["side"] == "sell" and current_price >= pos["current_sl"]:
            return True
        return False
