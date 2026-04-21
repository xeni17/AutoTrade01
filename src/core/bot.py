"""
core/bot.py - Main orchestrator with Telegram, Trailing Stop & Daily Dashboard
"""
import time
import os
from datetime import datetime
from loguru import logger
from dotenv import load_dotenv

from src.exchange.bybit_client import BybitClient
from src.scanner.pair_scanner import PairScanner
from src.strategy.smart_money import SmartMoneyStrategy
from src.strategy.trailing_stop import TrailingStopManager
from src.risk.risk_manager import RiskManager
from src.utils.telegram import (
    notify_signal, notify_trade_open, notify_trade_close,
    send_daily_dashboard, notify_bot_start, notify_error
)

load_dotenv()


class SmartMoneyBot:
    def __init__(self):
        self.mode = os.getenv("BOT_MODE", "paper")
        self.scan_interval = int(os.getenv("SCAN_INTERVAL_SECONDS", 60))
        logger.info(f"🤖 SmartMoneyBot starting in {self.mode.upper()} mode")
        self.client = BybitClient()
        self.scanner = PairScanner(self.client)
        self.strategy = SmartMoneyStrategy(self.client)
        self.trailing = TrailingStopManager()
        self.risk = RiskManager(self.client)
        self.watchlist = []
        self.last_scan = 0
        self.scan_every = 300
        self.daily_stats = self._reset_daily_stats()
        self.last_dashboard_date = None

    def run(self):
        logger.info("Bot loop started")
        notify_bot_start(self.mode, 0)
        while True:
            try:
                self._check_daily_dashboard()
                self._cycle()
                time.sleep(self.scan_interval)
            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                break
            except Exception as e:
                logger.error(f"Loop error: {e}")
                notify_error(str(e))
                time.sleep(10)

    def _cycle(self):
        now = time.time()
        if not self.watchlist or (now - self.last_scan) > self.scan_every:
            logger.info("Refreshing pair watchlist...")
            df = self.scanner.scan()
            if not df.empty:
                self.watchlist = df["symbol"].tolist()
                self.last_scan = now
        if not self.watchlist:
            return
        self._update_trailing_stops()
        for symbol in self.watchlist:
            signal = self.strategy.analyze(symbol)
            if signal.side == "none":
                continue
            notify_signal(signal)
            allowed, reason = self.risk.can_open_position(signal)
            if not allowed:
                logger.info(f"Skipping {symbol}: {reason}")
                continue
            self._execute(signal)

    def _execute(self, signal):
        contracts = self.risk.calculate_position_size(signal)
        if contracts <= 0:
            return
        if self.mode == "paper":
            logger.info(f"[PAPER] {signal.side.upper()} {contracts:.6f} {signal.symbol} @ {signal.entry_price}")
            notify_trade_open(signal, contracts, mode="paper")
            self.trailing.register(signal.symbol, signal.side, signal.entry_price, signal.sl_price)
            self.daily_stats["total_trades"] += 1
            return
        order = self.client.place_order(signal.symbol, signal.side, contracts, "market")
        if order:
            self.client.set_stop_loss_take_profit(signal.symbol, signal.side, signal.sl_price, signal.tp_price)
            self.trailing.register(signal.symbol, signal.side, signal.entry_price, signal.sl_price)
            notify_trade_open(signal, contracts, mode="live")
            self.risk.log_trade(signal, contracts, order)
            self.daily_stats["total_trades"] += 1

    def _update_trailing_stops(self):
        positions = self.client.get_positions()
        for pos in positions:
            symbol = pos.get("symbol")
            ticker = self.client.get_ticker(symbol)
            if not ticker:
                continue
            current_price = float(ticker.get("last", 0))
            self.trailing.update(symbol, current_price, self.client)
            if self.trailing.check_sl_hit(symbol, current_price):
                logger.info(f"Trailing SL hit: {symbol}")
                self.trailing.remove(symbol)

    def _check_daily_dashboard(self):
        now = datetime.now()
        today = now.date()
        if now.hour == 7 and now.minute < 2 and self.last_dashboard_date != today:
            logger.info("Sending daily dashboard...")
            self.last_dashboard_date = today
            balance = self.client.get_balance()
            positions = self.client.get_positions()
            self.daily_stats["balance"] = balance
            self.daily_stats["open_positions"] = positions
            send_daily_dashboard(self.daily_stats)
            self.daily_stats = self._reset_daily_stats()

    def _reset_daily_stats(self):
        return {
            "total_trades": 0, "win_trades": 0, "loss_trades": 0,
            "total_pnl": 0.0, "best_trade": 0.0, "worst_trade": 0.0,
            "balance": 0.0, "open_positions": []
        }
