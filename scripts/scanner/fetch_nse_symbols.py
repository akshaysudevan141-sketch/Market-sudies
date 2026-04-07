#!/usr/bin/env python3
# scripts/scanner/fetch_nse_symbols.py
# ─────────────────────────────────────────────────────────────────────────────
# Fetches ALL NSE-listed equity stocks directly from NSE India API
# Validates each one on Yahoo Finance (.NS only)
# Saves to data/nse_symbols.json for the scanner to use
# ─────────────────────────────────────────────────────────────────────────────

import requests
import yfinance as yf
import json
import os
import time
from datetime import datetime, timezone, timedelta

IST      = timezone(timedelta(hours=5, minutes=30))
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")

# ── NSE API headers (required to avoid 403) ───────────────────────────────────
HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://www.nseindia.com/",
    "Connection":      "keep-alive",
}

# ── Index membership lists from NSE ──────────────────────────────────────────
NSE_INDEX_URLS = {
    "Nifty 50":     "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%2050",
    "Nifty 100":    "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20100",
    "Nifty 500":    "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20500",
    "Bank Nifty":   "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20BANK",
    "Nifty IT":     "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20IT",
    "Nifty Pharma": "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20PHARMA",
    "Nifty Metal":  "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20METAL",
    "Nifty Auto":   "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20AUTO",
    "Nifty FMCG":   "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20FMCG",
    "Nifty Realty": "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20REALTY",
    "Nifty Midcap 100": "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20MIDCAP%20100",
    "Nifty Smallcap 100": "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20SMLCAP%20100",
}

# ── All NSE equity list URL ───────────────────────────────────────────────────
NSE_ALL_EQUITY_URL = "https://www.nseindia.com/api/equity-stockIndices?index=SECURITIES%20IN%20F%26O"
NSE_ALL_STOCKS_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"


def get_nse_session():
    """Create a session with NSE cookies."""
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        session.get("https://www.nseindia.com", timeout=10)
        time.sleep(1)
    except Exception as e:
        print(f"  ⚠️  Session init failed: {e}")
    return session


def fetch_index_symbols(session, index_name, url):
    """Fetch symbols for a specific NSE index."""
    try:
        res = session.get(url, timeout=15)
        if res.status_code != 200:
            print(f"  ⚠️  {index_name}: HTTP {res.status_code}")
            return []
        data = res.json()
        symbols = []
        for item in data.get("data", []):
            sym = item.get("symbol", "").strip()
            if sym and sym not in ("", "NIFTY 50", "NIFTY BANK"):
                symbols.append(sym)
        print(f"  ✅ {index_name:<25} {len(symbols)} stocks")
        return symbols
    except Exception as e:
        print(f"  ❌ {index_name}: {e}")
        return []


def fetch_all_nse_equities():
    """
    Fetch complete NSE equity list from NSE archives CSV.
    Returns list of symbols.
    """
    try:
        print("📡 Fetching complete NSE equity list...")
        res = requests.get(NSE_ALL_STOCKS_URL, headers=HEADERS, timeout=30)
        if res.status_code == 200:
            lines   = res.text.strip().split("\n")
            symbols = []
            for line in lines[1:]:   # skip header
                cols = line.split(",")
                if cols:
                    sym = cols[0].strip().replace('"', '')
                    if sym and len(sym) <= 20:
                        symbols.append(sym)
            print(f"  ✅ Got {len(symbols)} total NSE equities")
            return symbols
        else:
            print(f"  ❌ HTTP {res.status_code}")
            return []
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return []


def validate_yahoo_symbol(symbol, test_period="5d"):
    """
    Check if a symbol is valid on Yahoo Finance (.NS only).
    Returns True if data exists, False otherwise.
    """
    yf_sym = f"{symbol}.NS"
    try:
        ticker = yf.Ticker(yf_sym)
        hist   = ticker.history(period=test_period, interval="1d")
        if hist is not None and not hist.empty and len(hist) >= 1:
            ltp = round(float(hist["Close"].iloc[-1]), 2)
            return True, ltp
        return False, None
    except Exception:
        return False, None


def build_symbol_database():
    """
    Main function:
    1. Fetch all NSE index memberships
    2. Fetch complete NSE equity list
    3. Validate each symbol on Yahoo Finance (.NS only)
    4. Save nse_symbols.json
    """
    print("━" * 65)
    print("🔍 NSE Symbol Database Builder")
    print("   Fetching from NSE India + Validating on Yahoo Finance")
    print("━" * 65)

    session    = get_nse_session()
    index_map  = {}   # symbol → [list of indices]

    # ── Step 1: Fetch each index membership ──────────────────────────────────
    print("\n📊 Fetching index memberships from NSE...")
    for index_name, url in NSE_INDEX_URLS.items():
        symbols = fetch_index_symbols(session, index_name, url)
        for sym in symbols:
            if sym not in index_map:
                index_map[sym] = []
            if index_name not in index_map[sym]:
                index_map[sym].append(index_name)
        time.sleep(0.8)

    # ── Step 2: Fetch complete NSE equity list ────────────────────────────────
    print("\n📋 Fetching complete NSE equity list...")
    all_nse_symbols = fetch_all_nse_equities()

    # Add any symbols from complete list not already in index_map
    for sym in all_nse_symbols:
        if sym not in index_map:
            index_map[sym] = []   # no specific index, just NSE

    print(f"\n📈 Total unique symbols to validate: {len(index_map)}")

    # ── Step 3: Validate on Yahoo Finance ────────────────────────────────────
    print("\n🔎 Validating on Yahoo Finance (.NS only)...")
    print("   (This takes a few minutes for large lists)\n")

    valid_symbols   = {}
    invalid_symbols = []
    total           = len(index_map)

    for i, (symbol, indices) in enumerate(index_map.items()):
        print(f"  [{i+1}/{total}] {symbol:<15}", end="\r")
        is_valid, ltp = validate_yahoo_symbol(symbol)
        if is_valid:
            valid_symbols[symbol] = {
                "symbol":   symbol,
                "yf_symbol": f"{symbol}.NS",
                "indices":  indices,
                "ltp":      ltp,
            }
        else:
            invalid_symbols.append(symbol)
        time.sleep(0.15)  # rate limit

    print(f"\n\n  ✅ Valid   : {len(valid_symbols)}")
    print(f"  ❌ Invalid : {len(invalid_symbols)}")
    if invalid_symbols[:20]:
        print(f"  ⚠️  Skipped: {', '.join(invalid_symbols[:20])}" +
              ("..." if len(invalid_symbols) > 20 else ""))

    # ── Step 4: Save to JSON ──────────────────────────────────────────────────
    os.makedirs(DATA_DIR, exist_ok=True)
    out_path = os.path.join(DATA_DIR, "nse_symbols.json")

    output = {
        "_updated_at":     datetime.now(IST).isoformat(),
        "_total_valid":    len(valid_symbols),
        "_total_invalid":  len(invalid_symbols),
        "_invalid_list":   invalid_symbols,
        "symbols":         valid_symbols,
    }

    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ Saved → data/nse_symbols.json")
    print(f"   {len(valid_symbols)} valid NSE stocks ready for scanning")
    print("━" * 65)
    return valid_symbols


def load_symbols():
    """
    Load symbols from nse_symbols.json.
    Returns dict: { symbol: { yf_symbol, indices, ltp } }
    """
    path = os.path.join(DATA_DIR, "nse_symbols.json")
    if not os.path.exists(path):
        print("⚠️  nse_symbols.json not found. Run fetch_nse_symbols.py first.")
        return {}
    with open(path) as f:
        data = json.load(f)
    return data.get("symbols", {})


if __name__ == "__main__":
    build_symbol_database()
