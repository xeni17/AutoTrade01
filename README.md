# 🤖 Smart Money Bot — Bybit Auto Trader

Bot trading otomatis berbasis **Smart Money Concept** menggunakan data gratis dari Bybit API.

## 🧠 Strategi

Bot mendeteksi akumulasi "smart money" dengan menganalisis:

| Signal | Logika |
|--------|--------|
| **Funding Rate Negatif** | Shorts dominan → potensi short squeeze → BUY |
| **OI + Volume Naik** | Fresh money masuk → akumulasi → BUY |
| **Order Book Imbalance** | Buy wall besar → demand kuat → BUY |
| **Volume Spike** | Whale masuk tiba-tiba → BUY/SELL sesuai arah |
| **Funding Rate Positif Ekstrem** | Longs overcrowded → potensi dump → SELL |

## ⚙️ Alur Bot

```
Scan semua USDT pairs di Bybit
        ↓
Filter berdasarkan volume & scoring
        ↓
Ambil Top N pairs (default: 20)
        ↓
Analisis Smart Money per pair
        ↓
Cek Risk Management
        ↓
Execute Order + Set SL/TP
```

## 🚀 Setup

### 1. Clone & Install
```bash
git clone <repo-url>
cd smart-money-bot
pip install -r requirements.txt
```

### 2. Konfigurasi
```bash
cp .env.example .env
# Edit .env dengan API key Bybit kamu
```

### 3. Dapatkan API Key Bybit
- Login ke bybit.com
- API Management → Create New Key
- Permission: **Read + Trade** (jangan berikan withdraw!)
- Simpan di `.env`

### 4. Jalankan (Paper Trading dulu!)
```bash
# Pastikan BOT_MODE=paper di .env
python main.py
```

### 5. Switch ke Live
```bash
# Edit .env:
BOT_MODE=live
BYBIT_TESTNET=false
```

## 📁 Struktur Project

```
smart-money-bot/
├── main.py                    # Entry point
├── .env.example               # Config template
├── requirements.txt
└── src/
    ├── core/
    │   └── bot.py             # Main orchestrator
    ├── exchange/
    │   └── bybit_client.py    # Bybit API wrapper
    ├── scanner/
    │   └── pair_scanner.py    # Multi-pair screener
    ├── strategy/
    │   └── smart_money.py     # Signal generator
    └── risk/
        └── risk_manager.py    # Position sizing & limits
```

## ⚠️ Disclaimer

> Trading crypto mengandung risiko tinggi. Gunakan dana yang siap hilang.
> Selalu test di **paper mode** atau **testnet** sebelum live.
> Bot ini bukan financial advice.

## 🗺️ Roadmap

- [ ] Trailing stop otomatis
- [ ] Telegram notifications
- [ ] Dashboard web monitoring
- [ ] Backtesting module
- [ ] Multi-exchange support
