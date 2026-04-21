"""
scanner/pair_scanner.py - Screens pairs by pump potential
"""
import pandas as pd
import numpy as np
from loguru import logger
from src.exchange.bybit_client import BybitClient
import os

class PairScanner:
    def __init__(self, client):
        self.client = client
        self.min_volume = float(os.getenv("MIN_VOLUME_24H_USDT", 10_000_000))
        self.top_n = int(os.getenv("TOP_PAIRS_TO_MONITOR", 20))

    def score_pair(self, symbol):
        try:
            ticker = self.client.get_ticker(symbol)
            if not ticker: return None
            volume_24h = float(ticker.get("quoteVolume", 0))
            if volume_24h < self.min_volume: return None
            price = float(ticker.get("last", 0))
            change_24h = float(ticker.get("percentage", 0))
            high_24h = float(ticker.get("high", 0))
            low_24h = float(ticker.get("low", 0))
            ohlcv = self.client.get_ohlcv(symbol, "1h", 50)
            if len(ohlcv) < 20: return None
            closes = np.array([c[4] for c in ohlcv])
            volumes = np.array([c[5] for c in ohlcv])
            avg_vol = np.mean(volumes[-20:-1])
            curr_vol = volumes[-1]
            vol_surge = (curr_vol / avg_vol) if avg_vol > 0 else 1
            vol_score = min(vol_surge * 20, 30)
            funding_rate = self.client.get_funding_rate(symbol)
            if funding_rate < -0.0005: funding_score = 25
            elif funding_rate < 0: funding_score = 15
            elif funding_rate < 0.0005: funding_score = 5
            else: funding_score = 0
            if high_24h != low_24h:
                pos = (price - low_24h) / (high_24h - low_24h)
                momentum_score = 20 if pos < 0.3 else (12 if pos < 0.5 else 5)
            else: momentum_score = 0
            ob = self.client.get_order_book(symbol, 20)
            bid_vol = sum([b[1] for b in ob.get("bids", [])])
            ask_vol = sum([a[1] for a in ob.get("asks", [])])
            ob_score = (bid_vol / (bid_vol + ask_vol) * 15) if (bid_vol + ask_vol) > 0 else 0
            total_score = vol_score + funding_score + momentum_score + ob_score + 10
            return {"symbol": symbol, "price": price, "change_24h": change_24h,
                    "volume_24h": volume_24h, "funding_rate": funding_rate,
                    "vol_surge": round(vol_surge, 2), "score": round(total_score, 2)}
        except Exception as e:
            logger.debug(f"Skipping {symbol}: {e}")
            return None

    def scan(self):
        logger.info("Scanning all USDT pairs...")
        all_pairs = self.client.get_all_usdt_pairs()
        results = [r for sym in all_pairs if (r := self.score_pair(sym))]
        if not results: return pd.DataFrame()
        df = pd.DataFrame(results).sort_values("score", ascending=False).head(self.top_n).reset_index(drop=True)
        logger.info(f"Top {len(df)} pairs identified")
        return df
