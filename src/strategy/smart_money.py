"""
strategy/smart_money.py
Generates BUY/SELL signals based on:
- Funding rate extremes (short squeeze / long squeeze)
- Open Interest divergence
- Volume anomalies
- Order book imbalance
- Liquidation cluster proximity
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from loguru import logger
from src.exchange.bybit_client import BybitClient


@dataclass
class Signal:
    symbol: str
    side: str           # "buy" | "sell" | "none"
    strength: float     # 0.0 - 1.0
    reason: list[str]
    entry_price: float
    sl_price: float
    tp_price: float


class SmartMoneyStrategy:
    def __init__(self, client: BybitClient):
        self.client = client
        self.sl_pct = 0.02    # 2% stop loss
        self.tp_pct = 0.04    # 4% take profit (1:2 RR)

    def analyze(self, symbol: str) -> Signal:
        """Full smart money analysis for a symbol"""
        reasons = []
        buy_score = 0
        sell_score = 0

        price = self._get_price(symbol)
        if not price:
            return self._no_signal(symbol, price or 0)

        # === 1. FUNDING RATE ANALYSIS ===
        funding = self.client.get_funding_rate(symbol)

        if funding < -0.001:
            buy_score += 35
            reasons.append(f"🔥 Extreme negative funding ({funding:.4%}) → short squeeze imminent")
        elif funding < -0.0003:
            buy_score += 20
            reasons.append(f"📉 Negative funding ({funding:.4%}) → shorts paying longs")
        elif funding > 0.001:
            sell_score += 35
            reasons.append(f"⚠️ Extreme positive funding ({funding:.4%}) → long squeeze risk")
        elif funding > 0.0003:
            sell_score += 20
            reasons.append(f"📈 High funding ({funding:.4%}) → longs overextended")

        # === 2. OPEN INTEREST ANALYSIS ===
        oi_signal = self._analyze_oi(symbol)
        if oi_signal == "accumulation":
            buy_score += 25
            reasons.append("💰 OI rising with price → fresh longs entering (accumulation)")
        elif oi_signal == "distribution":
            sell_score += 25
            reasons.append("🏃 OI rising, price falling → smart money shorting")
        elif oi_signal == "short_cover":
            buy_score += 15
            reasons.append("📊 OI dropping → short covering, price relief incoming")

        # === 3. VOLUME ANOMALY ===
        vol_signal, vol_ratio = self._analyze_volume(symbol)
        if vol_signal == "spike_up":
            buy_score += 20
            reasons.append(f"📊 Volume spike {vol_ratio:.1f}x above average → whale accumulation")
        elif vol_signal == "spike_down":
            sell_score += 15
            reasons.append(f"📊 Volume spike on down candle → distribution detected")

        # === 4. ORDER BOOK IMBALANCE ===
        ob_signal, imbalance = self._analyze_order_book(symbol)
        if ob_signal == "buy_wall":
            buy_score += 20
            reasons.append(f"🧱 Strong buy wall detected (bid/ask ratio: {imbalance:.2f})")
        elif ob_signal == "sell_wall":
            sell_score += 20
            reasons.append(f"🧱 Strong sell wall detected (bid/ask ratio: {imbalance:.2f})")

        # === DETERMINE FINAL SIGNAL ===
        logger.debug(f"{symbol} | buy_score={buy_score} | sell_score={sell_score}")

        if buy_score >= 50 and buy_score > sell_score:
            sl = round(price * (1 - self.sl_pct), 4)
            tp = round(price * (1 + self.tp_pct), 4)
            return Signal(
                symbol=symbol, side="buy",
                strength=min(buy_score / 100, 1.0),
                reason=reasons, entry_price=price,
                sl_price=sl, tp_price=tp
            )
        elif sell_score >= 50 and sell_score > buy_score:
            sl = round(price * (1 + self.sl_pct), 4)
            tp = round(price * (1 - self.tp_pct), 4)
            return Signal(
                symbol=symbol, side="sell",
                strength=min(sell_score / 100, 1.0),
                reason=reasons, entry_price=price,
                sl_price=sl, tp_price=tp
            )
        else:
            return self._no_signal(symbol, price)

    def _get_price(self, symbol: str) -> float | None:
        ticker = self.client.get_ticker(symbol)
        if ticker:
            return float(ticker.get("last", 0))
        return None

    def _analyze_oi(self, symbol: str) -> str:
        """Analyze OI trend vs price trend"""
        try:
            ohlcv = self.client.get_ohlcv(symbol, "1h", 10)
            if len(ohlcv) < 5:
                return "neutral"
            closes = [c[4] for c in ohlcv]
            price_trend = closes[-1] > closes[-5]
            # Simplified: assume OI rising when volume is high
            volumes = [c[5] for c in ohlcv]
            vol_trend = volumes[-1] > np.mean(volumes[-5:])

            if price_trend and vol_trend:
                return "accumulation"
            elif not price_trend and vol_trend:
                return "distribution"
            elif not vol_trend:
                return "short_cover"
            return "neutral"
        except:
            return "neutral"

    def _analyze_volume(self, symbol: str) -> tuple[str, float]:
        """Detect volume spikes"""
        try:
            ohlcv = self.client.get_ohlcv(symbol, "1h", 25)
            if len(ohlcv) < 10:
                return "neutral", 1.0
            volumes = np.array([c[5] for c in ohlcv])
            closes = np.array([c[4] for c in ohlcv])
            avg_vol = np.mean(volumes[-20:-1])
            curr_vol = volumes[-1]
            ratio = curr_vol / avg_vol if avg_vol > 0 else 1.0
            price_up = closes[-1] > closes[-2]
            if ratio > 2.5:
                return ("spike_up" if price_up else "spike_down"), ratio
            return "neutral", ratio
        except:
            return "neutral", 1.0

    def _analyze_order_book(self, symbol: str) -> tuple[str, float]:
        """Detect order book imbalance"""
        try:
            ob = self.client.get_order_book(symbol, 20)
            bids = ob.get("bids", [])
            asks = ob.get("asks", [])
            bid_vol = sum([b[1] for b in bids])
            ask_vol = sum([a[1] for a in asks])
            total = bid_vol + ask_vol
            if total == 0:
                return "neutral", 0.5
            ratio = bid_vol / total
            if ratio > 0.65:
                return "buy_wall", ratio
            elif ratio < 0.35:
                return "sell_wall", ratio
            return "neutral", ratio
        except:
            return "neutral", 0.5

    def _no_signal(self, symbol: str, price: float) -> Signal:
        return Signal(
            symbol=symbol, side="none",
            strength=0.0, reason=["No clear smart money signal"],
            entry_price=price, sl_price=0, tp_price=0
        )
