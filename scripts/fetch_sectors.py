#!/usr/bin/env python3
# NSE Sector Returns — Clean Version (Investing-style)

import urllib.request, urllib.parse, json, time, os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
SECTORS = [
    'NIFTY AUTO','NIFTY BANK','NIFTY COMMODITIES','NIFTY CONSR DURBL',
    'NIFTY CONSUMPTION','NIFTY IND DEFENCE','NIFTY ENERGY',
    'NIFTY FIN SERVICE','NIFTY FMCG','NIFTY HEALTHCARE INDEX',
    'NIFTY INFRASTRUCTURE','NIFTY IT','NIFTY MEDIA','NIFTY METAL',
    'NIFTY OIL AND GAS','NIFTY PHARMA','NIFTY PSE','NIFTY PSU BANK',
    'NIFTY PVT BANK','NIFTY REALTY','NIFTY SERV SECTOR','NIFTY SMLCAP 100'
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'Referer': 'https://www.nseindia.com/'
}

# ─────────────────────────────────────────────────────────────
# SESSION (handles NSE cookies)
# ─────────────────────────────────────────────────────────────
import http.cookiejar

class NSE:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )
        self._warm()

    def _warm(self):
        req = urllib.request.Request("https://www.nseindia.com", headers=HEADERS)
        self.opener.open(req)
        time.sleep(1)

    def get(self, url, params=None):
        if params:
            url += "?" + urllib.parse.urlencode(params)

        req = urllib.request.Request(url, headers=HEADERS)
        with self.opener.open(req) as res:
            data = res.read()
            try:
                import gzip
                data = gzip.decompress(data)
            except:
                pass
            return json.loads(data.decode())

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
def parse_date(s):
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except:
            pass
    return None

def pct(new, old):
    if not new or not old:
        return None
    return round((new - old) / old * 100, 2)

def closest_record(records, target):
    best, best_diff = None, None
    for r in records:
        dt = parse_date(
            r.get("EOD_TIMESTAMP") or r.get("HistoricalDate") or ""
        )
        val = float(r.get("EOD_CLOSE_INDEX_VAL") or r.get("CLOSE") or 0)

        if not dt or not val:
            continue

        diff = abs((dt - target).days)

        if best_diff is None or diff < best_diff:
            best = (dt, val)
            best_diff = diff

    return best

# ─────────────────────────────────────────────────────────────
# CORE LOGIC
# ─────────────────────────────────────────────────────────────
def fetch_sector(nse, index):

    today = datetime.now()

    anchors = {
        "1D": today - timedelta(days=1),
        "1W": today - timedelta(weeks=1),
        "1M": today - relativedelta(months=1),
        "3M": today - relativedelta(months=3),
        "1Y": today - relativedelta(years=1),
    }

    # fetch enough history (1 year + buffer)
    data = nse.get(
        "https://www.nseindia.com/api/historical/indicesHistory",
        params={
            "indexType": index,
            "from": (today - relativedelta(years=1, days=10)).strftime("%d-%m-%Y"),
            "to": today.strftime("%d-%m-%Y"),
        }
    )

    records = data.get("data", {}).get("indexCloseOnlineRecords", [])

    if not records:
        return None

    # latest value
    latest_dt, latest_val = closest_record(records, today)

    result = {"index": index, "last": latest_val}

    for key, anchor in anchors.items():
        rec = closest_record(records, anchor)
        if rec:
            result[key] = pct(latest_val, rec[1])
        else:
            result[key] = None

    return result

# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def run():

    print("\n🚀 NSE Sector Returns (Clean v4 — Investing style)\n")

    nse = NSE()
    output = []

    for idx in SECTORS:
        try:
            print(f"Fetching {idx}...")
            data = fetch_sector(nse, idx)

            if data:
                print(
                    f"  1D:{data['1D']}%  1W:{data['1W']}%  "
                    f"1M:{data['1M']}%  3M:{data['3M']}%  1Y:{data['1Y']}%"
                )
                output.append(data)

            time.sleep(0.5)

        except Exception as e:
            print(f"❌ {idx} failed: {e}")

    # save
    os.makedirs("data", exist_ok=True)
    with open("data/sector_returns.json", "w") as f:
        json.dump(output, f, indent=2)

    print("\n✅ Done. Saved to data/sector_returns.json\n")

# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    run()
