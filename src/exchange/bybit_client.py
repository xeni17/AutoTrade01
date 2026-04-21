"""
exchange/bybit_client.py - Bybit API wrapper via ccxt
"""
import ccxt
import os
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

class BybitClient:
    def __init__(self):
        testnet = os.getenv("BYBIT_TESTNET", "true").lower() == "true"
        self.exchange = ccxt.bybit({
            "apiKey": os.getenv("BYBIT_API_KEY"),
            "secret": os.getenv("BYBIT_API_SECRET"),
            "enableRateLimit": True,
            "options": {"defaultType": "future"}
        })
        if testnet:
            self.exchange.set_sandbox_mode(True)
            logger.info("Running on Bybit TESTNET")
        else:
            logger.warning("Running on Bybit LIVE")

    def get_all_usdt_pairs(self):
        markets = self.exchange.load_markets()
        return [s for s, m in markets.items() if m.get("quote") == "USDT" and m.get("active") and ":USDT" in s]

    def get_ticker(self, symbol):
        try: return self.exchange.fetch_ticker(symbol)
        except: return {}

    def get_ohlcv(self, symbol, timeframe="1h", limit=100):
        try: return self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        except: return []

    def get_order_book(self, symbol, limit=50):
        try: return self.exchange.fetch_order_book(symbol, limit)
        except: return {}

    def get_funding_rate(self, symbol):
        try: return self.exchange.fetch_funding_rate(symbol).get("fundingRate", 0.0)
        except: return 0.0

    def get_open_interest(self, symbol):
        try: return self.exchange.fetch_open_interest(symbol)
        except: return {}

    def place_order(self, symbol, side, amount, order_type="market", price=None):
        try:
            if order_type == "market":
                return self.exchange.create_market_order(symbol, side, amount)
            return self.exchange.create_limit_order(symbol, side, amount, price)
        except Exception as e:
            logger.error(f"Order error {symbol}: {e}")
            return {}

    def set_stop_loss_take_profit(self, symbol, side, sl_price, tp_price):
        try:
            self.exchange.set_trading_stop(symbol, {"stopLoss": str(sl_price), "takeProfit": str(tp_price), "positionIdx": 0})
            return True
        except: return False

    def get_positions(self):
        try: return [p for p in self.exchange.fetch_positions() if float(p.get("contracts", 0)) > 0]
        except: return []

    def get_balance(self):
        try: return float(self.exchange.fetch_balance().get("USDT", {}).get("free", 0))
        except: return 0.0
