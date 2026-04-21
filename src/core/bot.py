"""
core/bot.py - Main orchestrator
"""
import time
import os
from loguru import logger
from dotenv import load_dotenv
from src.exchange.bybit_client import BybitClient
from src.scanner.pair_scanner import PairScanner
from src.strategy.smart_money import SmartMoneyStrategy
from src.risk.risk_manager import RiskManager

load_dotenv()

class SmartMoneyBot:
    def __init__(self):
        self.mode = os.getenv("BOT_MODE", "paper")
        self.scan_interval = int(os.getenv("SCAN_INTERVAL_SECONDS", 60))
        logger.info(f"Robot SmartMoneyBot starting in {self.mode.upper()} mode")
        self.client = BybitClient()
        self.scanner = PairScanner(self.client)
        self.strategy = SmartMoneyStrategy(self.client)
        self.risk = RiskManager(self.client)
        self.watchlist = []
        self.last_scan = 0
        self.scan_every = 300

    def run(self):
        logger.info("Bot loop started")
        while True:
            try:
                self._cycle()
                time.sleep(self.scan_interval)
            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                break
            except Exception as e:
                logger.error(f"Loop error: {e}")
                time.sleep(10)

    def _cycle(self):
        now = time.time()
        if not self.watchlist or (now - self.last_scan) > self.scan_every:
            logger.info("Refreshing pair watchlist...")
            df = self.scanner.scan()
            if not df.empty:
                self.watchlist = df["symbol"].tolist()
                self.last_scan = now

        for symbol in self.watchlist:
            signal = self.strategy.analyze(symbol)
            if signal.side == "none":
                continue
            logger.info(f"Signal: {signal.side.upper()} {symbol} (strength: {signal.strength:.0%})")
            allowed, reason = self.risk.can_open_position(signal)
            if not allowed:
                continue
            self._execute(signal)

    def _execute(self, signal):
        contracts = self.risk.calculate_position_size(signal)
        if contracts <= 0:
            return
        if self.mode == "paper":
            logger.info(f"[PAPER] Would {signal.side.upper()} {contracts:.6f} {signal.symbol} @ {signal.entry_price}")
            return
        order = self.client.place_order(signal.symbol, signal.side, contracts, "market")
        if order:
            self.client.set_stop_loss_take_profit(signal.symbol, signal.side, signal.sl_price, signal.tp_price)
            self.risk.log_trade(signal, contracts, order)
