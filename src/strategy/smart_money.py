"""
strategy/smart_money.py - Smart Money signal generator
"""
import numpy as np
from dataclasses import dataclass
from loguru import logger

@dataclass
class Signal:
    symbol: str
    side: str
    strength: float
    reason: list
    entry_price: float
    sl_price: float
    tp_price: float

class SmartMoneyStrategy:
    def __init__(self, client):
        self.client = client
        self.sl_pct = 0.02
        self.tp_pct = 0.04

    def analyze(self, symbol):
        reasons = []
        buy_score = 0
        sell_score = 0
        ticker = self.client.get_ticker(symbol)
        if not ticker: return self._no_signal(symbol, 0)
        price = float(ticker.get("last", 0))
        funding = self.client.get_funding_rate(symbol)
        if funding < -0.001: buy_score += 35; reasons.append(f"Extreme negative funding ({funding:.4%}) - short squeeze")
        elif funding < -0.0003: buy_score += 20; reasons.append(f"Negative funding ({funding:.4%})")
        elif funding > 0.001: sell_score += 35; reasons.append(f"Extreme positive funding ({funding:.4%}) - long squeeze")
        elif funding > 0.0003: sell_score += 20; reasons.append(f"High funding ({funding:.4%})")
        ob = self.client.get_order_book(symbol, 20)
        bid_vol = sum([b[1] for b in ob.get("bids", [])])
        ask_vol = sum([a[1] for a in ob.get("asks", [])])
        if bid_vol + ask_vol > 0:
            ratio = bid_vol / (bid_vol + ask_vol)
            if ratio > 0.65: buy_score += 20; reasons.append(f"Strong buy wall (ratio: {ratio:.2f})")
            elif ratio < 0.35: sell_score += 20; reasons.append(f"Strong sell wall (ratio: {ratio:.2f})")
        ohlcv = self.client.get_ohlcv(symbol, "1h", 25)
        if len(ohlcv) >= 10:
            vols = np.array([c[5] for c in ohlcv])
            closes = np.array([c[4] for c in ohlcv])
            ratio = vols[-1] / np.mean(vols[-20:-1]) if np.mean(vols[-20:-1]) > 0 else 1
            if ratio > 2.5:
                if closes[-1] > closes[-2]: buy_score += 20; reasons.append(f"Volume spike {ratio:.1f}x - accumulation")
                else: sell_score += 15; reasons.append(f"Volume spike {ratio:.1f}x - distribution")
        if buy_score >= 50 and buy_score > sell_score:
            return Signal(symbol, "buy", min(buy_score/100, 1.0), reasons, price,
                         round(price*(1-self.sl_pct), 4), round(price*(1+self.tp_pct), 4))
        elif sell_score >= 50 and sell_score > buy_score:
            return Signal(symbol, "sell", min(sell_score/100, 1.0), reasons, price,
                         round(price*(1+self.sl_pct), 4), round(price*(1-self.tp_pct), 4))
        return self._no_signal(symbol, price)

    def _no_signal(self, symbol, price):
        return Signal(symbol, "none", 0.0, ["No clear signal"], price, 0, 0)
