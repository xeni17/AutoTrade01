# Robot Smart Money Bot - Bybit Auto Trader

Bot trading otomatis berbasis Smart Money Concept menggunakan data gratis dari Bybit API.

## Strategi

- **Funding Rate Negatif** - Short squeeze potential - BUY
- **Order Book Imbalance** - Buy wall besar - BUY  
- **Volume Spike** - Whale accumulation - BUY/SELL
- **Funding Rate Positif Ekstrem** - Long squeeze risk - SELL

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
python main.py
```

## Disclaimer
Trading crypto mengandung risiko. Test di paper mode dulu sebelum live.
