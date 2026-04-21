"""
scanner/pair_scanner.py
Screens all USDT pairs and ranks by pump potential
using free data sources only.
"""

import pandas as pd
import numpy as np
from loguru import logger
from src.exchange.bybit_client import BybitClient
import os


class PairScanner:
    def __init__(self, client: BybitClient):
        self.client = client
        self.min_volume = float(os.getenv("MIN_VOLUME_24H_USDT", 10_000_000))
        self.top_n = int(os.getenv("TOP_PAIRS_TO_MONITOR", 20))

    def score_pair(self, symbol: str) -> dict | None:
        """Score a single pair for pump potential (0-100)"""
        try:
            ticker = self.client.get_ticker(symbol)
            if not ticker:
                return None

            volume_24h = float(ticker.get("quoteVolume", 0))
            if volume_24h < self.min_volume:
                return None

            price = float(ticker.get("last", 0))
            change_24h = float(ticker.get("percentage", 0))
            high_24h = float(ticker.get("high", 0))
            low_24h = float(ticker.get("low", 0))

            # --- OHLCV for technical indicators ---
            ohlcv = self.client.get_ohlcv(symbol, "1h", 50)
            if len(ohlcv) < 20:
                return None

            closes = np.array([c[4] for c in ohlcv])
            volumes = np.array([c[5] for c in ohlcv])

            # 1. Volume surge score (current vs avg)
            avg_vol = np.mean(volumes[-20:-1])
            curr_vol = volumes[-1]
            vol_surge = (curr_vol / avg_vol) if avg_vol > 0 else 1
            vol_score = min(vol_surge * 20, 30)  # max 30 pts

            # 2. Funding rate score (negative = shorts dominant = squeeze potential)
            funding_rate = self.client.get_funding_rate(symbol)
            if funding_rate < -0.0005:
                funding_score = 25  # Strong short squeeze setup
            elif funding_rate < 0:
                funding_score = 15
            elif funding_rate < 0.0005:
                funding_score = 5
            else:
                funding_score = 0  # Longs crowded, risky
            # max 25 pts

            # 3. Price momentum score (% from 24h low)
            if high_24h != low_24h:
                position_in_range = (price - low_24h) / (high_24h - low_24h)
                # Near low = accumulation zone = more potential
                if position_in_range < 0.3:
                    momentum_score = 20
                elif position_in_range < 0.5:
                    momentum_score = 12
                else:
                    momentum_score = 5
            else:
                momentum_score = 0
            # max 20 pts

            # 4. Order book imbalance score
            ob = self.client.get_order_book(symbol, 20)
            bid_vol = sum([b[1] for b in ob.get("bids", [])])
            ask_vol = sum([a[1] for a in ob.get("asks", [])])
            if bid_vol + ask_vol > 0:
                imbalance = bid_vol / (bid_vol + ask_vol)
                ob_score = imbalance * 15  # max 15 pts
            else:
                ob_score = 0

            # 5. OI score
            oi_data = self.client.get_open_interest(symbol)
            oi_score = 0
            if oi_data:
                # OI increasing = smart money entering
                oi_score = 10  # max 10 pts (simplified, extend with history)

            total_score = vol_score + funding_score + momentum_score + ob_score + oi_score

            return {
                "symbol": symbol,
                "price": price,
                "change_24h": change_24h,
                "volume_24h": volume_24h,
                "funding_rate": funding_rate,
                "vol_surge": round(vol_surge, 2),
                "score": round(total_score, 2),
                "vol_score": round(vol_score, 2),
                "funding_score": funding_score,
                "momentum_score": momentum_score,
                "ob_score": round(ob_score, 2),
                "oi_score": oi_score,
            }

        except Exception as e:
            logger.debug(f"Skipping {symbol}: {e}")
            return None

    def scan(self) -> pd.DataFrame:
        """Scan all pairs and return top candidates sorted by score"""
        logger.info("🔍 Scanning all USDT pairs...")
        all_pairs = self.client.get_all_usdt_pairs()

        results = []
        for i, symbol in enumerate(all_pairs):
            if i % 20 == 0:
                logger.info(f"Scanning {i}/{len(all_pairs)}...")
            result = self.score_pair(symbol)
            if result:
                results.append(result)

        if not results:
            logger.warning("No pairs passed screening")
            return pd.DataFrame()

        df = pd.DataFrame(results)
        df = df.sort_values("score", ascending=False).head(self.top_n)
        df = df.reset_index(drop=True)

        logger.info(f"✅ Top {len(df)} pairs identified")
        logger.info(f"\n{df[['symbol','score','funding_rate','vol_surge','change_24h']].to_string()}")

        return df
