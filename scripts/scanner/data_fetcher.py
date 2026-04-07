#!/usr/bin/env python3
# scripts/scanner/data_fetcher.py
# ─────────────────────────────────────────────────────────────────────────────
# Fetches live NSE stock data for any timeframe using yfinance
# ─────────────────────────────────────────────────────────────────────────────

import yfinance as yf
import pandas as pd
import time
from datetime import datetime, timezone, timedelta

def get_nse_symbol(symbol):
    """Convert NSE symbol to yfinance format (append .NS)"""
    symbol = symbol.upper().strip()
    if not symbol.endswith(".NS") and not symbol.endswith(".BO"):
        return f"{symbol}.NS"
    return symbol

def fetch_stock_data(symbol, period="180d", interval="1d", retries=3):
    """
    Fetch OHLCV data for a single NSE stock.
    
    Args:
        symbol   : NSE symbol e.g. 'RELIANCE'
        period   : Data period e.g. '5d', '30d', '180d', '2y'
        interval : Candle size e.g. '5m', '15m', '1h', '1d', '1wk'
        retries  : Number of retry attempts on failure
    
    Returns:
        DataFrame with columns: open, high, low, close, volume
        None if fetch fails
    """
    yf_symbol = get_nse_symbol(symbol)
    
    for attempt in range(retries):
        try:
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(period=period, interval=interval, auto_adjust=True)
            
            if df is None or df.empty:
                if attempt < retries - 1:
                    time.sleep(1)
                    continue
                return None
            
            # Normalize column names to lowercase
            df.columns = [c.lower() for c in df.columns]
            
            # Keep only OHLCV
            df = df[["open", "high", "low", "close", "volume"]].copy()
            
            # Drop rows with NaN
            df.dropna(inplace=True)
            
            if len(df) < 10:
                return None
            
            return df
            
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1.5)
                continue
            return None
    
    return None

def fetch_multiple_stocks(symbols, period="180d", interval="1d", delay=0.3):
    """
    Fetch data for multiple stocks with rate limiting.
    
    Returns:
        dict: { symbol: DataFrame }  (only successful fetches)
    """
    results = {}
    total = len(symbols)
    
    for i, symbol in enumerate(symbols):
        print(f"  [{i+1}/{total}] Fetching {symbol}...", end="\r")
        df = fetch_stock_data(symbol, period=period, interval=interval)
        if df is not None:
            results[symbol] = df
        time.sleep(delay)
    
    print(f"\n  ✅ Fetched {len(results)}/{total} stocks")
    return results

def get_live_price(symbol):
    """Get current live price for a symbol."""
    try:
        ticker = yf.Ticker(get_nse_symbol(symbol))
        info = ticker.fast_info
        return round(float(info.last_price), 2)
    except:
        return None

def is_market_open():
    """Check if NSE market is currently open (9:15 AM - 3:30 PM IST Mon-Fri)."""
    ist = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(ist)
    if now.weekday() >= 5:  # Saturday/Sunday
        return False
    market_open  = now.replace(hour=9,  minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close

def get_market_status():
    """Return market status string."""
    ist = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(ist)
    if is_market_open():
        return { "open": True,  "status": "🟢 Market Open",  "time": now.strftime("%H:%M IST") }
    elif now.weekday() >= 5:
        return { "open": False, "status": "🔴 Weekend",       "time": now.strftime("%H:%M IST") }
    elif now.hour < 9 or (now.hour == 9 and now.minute < 15):
        return { "open": False, "status": "🟡 Pre-Market",    "time": now.strftime("%H:%M IST") }
    else:
        return { "open": False, "status": "🔴 Market Closed", "time": now.strftime("%H:%M IST") }
