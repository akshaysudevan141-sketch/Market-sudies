#!/usr/bin/env python3
# scripts/scanner/config.py
# ─────────────────────────────────────────────────────────────────────────────
# All configurable settings for the NSE Stock Scanner
# ─────────────────────────────────────────────────────────────────────────────

# ── Timeframes ────────────────────────────────────────────────────────────────
# All supported timeframes — user can pick any or ALL
TIMEFRAMES = {
    "5m":  { "label": "5 Min",    "period": "5d",   "interval": "5m",  "trading": True  },
    "15m": { "label": "15 Min",   "period": "5d",   "interval": "15m", "trading": True  },
    "30m": { "label": "30 Min",   "period": "10d",  "interval": "30m", "trading": True  },
    "1h":  { "label": "1 Hour",   "period": "30d",  "interval": "60m", "trading": True  },
    "1d":  { "label": "Daily",    "period": "180d", "interval": "1d",  "trading": False },
    "1wk": { "label": "Weekly",   "period": "2y",   "interval": "1wk", "trading": False },
}

# Default timeframe when none selected
DEFAULT_TIMEFRAME = "1d"

# ── Stock Universes ───────────────────────────────────────────────────────────
UNIVERSES = {
    "nifty50": {
        "label": "Nifty 50",
        "symbols": [
            "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
            "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK",
            "LT", "AXISBANK", "ASIANPAINT", "MARUTI", "TITAN",
            "SUNPHARMA", "ULTRACEMCO", "WIPRO", "ONGC", "NTPC",
            "POWERGRID", "BAJFINANCE", "HCLTECH", "M&M", "NESTLEIND",
            "TATAMOTORS", "TECHM", "BAJAJFINSV", "ADANIPORTS", "COALINDIA",
            "DRREDDY", "DIVISLAB", "CIPLA", "EICHERMOT", "GRASIM",
            "HEROMOTOCO", "HINDALCO", "INDUSINDBK", "JSWSTEEL", "TATACONSUM",
            "TATASTEEL", "APOLLOHOSP", "BPCL", "BRITANNIA", "SHRIRAMFIN",
            "SBILIFE", "HDFCLIFE", "BAJAJ-AUTO", "LTIM", "ADANIENT"
        ]
    },
    "nifty100": {
        "label": "Nifty 100",
        "symbols": [
            # Nifty 50
            "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
            "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK",
            "LT", "AXISBANK", "ASIANPAINT", "MARUTI", "TITAN",
            "SUNPHARMA", "ULTRACEMCO", "WIPRO", "ONGC", "NTPC",
            "POWERGRID", "BAJFINANCE", "HCLTECH", "M&M", "NESTLEIND",
            "TATAMOTORS", "TECHM", "BAJAJFINSV", "ADANIPORTS", "COALINDIA",
            "DRREDDY", "DIVISLAB", "CIPLA", "EICHERMOT", "GRASIM",
            "HEROMOTOCO", "HINDALCO", "INDUSINDBK", "JSWSTEEL", "TATACONSUM",
            "TATASTEEL", "APOLLOHOSP", "BPCL", "BRITANNIA", "SHRIRAMFIN",
            "SBILIFE", "HDFCLIFE", "BAJAJ-AUTO", "LTIM", "ADANIENT",
            # Next 50
            "SIEMENS", "HAL", "PIDILITIND", "DABUR", "MUTHOOTFIN",
            "GODREJCP", "MARICO", "BERGEPAINT", "HAVELLS", "TRENT",
            "AMBUJACEM", "DMART", "INDIGO", "NAUKRI", "BIOCON",
            "TORNTPHARM", "LUPIN", "PGHH", "COLPAL", "BANDHANBNK",
            "FEDERALBNK", "PNB", "CANBK", "BANKBARODA", "IDFCFIRSTB",
            "CHOLAFIN", "MFSL", "PIIND", "AUROPHARMA", "ALKEM",
            "CONCOR", "SAIL", "NMDC", "GAIL", "IOC",
            "RECLTD", "PFC", "IRCTC", "ZOMATO", "PAYTM",
            "NYKAA", "POLICYBZR", "DELHIVERY", "CARTRADE", "EASEMYTRIP",
            "MEDIASSIST", "RAINBOW", "SYNGENE", "LICI", "RVNL"
        ]
    },
    "banknifty": {
        "label": "Bank Nifty",
        "symbols": [
            "HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "SBIN",
            "INDUSINDBK", "BANDHANBNK", "FEDERALBNK", "PNB", "CANBK",
            "BANKBARODA", "IDFCFIRSTB", "AUBANK", "RBLBANK", "YESBANK"
        ]
    },
    "watchlist": {
        "label": "My Watchlist",
        "symbols": []  # User can add custom symbols
    }
}

# ── Scanner Filters ───────────────────────────────────────────────────────────
FILTERS = {
    "min_price":       20.0,
    "max_price":       50000.0,
    "min_volume":      50000,       # Minimum daily volume
    "volume_surge":    1.5,         # Volume must be 1.5x the 20-day average
    "rsi_min":         0,
    "rsi_max":         100,
    "consolidation_pct": 10.0,      # % range for consolidation detection
    "lookback_candles":  3,         # How many recent candles to check patterns
}

# ── Candlestick Patterns to Detect ───────────────────────────────────────────
BULLISH_PATTERNS = [
    "Morning Star",
    "Morning Doji Star",
    "Bullish Engulfing",
    "Hammer",
    "Dragonfly Doji",
    "3 White Soldiers",
    "3 Inside Up",
    "3 Outside Up",
    "Piercing Line",
    "Bullish Harami",
    "Bullish Marubozu",
    "Tweezer Bottom",
    "Inside Bar",
    "Cup and Handle",
]

BEARISH_PATTERNS = [
    "Evening Star",
    "Evening Doji Star",
    "Bearish Engulfing",
    "Shooting Star",
    "Gravestone Doji",
    "Hanging Man",
    "3 Black Crows",
    "3 Inside Down",
    "3 Outside Down",
    "Dark Cloud Cover",
    "Bearish Harami",
    "Bearish Marubozu",
    "Tweezer Top",
]

# ── Signal Weights (inspired by PKScreener) ───────────────────────────────────
SIGNAL_WEIGHTS = {
    "rsi":         15,
    "macd":        15,
    "ema":         15,
    "volume":      15,
    "candle":      20,
    "price_action":10,
    "momentum":    10,
}
