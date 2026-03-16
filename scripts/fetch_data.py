"""
fetch_data.py — NSE FII/DII Auto-Fetch Script
=============================================
Run by GitHub Actions daily at 6 PM IST (Mon–Fri).
Writes:
  data/latest.json  — today's session data
  data/history.json — running archive of all sessions (up to 60 days)
"""

import requests, json, os, sys
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

NSE_API = "https://www.nseindia.com/api/fiidiiTradeReact"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://www.nseindia.com/",
    "Connection":      "keep-alive",
}


def fetch_nse():
    """Fetch raw FII/DII cash data from NSE API."""
    session = requests.Session()
    session.headers.update(HEADERS)
    resp = session.get(NSE_API, timeout=25)
    resp.raise_for_status()
    return resp.json()

def fetch_fao_oi(date_str):
    """Fetch F&O Participant OI CSV from NSE Archives."""
    # NSE format: ddmmyyyy (e.g., 16032026)
    formatted_date = datetime.strptime(date_str, "%d-%b-%Y").strftime("%d%m%Y")
    url = f"https://nsearchives.nseindia.com/content/nsccl/fao_participant_oi_{formatted_date}b.csv"
    
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code == 200:
            return resp.text
        # Fallback without 'b'
        url_fallback = f"https://nsearchives.nseindia.com/content/nsccl/fao_participant_oi_{formatted_date}.csv"
        resp = session.get(url_fallback, timeout=15)
        if resp.status_code == 200:
            return resp.text
    except Exception as e:
        print(f"Warning: Failed to fetch F&O data ({e})", file=sys.stderr)
    return None

def parse_fao(csv_text):
    """Parse FII/DII from the OI CSV."""
    fao_data = {}
    if not csv_text: return fao_data
    
    lines = csv_text.strip().split('\n')
    import csv
    reader = csv.reader(lines[1:]) # Skip header row 1, row 2 is actual headers
    next(reader, None)
    
    for row in reader:
        if not row or len(row) < 14: continue
        client_type = row[0].strip()
        if client_type in ["FII", "DII"]:
            fao_data[client_type] = {
                "idx_fut_long":  int(row[1]) if row[1] else 0,
                "idx_fut_short": int(row[2]) if row[2] else 0,
                "idx_call_long": int(row[5]) if row[5] else 0,
                "idx_call_short":int(row[6]) if row[6] else 0,
                "idx_put_long":  int(row[9]) if row[9] else 0,
                "idx_put_short": int(row[10]) if row[10] else 0,
            }
    return fao_data

def transform(raw_cash, raw_fao_csv):
    """Convert NSE raw response to a clean flat dict."""
    out = {
        "date":     "",
        "fii_buy":  0, "fii_sell": 0, "fii_net": 0,
        "dii_buy":  0, "dii_sell": 0, "dii_net": 0,
        # Default F&O fields
        "fii_idx_fut_long": 0, "fii_idx_fut_short": 0, "fii_idx_fut_net": 0,
        "dii_idx_fut_long": 0, "dii_idx_fut_short": 0, "dii_idx_fut_net": 0,
        "fii_idx_call_long": 0, "fii_idx_call_short": 0, "fii_idx_call_net": 0,
        "fii_idx_put_long": 0, "fii_idx_put_short": 0, "fii_idx_put_net": 0,
    }
    
    # 1. Parse Cash Data
    for row in raw_cash:
        cat = (row.get("category") or "").upper()
        if "FII" in cat or "FPI" in cat:
            out["fii_buy"]  = float(row.get("buyValue",  0) or 0)
            out["fii_sell"] = float(row.get("sellValue", 0) or 0)
            out["fii_net"]  = float(row.get("netValue",  0) or 0)
            out["date"]     = row.get("date", "")
        elif "DII" in cat:
            out["dii_buy"]  = float(row.get("buyValue",  0) or 0)
            out["dii_sell"] = float(row.get("sellValue", 0) or 0)
            out["dii_net"]  = float(row.get("netValue",  0) or 0)

    # 2. Parse & Merge F&O Data
    if out["date"]:
        fao_parsed = parse_fao(raw_fao_csv)
        if "FII" in fao_parsed:
            f = fao_parsed["FII"]
            out["fii_idx_fut_long"] = f["idx_fut_long"]
            out["fii_idx_fut_short"] = f["idx_fut_short"]
            out["fii_idx_fut_net"] = f["idx_fut_long"] - f["idx_fut_short"]
            
            out["fii_idx_call_long"] = f["idx_call_long"]
            out["fii_idx_call_short"]= f["idx_call_short"]
            out["fii_idx_call_net"]  = f["idx_call_long"] - f["idx_call_short"]
            
            out["fii_idx_put_long"]  = f["idx_put_long"]
            out["fii_idx_put_short"] = f["idx_put_short"]
            out["fii_idx_put_net"]   = f["idx_put_long"] - f["idx_put_short"]
            
        if "DII" in fao_parsed:
            d = fao_parsed["DII"]
            out["dii_idx_fut_long"] = d["idx_fut_long"]
            out["dii_idx_fut_short"] = d["idx_fut_short"]
            out["dii_idx_fut_net"] = d["idx_fut_long"] - d["idx_fut_short"]

    out["_updated_at"] = datetime.now(IST).strftime("%d-%b-%Y %H:%M IST")
    out["_source"]     = "github-actions"
    return out


def update_history(latest):
    """Append today's data to history.json (keeps last 60 days)."""
    history_path = "data/history.json"
    try:
        with open(history_path) as f:
            history = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        history = []

    # Remove existing entry for same date (avoid duplicates)
    history = [row for row in history if row.get("date") != latest["date"]]
    # Prepend today
    history.insert(0, latest)
    # Keep only last 60 trading days
    history = history[:60]

    with open(history_path, "w") as f:
        json.dump(history, f)

    return history


if __name__ == "__main__":
    print(f"[{datetime.now(IST).strftime('%d-%b-%Y %H:%M IST')}] Fetching NSE FII/DII data...")

    try:
        raw_cash = fetch_nse()
        
        # We need the date from the cash data to fetch the right OI CSV
        date_str = ""
        for row in raw_cash:
            if row.get("category", "").upper() in ["FII", "FPI"]:
                date_str = row.get("date", "")
                break
                
        raw_fao = None
        if date_str:
            raw_fao = fetch_fao_oi(date_str)
            
        data = transform(raw_cash, raw_fao)
    except Exception as e:
        print(f"❌ Fetch failed: {e}", file=sys.stderr)
        sys.exit(1)

    if not data["date"]:
        print("❌ No data returned from NSE (market may be closed).", file=sys.stderr)
        sys.exit(0)  # exit 0 so workflow doesn't fail on holidays

    print(f"✅ Date: {data['date']}")
    print(f"   [CASH] FII Net: {data['fii_net']} | DII Net: {data['dii_net']}")
    print(f"   [F&O]  FII Idx Fut Net: {data.get('fii_idx_fut_net', 0)} | Call Net: {data.get('fii_idx_call_net', 0)} | Put Net: {data.get('fii_idx_put_net', 0)}")

    os.makedirs("data", exist_ok=True)

    # Write latest.json
    with open("data/latest.json", "w") as f:
        json.dump(data, f, indent=2)
    print("✅ Written → data/latest.json")

    # Update rolling history
    update_history(data)
    print("✅ Updated → data/history.json")
