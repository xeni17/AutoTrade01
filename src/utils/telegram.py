"""
utils/telegram.py - Telegram notifications & daily dashboard
"""
import requests
import os
from datetime import datetime
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_message(text: str, parse_mode: str = "HTML"):
    """Send message to Telegram"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured, skipping notification")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        res = requests.post(url, json=payload, timeout=10)
        return res.ok
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False


def notify_signal(signal):
    """Send signal notification"""
    emoji = "🟢" if signal.side == "buy" else "🔴"
    side_label = "LONG" if signal.side == "buy" else "SHORT"

    text = (
        f"{emoji} <b>SINYAL {side_label}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📌 <b>Pair:</b> {signal.symbol}\n"
        f"💰 <b>Entry:</b> {signal.entry_price}\n"
        f"🛑 <b>Stop Loss:</b> {signal.sl_price}\n"
        f"🎯 <b>Take Profit:</b> {signal.tp_price}\n"
        f"💪 <b>Kekuatan:</b> {signal.strength:.0%}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📊 <b>Alasan:</b>\n"
    )
    for r in signal.reason:
        text += f"  • {r}\n"

    text += f"\n⏰ {datetime.now().strftime('%H:%M:%S')}"
    send_message(text)


def notify_trade_open(signal, contracts, mode="paper"):
    """Notify when trade is opened"""
    emoji = "🟢" if signal.side == "buy" else "🔴"
    mode_label = "📝 PAPER" if mode == "paper" else "💸 LIVE"

    text = (
        f"{emoji} <b>ORDER TERBUKA</b> {mode_label}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📌 {signal.symbol}\n"
        f"📈 {signal.side.upper()} {contracts:.6f} kontrak\n"
        f"💰 Entry: <code>{signal.entry_price}</code>\n"
        f"🛑 SL: <code>{signal.sl_price}</code>\n"
        f"🎯 TP: <code>{signal.tp_price}</code>\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S')}"
    )
    send_message(text)


def notify_trade_close(symbol, side, entry, close_price, pnl_pct, reason=""):
    """Notify when trade is closed"""
    emoji = "✅" if pnl_pct > 0 else "❌"
    pnl_label = f"+{pnl_pct:.2f}%" if pnl_pct > 0 else f"{pnl_pct:.2f}%"

    text = (
        f"{emoji} <b>ORDER DITUTUP</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📌 {symbol} {side.upper()}\n"
        f"📥 Entry: <code>{entry}</code>\n"
        f"📤 Close: <code>{close_price}</code>\n"
        f"💹 <b>PnL: {pnl_label}</b>\n"
        f"📝 Alasan: {reason}\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S')}"
    )
    send_message(text)


def notify_trailing_stop_update(symbol, new_sl):
    """Notify trailing stop adjustment"""
    text = (
        f"🔄 <b>TRAILING STOP UPDATE</b>\n"
        f"📌 {symbol}\n"
        f"🛑 SL baru: <code>{new_sl}</code>\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S')}"
    )
    send_message(text)


def send_daily_dashboard(stats: dict):
    """Send daily performance dashboard at 7am"""
    total_trades = stats.get("total_trades", 0)
    win_trades = stats.get("win_trades", 0)
    loss_trades = stats.get("loss_trades", 0)
    winrate = (win_trades / total_trades * 100) if total_trades > 0 else 0
    total_pnl = stats.get("total_pnl", 0.0)
    best_trade = stats.get("best_trade", 0.0)
    worst_trade = stats.get("worst_trade", 0.0)
    balance = stats.get("balance", 0.0)
    open_positions = stats.get("open_positions", [])

    pnl_emoji = "📈" if total_pnl >= 0 else "📉"
    pnl_label = f"+{total_pnl:.2f}%" if total_pnl >= 0 else f"{total_pnl:.2f}%"

    text = (
        f"🤖 <b>LAPORAN HARIAN - Smart Money Bot</b>\n"
        f"📅 {datetime.now().strftime('%d %B %Y')}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Balance:</b> ${balance:.2f} USDT\n"
        f"{pnl_emoji} <b>Total PnL:</b> {pnl_label}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Statistik Trading:</b>\n"
        f"  • Total Trade: {total_trades}\n"
        f"  • Menang: {win_trades} ✅\n"
        f"  • Kalah: {loss_trades} ❌\n"
        f"  • Win Rate: {winrate:.1f}%\n"
        f"  • Trade Terbaik: +{best_trade:.2f}%\n"
        f"  • Trade Terburuk: {worst_trade:.2f}%\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
    )

    if open_positions:
        text += f"📌 <b>Posisi Terbuka ({len(open_positions)}):</b>\n"
        for pos in open_positions:
            pnl = pos.get("unrealizedPnl", 0)
            pnl_str = f"+{pnl:.2f}" if pnl >= 0 else f"{pnl:.2f}"
            text += f"  • {pos.get('symbol')} {pos.get('side')} → {pnl_str} USDT\n"
    else:
        text += "📌 <b>Posisi Terbuka:</b> Tidak ada\n"

    text += f"━━━━━━━━━━━━━━━━━━━\n⏰ Dikirim jam 07:00 WIB"
    send_message(text)


def notify_bot_start(mode: str, watchlist_count: int):
    """Notify bot startup"""
    text = (
        f"🚀 <b>Smart Money Bot AKTIF</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"⚙️ Mode: <b>{'📝 PAPER' if mode == 'paper' else '💸 LIVE'}</b>\n"
        f"🔍 Memantau: <b>{watchlist_count} pair</b>\n"
        f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    )
    send_message(text)


def notify_error(error_msg: str):
    """Notify critical errors"""
    text = (
        f"⚠️ <b>ERROR BOT</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<code>{error_msg[:200]}</code>\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S')}"
    )
    send_message(text)
