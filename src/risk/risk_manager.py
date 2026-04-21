"""
risk/risk_manager.py - Position sizing and risk control
"""
import os
from loguru import logger

class RiskManager:
    def __init__(self, client):
        self.client = client
        self.max_positions = int(os.getenv("MAX_OPEN_POSITIONS", 5))
        self.max_pos_size = float(os.getenv("MAX_POSITION_SIZE_USDT", 100))

    def can_open_position(self, signal):
        positions = self.client.get_positions()
        if len(positions) >= self.max_positions:
            return False, f"Max positions reached ({self.max_positions})"
        if signal.symbol in [p["symbol"] for p in positions]:
            return False, f"Already in {signal.symbol}"
        if self.client.get_balance() < self.max_pos_size:
            return False, "Insufficient balance"
        if signal.strength < 0.5:
            return False, f"Signal too weak: {signal.strength:.2f}"
        return True, "OK"

    def calculate_position_size(self, signal):
        size_usdt = min(self.max_pos_size * 0.5 * (0.5 + signal.strength), self.max_pos_size)
        return size_usdt / signal.entry_price if signal.entry_price > 0 else 0

    def log_trade(self, signal, contracts, order):
        logger.info(f"TRADE: {signal.side.upper()} {signal.symbol} | Entry: {signal.entry_price} | SL: {signal.sl_price} | TP: {signal.tp_price}")
