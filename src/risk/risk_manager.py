"""
risk/risk_manager.py
Controls position sizing, max exposure, and drawdown limits.
"""

import os
from loguru import logger
from src.exchange.bybit_client import BybitClient
from src.strategy.smart_money import Signal


class RiskManager:
    def __init__(self, client: BybitClient):
        self.client = client
        self.max_positions = int(os.getenv("MAX_OPEN_POSITIONS", 5))
        self.max_pos_size = float(os.getenv("MAX_POSITION_SIZE_USDT", 100))
        self.total_capital = float(os.getenv("TOTAL_CAPITAL_USDT", 500))
        self.max_daily_loss_pct = 0.05  # 5% daily max drawdown

    def can_open_position(self, signal: Signal) -> tuple[bool, str]:
        """Check if we're allowed to open a new position"""
        positions = self.client.get_positions()

        # Max positions check
        if len(positions) >= self.max_positions:
            return False, f"Max positions reached ({self.max_positions})"

        # Already in this pair?
        open_symbols = [p["symbol"] for p in positions]
        if signal.symbol in open_symbols:
            return False, f"Already have position in {signal.symbol}"

        # Balance check
        balance = self.client.get_balance()
        if balance < self.max_pos_size:
            return False, f"Insufficient balance: {balance:.2f} USDT"

        # Signal strength minimum
        if signal.strength < 0.5:
            return False, f"Signal too weak: {signal.strength:.2f}"

        return True, "OK"

    def calculate_position_size(self, signal: Signal) -> float:
        """
        Kelly-inspired sizing based on signal strength.
        Stronger signal = larger position (within limits).
        """
        base_size = self.max_pos_size * 0.5  # Start at 50% of max
        strength_multiplier = 0.5 + signal.strength  # 0.5x - 1.5x
        size_usdt = base_size * strength_multiplier
        size_usdt = min(size_usdt, self.max_pos_size)

        # Convert to contracts
        if signal.entry_price > 0:
            contracts = size_usdt / signal.entry_price
            logger.info(f"Position size: {size_usdt:.2f} USDT = {contracts:.6f} {signal.symbol}")
            return contracts
        return 0.0

    def log_trade(self, signal: Signal, contracts: float, order: dict):
        """Log trade details"""
        logger.info(
            f"\n{'='*50}\n"
            f"🚀 TRADE EXECUTED\n"
            f"Symbol  : {signal.symbol}\n"
            f"Side    : {signal.side.upper()}\n"
            f"Entry   : {signal.entry_price}\n"
            f"SL      : {signal.sl_price}\n"
            f"TP      : {signal.tp_price}\n"
            f"Size    : {contracts:.6f}\n"
            f"Strength: {signal.strength:.0%}\n"
            f"Reasons : {' | '.join(signal.reason)}\n"
            f"{'='*50}"
        )
