"""
backtest/backtest.py
Backtest smart money strategy on historical OHLCV data.
Usage: python -m src.backtest.backtest --symbol BTC/USDT:USDT --days 30
"""

import argparse
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from loguru import logger
from dotenv import load_dotenv

load_dotenv()


class BacktestEngine:
    def __init__(self, symbol: str, timeframe: str = "1h",
                 days: int = 30, sl_pct: float = 0.02, tp_pct: float = 0.04,
                 trail_pct: float = 0.015):
        self.symbol = symbol
        self.timeframe = timeframe
        self.days = days
        self.sl_pct = sl_pct
        self.tp_pct = tp_pct
        self.trail_pct = trail_pct
        self.trades = []

    def load_data(self) -> pd.DataFrame:
        """Load historical OHLCV from Bybit"""
        from src.exchange.bybit_client import BybitClient
        client = BybitClient()
        limit = self.days * 24 if self.timeframe == "1h" else self.days
        logger.info(f"Loading {limit} candles for {self.symbol}...")
        ohlcv = client.get_ohlcv(self.symbol, self.timeframe, limit)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("timestamp")
        logger.info(f"Loaded {len(df)} candles from {df.index[0]} to {df.index[-1]}")
        return df

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate buy/sell signals based on smart money indicators"""
        df = df.copy()

        # Volume surge (>2x average)
        df["vol_avg"] = df["volume"].rolling(20).mean()
        df["vol_surge"] = df["volume"] / df["vol_avg"]

        # Price position in range
        df["high_20"] = df["high"].rolling(20).max()
        df["low_20"] = df["low"].rolling(20).min()
        df["range_pos"] = (df["close"] - df["low_20"]) / (df["high_20"] - df["low_20"] + 1e-10)

        # Momentum
        df["roc"] = df["close"].pct_change(3)

        # Signal logic
        df["signal"] = "none"

        buy_cond = (
            (df["vol_surge"] > 1.8) &        # Volume spike
            (df["range_pos"] < 0.35) &        # Near range low (accumulation)
            (df["roc"] > -0.02)               # Not in freefall
        )

        sell_cond = (
            (df["vol_surge"] > 1.8) &         # Volume spike
            (df["range_pos"] > 0.65) &         # Near range high (distribution)
            (df["roc"] < 0.02)                 # Not pumping hard
        )

        df.loc[buy_cond, "signal"] = "buy"
        df.loc[sell_cond, "signal"] = "sell"

        return df

    def run(self) -> dict:
        """Run full backtest"""
        df = self.load_data()
        df = self.generate_signals(df)

        capital = 1000.0
        initial_capital = capital
        position = None
        trades = []

        for i in range(len(df)):
            row = df.iloc[i]
            price = row["close"]

            # Check existing position
            if position:
                side = position["side"]
                entry = position["entry"]
                sl = position["sl"]
                tp = position["tp"]
                peak = position.get("peak", entry)

                # Update trailing stop
                if side == "buy":
                    if price > peak:
                        position["peak"] = price
                        new_sl = price * (1 - self.trail_pct)
                        if new_sl > sl:
                            position["sl"] = new_sl
                            sl = new_sl
                elif side == "sell":
                    if price < peak:
                        position["peak"] = price
                        new_sl = price * (1 + self.trail_pct)
                        if new_sl < sl:
                            position["sl"] = new_sl
                            sl = new_sl

                # Check SL/TP hit
                closed = False
                close_reason = ""
                close_price = price

                if side == "buy":
                    if row["low"] <= sl:
                        close_price = sl
                        close_reason = "Stop Loss"
                        closed = True
                    elif row["high"] >= tp:
                        close_price = tp
                        close_reason = "Take Profit"
                        closed = True
                elif side == "sell":
                    if row["high"] >= sl:
                        close_price = sl
                        close_reason = "Stop Loss"
                        closed = True
                    elif row["low"] <= tp:
                        close_price = tp
                        close_reason = "Take Profit"
                        closed = True

                if closed:
                    if side == "buy":
                        pnl_pct = (close_price - entry) / entry
                    else:
                        pnl_pct = (entry - close_price) / entry

                    pnl_usdt = capital * 0.1 * pnl_pct  # 10% position size
                    capital += pnl_usdt

                    trades.append({
                        "entry_time": position["entry_time"],
                        "exit_time": df.index[i],
                        "symbol": self.symbol,
                        "side": side,
                        "entry": entry,
                        "exit": close_price,
                        "pnl_pct": pnl_pct * 100,
                        "pnl_usdt": pnl_usdt,
                        "reason": close_reason,
                        "capital_after": capital
                    })
                    position = None

            # Open new position
            if position is None and row["signal"] != "none":
                side = row["signal"]
                if side == "buy":
                    sl = price * (1 - self.sl_pct)
                    tp = price * (1 + self.tp_pct)
                else:
                    sl = price * (1 + self.sl_pct)
                    tp = price * (1 - self.tp_pct)

                position = {
                    "side": side,
                    "entry": price,
                    "sl": sl,
                    "tp": tp,
                    "peak": price,
                    "entry_time": df.index[i]
                }

        self.trades = trades
        return self._summary(trades, initial_capital, capital)

    def _summary(self, trades: list, initial: float, final: float) -> dict:
        """Calculate backtest statistics"""
        if not trades:
            return {"error": "No trades generated"}

        df = pd.DataFrame(trades)
        wins = df[df["pnl_pct"] > 0]
        losses = df[df["pnl_pct"] <= 0]
        win_rate = len(wins) / len(df) * 100

        summary = {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "period_days": self.days,
            "total_trades": len(df),
            "win_trades": len(wins),
            "loss_trades": len(losses),
            "win_rate": round(win_rate, 1),
            "total_pnl_pct": round((final - initial) / initial * 100, 2),
            "total_pnl_usdt": round(final - initial, 2),
            "avg_win_pct": round(wins["pnl_pct"].mean(), 2) if len(wins) else 0,
            "avg_loss_pct": round(losses["pnl_pct"].mean(), 2) if len(losses) else 0,
            "best_trade_pct": round(df["pnl_pct"].max(), 2),
            "worst_trade_pct": round(df["pnl_pct"].min(), 2),
            "profit_factor": round(abs(wins["pnl_pct"].sum() / losses["pnl_pct"].sum()), 2) if len(losses) else 999,
            "initial_capital": initial,
            "final_capital": round(final, 2),
        }

        self._print_report(summary, df)
        return summary

    def _print_report(self, summary: dict, df: pd.DataFrame):
        """Print formatted backtest report"""
        pnl_sign = "+" if summary["total_pnl_pct"] >= 0 else ""
        logger.info("\n" + "="*50)
        logger.info(f"📊 BACKTEST REPORT - {summary['symbol']}")
        logger.info("="*50)
        logger.info(f"Periode    : {summary['period_days']} hari ({summary['timeframe']})")
        logger.info(f"Total Trade: {summary['total_trades']}")
        logger.info(f"Win Rate   : {summary['win_rate']}%")
        logger.info(f"Total PnL  : {pnl_sign}{summary['total_pnl_pct']}% (${summary['total_pnl_usdt']})")
        logger.info(f"Best Trade : +{summary['best_trade_pct']}%")
        logger.info(f"Worst Trade: {summary['worst_trade_pct']}%")
        logger.info(f"Profit Factor: {summary['profit_factor']}")
        logger.info(f"Modal Awal : ${summary['initial_capital']}")
        logger.info(f"Modal Akhir: ${summary['final_capital']}")
        logger.info("="*50)
        logger.info("\n📋 Last 5 Trades:")
        for _, t in df.tail(5).iterrows():
            sign = "+" if t["pnl_pct"] > 0 else ""
            logger.info(f"  {t['side'].upper()} {t['entry']:.4f}→{t['exit']:.4f} {sign}{t['pnl_pct']:.2f}% [{t['reason']}]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest Smart Money Bot")
    parser.add_argument("--symbol", default="BTC/USDT:USDT", help="Trading pair")
    parser.add_argument("--timeframe", default="1h", help="Candle timeframe")
    parser.add_argument("--days", type=int, default=30, help="Backtest period in days")
    parser.add_argument("--sl", type=float, default=2.0, help="Stop loss %")
    parser.add_argument("--tp", type=float, default=4.0, help="Take profit %")
    args = parser.parse_args()

    engine = BacktestEngine(
        symbol=args.symbol,
        timeframe=args.timeframe,
        days=args.days,
        sl_pct=args.sl / 100,
        tp_pct=args.tp / 100
    )
    engine.run()
