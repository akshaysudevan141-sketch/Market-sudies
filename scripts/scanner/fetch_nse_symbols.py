#!/usr/bin/env python3
# scripts/scanner/fetch_nse_symbols.py
# Fetches ALL NSE index constituents + validates on Yahoo Finance (.NS stocks only)

import requests, yfinance as yf, json, os, time
from datetime import datetime, timezone, timedelta

IST      = timezone(timedelta(hours=5, minutes=30))
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://www.nseindia.com/",
    "Connection":      "keep-alive",
}

# ── ALL NSE Indices → API index key mapping ───────────────────────────────────
# Source: https://www.nseindia.com → Indices section
NSE_INDICES = {
    # ── Broad Market ──────────────────────────────────────────────────────────
    "Nifty 50":              "NIFTY%2050",
    "Nifty Next 50":         "NIFTY%20NEXT%2050",
    "Nifty 100":             "NIFTY%20100",
    "Nifty 200":             "NIFTY%20200",
    "Nifty 500":             "NIFTY%20500",
    "Nifty Midcap 50":       "NIFTY%20MIDCAP%2050",
    "Nifty Midcap 100":      "NIFTY%20MIDCAP%20100",
    "Nifty Midcap 150":      "NIFTY%20MIDCAP%20150",
    "Nifty Smallcap 50":     "NIFTY%20SMLCAP%2050",
    "Nifty Smallcap 100":    "NIFTY%20SMLCAP%20100",
    "Nifty Smallcap 250":    "NIFTY%20SMLCAP%20250",
    "Nifty Microcap 250":    "NIFTY%20MICROCAP250",
    "Nifty LargeMidcap 250": "NIFTY%20LARGEMIDCAP%20250",
    "Nifty MidSmall 400":    "NIFTY%20MIDSML%20400",
    "Nifty Total Market":    "NIFTY%20TOTAL%20MARKET",

    # ── Sectoral ──────────────────────────────────────────────────────────────
    "Bank Nifty":            "NIFTY%20BANK",
    "Nifty Auto":            "NIFTY%20AUTO",
    "Nifty Cement":          "NIFTY%20CONSTR",
    "Nifty Chemicals":       "NIFTY%20CHEMICALS",
    "Nifty Consumer Dur":    "NIFTY%20CONSR%20DURBL",
    "Nifty Energy":          "NIFTY%20ENERGY",
    "Nifty Finance":         "NIFTY%20FIN%20SERVICE",
    "Nifty FMCG":            "NIFTY%20FMCG",
    "Nifty Healthcare":      "NIFTY%20HEALTHCARE%20INDEX",
    "Nifty Infra":           "NIFTY%20INFRA",
    "Nifty IT":              "NIFTY%20IT",
    "Nifty Media":           "NIFTY%20MEDIA",
    "Nifty Metal":           "NIFTY%20METAL",
    "Nifty MNC":             "NIFTY%20MNC",
    "Nifty Oil and Gas":     "NIFTY%20OIL%20AND%20GAS",
    "Nifty Pharma":          "NIFTY%20PHARMA",
    "Nifty PSE":             "NIFTY%20PSE",
    "Nifty PSU Bank":        "NIFTY%20PSU%20BANK",
    "Nifty Pvt Bank":        "NIFTY%20PVT%20BANK",
    "Nifty Realty":          "NIFTY%20REALTY",

    # ── Thematic ──────────────────────────────────────────────────────────────
    "Nifty Commodities":     "NIFTY%20COMMODITIES",
    "Nifty CPSE":            "NIFTY%20CPSE",
    "Nifty Defence":         "NIFTY%20IND%20DEFENCE",
    "Nifty India Mfg":       "NIFTY%20INDIA%20MANUFACTURING",
    "Nifty Mobility":        "NIFTY%20INDIA%20MOBILITY",
    "Nifty REITs":           "NIFTY%20REITS%20%26%20INVITS",

    # ── F&O ───────────────────────────────────────────────────────────────────
    "F&O":                   "SECURITIES%20IN%20F%26O",
}

# ── Words/patterns that indicate an INDEX NAME, not a stock symbol ────────────
INDEX_PREFIXES = (
    "NIFTY", "SENSEX", "INDIA VIX", "BSE", "CNX",
    "CRISIL", "MSEI", "CDSL", "NSDL",
)

def is_valid_stock_symbol(sym):
    """Return True only if sym looks like a real NSE stock ticker."""
    if not sym or len(sym) > 20:
        return False
    if " " in sym:                          # index names have spaces
        return False
    if sym.startswith("$"):                 # yfinance prefix artifact
        return False
    for prefix in INDEX_PREFIXES:
        if sym.upper().startswith(prefix):
            return False
    # Must contain at least one letter
    if not any(c.isalpha() for c in sym):
        return False
    return True

def get_nse_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        session.get("https://www.nseindia.com", timeout=10)
        time.sleep(1)
    except Exception as e:
        print(f"  ⚠️  Session: {e}")
    return session

def fetch_index_constituents(session, index_name, index_key):
    """Fetch constituent stocks of one NSE index."""
    url = f"https://www.nseindia.com/api/equity-stockIndices?index={index_key}"
    try:
        res = session.get(url, timeout=15)
        if res.status_code != 200:
            print(f"  ⚠️  {index_name:<28} HTTP {res.status_code}")
            return []
        data    = res.json()
        symbols = []
        for item in data.get("data", []):
            sym = item.get("symbol", "").strip()
            if is_valid_stock_symbol(sym):
                symbols.append(sym)
        print(f"  ✅ {index_name:<28} {len(symbols):>4} stocks")
        return symbols
    except Exception as e:
        print(f"  ❌ {index_name:<28} {str(e)[:50]}")
        return []

def fetch_all_nse_equities():
    """Fetch complete NSE equity list from NSE archives CSV (~2000+ stocks)."""
    url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    try:
        print("  Downloading NSE equity master CSV...")
        res = requests.get(url, headers=HEADERS, timeout=30)
        if res.status_code != 200:
            print(f"  ❌ HTTP {res.status_code}")
            return []
        lines   = res.text.strip().split("\n")
        symbols = []
        for line in lines[1:]:
            cols = line.split(",")
            if cols:
                sym = cols[0].strip().replace('"', '')
                if is_valid_stock_symbol(sym):
                    symbols.append(sym)
        print(f"  ✅ Got {len(symbols)} NSE equity symbols")
        return symbols
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return []

def validate_yahoo_nse(symbol, test_period="5d"):
    """
    Check symbol on Yahoo Finance as SYMBOL.NS (NSE only).
    Returns (is_valid, ltp)
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
    print("━" * 65)
    print("🔍 NSE Symbol Database Builder")
    print(f"   Fetching {len(NSE_INDICES)} indices from NSE India")
    print("   Validating each stock on Yahoo Finance (.NS only)")
    print("━" * 65)

    session   = get_nse_session()
    index_map = {}   # { symbol: [list of index names] }

    # ── Step 1: Fetch all index constituents ──────────────────────────────────
    print(f"\n📊 Fetching index constituents from NSE India API...")
    for idx_name, idx_key in NSE_INDICES.items():
        syms = fetch_index_constituents(session, idx_name, idx_key)
        for sym in syms:
            if sym not in index_map:
                index_map[sym] = []
            if idx_name not in index_map[sym]:
                index_map[sym].append(idx_name)
        time.sleep(0.5)

    print(f"\n  📈 Unique stocks across all indices: {len(index_map)}")

    # ── Step 2: Add remaining NSE equities not in any index ───────────────────
    print("\n📋 Fetching complete NSE equity master list...")
    all_syms = fetch_all_nse_equities()
    added = 0
    for sym in all_syms:
        if sym not in index_map:
            index_map[sym] = []   # not in any named index
            added += 1
    print(f"  ➕ {added} additional stocks from NSE master list")
    print(f"  📊 Total unique symbols to validate: {len(index_map)}")

    # ── Step 3: Validate every symbol on Yahoo Finance (.NS only) ─────────────
    print(f"\n🔎 Validating on Yahoo Finance (.NS only)...")
    print("   Only stocks with valid Yahoo data will be scanned\n")

    valid   = {}
    invalid = []
    total   = len(index_map)

    for i, (sym, indices) in enumerate(index_map.items()):
        print(f"  [{i+1:>4}/{total}] {sym:<16}", end="\r")
        ok, ltp = validate_yahoo_nse(sym)
        if ok:
            valid[sym] = {
                "symbol":    sym,
                "yf_symbol": f"{sym}.NS",
                "indices":   indices,
                "ltp":       ltp,
            }
        else:
            invalid.append(sym)
        time.sleep(0.12)

    print(f"\n\n{'─'*65}")
    print(f"  ✅ Valid on Yahoo (.NS)  : {len(valid)}")
    print(f"  ❌ Not found / delisted  : {len(invalid)}")
    if invalid[:20]:
        print(f"  ⚠️  Sample skipped       : {', '.join(invalid[:20])}")
    print(f"{'─'*65}")

    # ── Step 4: Show index breakdown ──────────────────────────────────────────
    from collections import Counter
    idx_count = Counter()
    for info in valid.values():
        for idx in info["indices"]:
            idx_count[idx] += 1
    print(f"\n  Index Breakdown:")
    for idx, cnt in sorted(idx_count.items(), key=lambda x: -x[1]):
        print(f"    {idx:<30} {cnt:>4} stocks")

    # ── Step 5: Save ──────────────────────────────────────────────────────────
    os.makedirs(DATA_DIR, exist_ok=True)
    out = {
        "_updated_at":    datetime.now(IST).isoformat(),
        "_total_valid":   len(valid),
        "_total_invalid": len(invalid),
        "_invalid_list":  invalid,
        "_index_keys":    list(NSE_INDICES.keys()),
        "symbols":        valid,
    }
    path = os.path.join(DATA_DIR, "nse_symbols.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)

    print(f"\n✅ Saved → data/nse_symbols.json")
    print(f"   {len(valid)} valid NSE stocks (.NS) ready for scanning")
    print("━" * 65)
    return valid


def load_symbols():
    """Load validated symbol list from cache."""
    path = os.path.join(DATA_DIR, "nse_symbols.json")
    if not os.path.exists(path):
        print("⚠️  nse_symbols.json not found. Run fetch_nse_symbols.py first.")
        return {}
    with open(path) as f:
        data = json.load(f)
    return data.get("symbols", {})


if __name__ == "__main__":
    build_symbol_database()
