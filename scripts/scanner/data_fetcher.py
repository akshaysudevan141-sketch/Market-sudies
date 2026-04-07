#!/usr/bin/env python3
# scripts/scanner/data_fetcher.py
# ─────────────────────────────────────────────────────────────────────────────
# Fetches live NSE data via yfinance with symbol correction + BSE fallback
# ─────────────────────────────────────────────────────────────────────────────

import yfinance as yf
import pandas as pd
import time
from datetime import datetime, timezone, timedelta

# ── Symbol corrections ────────────────────────────────────────────────────────
# Maps old/wrong NSE symbol → correct yfinance symbol
# Reasons: demergers, name changes, special chars
SYMBOL_MAP = {
    # Demerged / Renamed
    "TATAMOTORS":  "TMCV",        # Tata Motors CV (demerged 2025)
    "TATAMOTORS2": "TMPV",        # Tata Motors PV (demerged 2025)
    "LTIM":        "LTIM",        # LTIMindtree — try as-is first
    "M&M":         "M%26M",       # & needs encoding — try MM.NS too
    "BAJAJ-AUTO":  "BAJAJ-AUTO",  # hyphen OK in yfinance
    "ADANITRANS":  "ADANITRANS",

    # Common alternate tickers
    "NAUKRI":      "NAUKRI",      # Info Edge
    "DMART":       "DMART",       # Avenue Supermarts
    "IRFC":        "IRFC",
    "RVNL":        "RVNL",
}

# ── Alternate symbols to try if primary fails ─────────────────────────────────
SYMBOL_FALLBACKS = {
    "M&M":        ["MM.NS", "M%26M.NS", "M&M.BO"],
    "LTIM":       ["LTIM.NS", "LTIMINDTREE.NS"],
    "TATAMOTORS": ["TMCV.NS", "TATAMOTORS.BO"],
    "BAJAJ-AUTO": ["BAJAJ-AUTO.NS", "BAJALAUTO.NS"],
    "ADANITRANS": ["ADANITRANS.NS", "ADANIPOWER.NS"],
    "HDFCAMC":    ["HDFCAMC.NS", "HDFC-AMC.NS"],
    "HDFC-ERGO":  ["HDFCERGO.NS"],
    "MCDOWELL-N": ["MCDOWELL-N.NS", "UBL.NS"],
    "UNITDSPR":   ["UNITDSPR.NS", "UNITEDSPIRITS.NS"],
    "ANAND RATHI":["ANANDRATH.NS"],
}

def get_yf_symbol(symbol):
    """Convert NSE symbol to yfinance format."""
    symbol = symbol.upper().strip()
    # Replace & for URL safety
    yf_sym = symbol.replace("&", "%26")
    if not yf_sym.endswith(".NS") and not yf_sym.endswith(".BO"):
        return f"{yf_sym}.NS"
    return yf_sym

def fetch_stock_data(symbol, period="180d", interval="1d", retries=2):
    """
    Fetch OHLCV for a single NSE stock.
    Tries primary .NS symbol first, then fallbacks.
    """
    # Build list of symbols to try
    symbols_to_try = []

    if symbol in SYMBOL_FALLBACKS:
        symbols_to_try = SYMBOL_FALLBACKS[symbol]
    else:
        corrected = SYMBOL_MAP.get(symbol, symbol)
        symbols_to_try = [
            f"{corrected}.NS",
            f"{corrected}.BO",   # BSE fallback
        ]

    for yf_symbol in symbols_to_try:
        for attempt in range(retries):
            try:
                ticker = yf.Ticker(yf_symbol)
                df = ticker.history(
                    period=period,
                    interval=interval,
                    auto_adjust=True
                )
                if df is None or df.empty:
                    break  # try next symbol

                df.columns = [c.lower() for c in df.columns]
                df = df[["open","high","low","close","volume"]].copy()
                df.dropna(inplace=True)

                if len(df) < 5:
                    break  # try next symbol

                return df  # ✅ success

            except Exception:
                if attempt < retries - 1:
                    time.sleep(0.5)
                continue

    return None  # all attempts failed

def fetch_multiple_stocks(symbols, period="180d", interval="1d", delay=0.2):
    """
    Fetch data for multiple stocks with rate limiting.
    Returns: { symbol: DataFrame }
    """
    results    = {}
    failed     = []
    total      = len(symbols)

    for i, symbol in enumerate(symbols):
        print(f"  [{i+1}/{total}] {symbol:<15}", end="\r")
        df = fetch_stock_data(symbol, period=period, interval=interval)
        if df is not None:
            results[symbol] = df
        else:
            failed.append(symbol)
        time.sleep(delay)

    print(f"\n  ✅ Fetched: {len(results)}/{total}  ❌ Failed: {len(failed)}")
    if failed:
        print(f"  ⚠️  Skipped: {', '.join(failed)}")
    return results

def get_market_status():
    """Check if NSE market is open."""
    ist = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(ist)
    if now.weekday() >= 5:
        return {"open":False,"status":"Weekend","time":now.strftime("%H:%M IST")}
    mo = now.replace(hour=9,  minute=15, second=0, microsecond=0)
    mc = now.replace(hour=15, minute=30, second=0, microsecond=0)
    if mo <= now <= mc:
        return {"open":True, "status":"🟢 Market Open",  "time":now.strftime("%H:%M IST")}
    if now.hour < 9 or (now.hour == 9 and now.minute < 15):
        return {"open":False,"status":"🟡 Pre-Market",   "time":now.strftime("%H:%M IST")}
    return     {"open":False,"status":"🔴 Market Closed","time":now.strftime("%H:%M IST")}
