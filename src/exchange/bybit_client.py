"""
exchange/bybit_client.py
Handles all Bybit API interactions via ccxt
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
            "options": {
                "defaultType": "future",  # USDT Perpetual
                "adjustForTimeDifference": True,
            }
        })

        if testnet:
            self.exchange.set_sandbox_mode(True)
            logger.info("🧪 Running on Bybit TESTNET")
        else:
            logger.warning("🚨 Running on Bybit LIVE")

    def get_all_usdt_pairs(self) -> list[str]:
        """Get all active USDT perpetual pairs"""
        try:
            markets = self.exchange.load_markets()
            pairs = [
                symbol for symbol, market in markets.items()
                if market.get("quote") == "USDT"
                and market.get("active")
                and market.get("type") == "swap"
                and ":USDT" in symbol
            ]
            logger.info(f"Found {len(pairs)} USDT perpetual pairs")
            return pairs
        except Exception as e:
            logger.error(f"Error fetching pairs: {e}")
            return []

    def get_ticker(self, symbol: str) -> dict:
        """Get current ticker data"""
        try:
            return self.exchange.fetch_ticker(symbol)
        except Exception as e:
            logger.error(f"Error fetching ticker {symbol}: {e}")
            return {}

    def get_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 100) -> list:
        """Get OHLCV candlestick data"""
        try:
            return self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        except Exception as e:
            logger.error(f"Error fetching OHLCV {symbol}: {e}")
            return []

    def get_order_book(self, symbol: str, limit: int = 50) -> dict:
        """Get order book depth"""
        try:
            return self.exchange.fetch_order_book(symbol, limit)
        except Exception as e:
            logger.error(f"Error fetching order book {symbol}: {e}")
            return {}

    def get_funding_rate(self, symbol: str) -> float:
        """Get current funding rate"""
        try:
            funding = self.exchange.fetch_funding_rate(symbol)
            return funding.get("fundingRate", 0.0)
        except Exception as e:
            logger.error(f"Error fetching funding rate {symbol}: {e}")
            return 0.0

    def get_open_interest(self, symbol: str) -> dict:
        """Get open interest data"""
        try:
            oi = self.exchange.fetch_open_interest(symbol)
            return oi
        except Exception as e:
            logger.error(f"Error fetching OI {symbol}: {e}")
            return {}

    def place_order(self, symbol: str, side: str, amount: float,
                    order_type: str = "market", price: float = None) -> dict:
        """Place an order"""
        try:
            if order_type == "market":
                order = self.exchange.create_market_order(symbol, side, amount)
            else:
                order = self.exchange.create_limit_order(symbol, side, amount, price)
            logger.info(f"✅ Order placed: {side} {amount} {symbol} @ {price or 'market'}")
            return order
        except Exception as e:
            logger.error(f"Error placing order {symbol}: {e}")
            return {}

    def set_stop_loss_take_profit(self, symbol: str, side: str,
                                   sl_price: float, tp_price: float) -> bool:
        """Set SL/TP for a position"""
        try:
            position_side = "Buy" if side == "buy" else "Sell"
            self.exchange.set_trading_stop(symbol, {
                "stopLoss": str(sl_price),
                "takeProfit": str(tp_price),
                "positionIdx": 0,
            })
            logger.info(f"✅ SL/TP set for {symbol}: SL={sl_price}, TP={tp_price}")
            return True
        except Exception as e:
            logger.error(f"Error setting SL/TP {symbol}: {e}")
            return False

    def get_positions(self) -> list:
        """Get all open positions"""
        try:
            positions = self.exchange.fetch_positions()
            return [p for p in positions if float(p.get("contracts", 0)) > 0]
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []

    def get_balance(self) -> float:
        """Get available USDT balance"""
        try:
            balance = self.exchange.fetch_balance()
            return float(balance.get("USDT", {}).get("free", 0))
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            return 0.0
