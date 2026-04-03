#!/usr/bin/env python3

import requests
import json
import os
import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# ─────────────────────────────────────────────
# NSE SECTORS
# ─────────────────────────────────────────────
SECTORS = [
    "NIFTY AUTO",
    "NIFTY BANK",
    "NIFTY COMMODITIES",
    "NIFTY CONSR DURBL",
    "NIFTY CONSUMPTION",
    "NIFTY IND DEFENCE",
    "NIFTY ENERGY",
    "NIFTY FIN SERVICE",
    "NIFTY FMCG",
    "NIFTY HEALTHCARE INDEX",
    "NIFTY INFRASTRUCTURE",
    "NIFTY IT",
    "NIFTY MEDIA",
    "NIFTY METAL",
    "NIFTY OIL AND GAS",
    "NIFTY PHARMA",
    "NIFTY PSE",
    "NIFTY PSU BANK",
    "NIFTY PVT BANK",
    "NIFTY REALTY",
    "NIFTY SERV SECTOR",
    "NIFTY SMLCAP 100"
]

# ─────────────────────────────────────────────
# NSE HEADERS
# ─────────────────────────────────────────────
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": "https://www.nseindia.com/"
}

# ─────────────────────────────────────────────
# NSE SESSION
# ─────────────────────────────────────────────
class NSE:

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

        # warmup request for cookies
        self.session.get("https://www.nseindia.com", timeout=10)
        time.sleep(1)

    def get(self, url, params=None):

        for i in range(3):
            try:
                r = self.session.get(url, params=params, timeout=20)

                if r.status_code == 200:
                    return r.json()

                time.sleep(1)

            except Exception:
                time.sleep(1)

        return None


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def parse_date(s):

    formats = ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d")

    for f in formats:
        try:
            return datetime.strptime(s, f)
        except:
            pass

    return None


def pct(new, old):

    if not new or not old:
        return None

    return round((new - old) / old * 100, 2)


def closest_record(records, target):

    best = None
    diff = None

    for r in records:

        dt = parse_date(
            r.get("EOD_TIMESTAMP") or r.get("HistoricalDate") or ""
        )

        val = float(
            r.get("EOD_CLOSE_INDEX_VAL") or r.get("CLOSE") or 0
        )

        if not dt or not val:
            continue

        d = abs((dt - target).days)

        if diff is None or d < diff:
            best = (dt, val)
            diff = d

    return best


# ─────────────────────────────────────────────
# FETCH SECTOR RETURNS
# ─────────────────────────────────────────────
def fetch_sector(nse, index):

    today = datetime.now()

    anchors = {
        "1D": today - timedelta(days=1),
        "1W": today - timedelta(days=7),
        "1M": today - relativedelta(months=1),
        "3M": today - relativedelta(months=3),
        "1Y": today - relativedelta(years=1),
    }

    data = nse.get(
        "https://www.nseindia.com/api/historical/indicesHistory",
        params={
            "indexType": index,
            "from": (today - relativedelta(years=1, days=10)).strftime("%d-%m-%Y"),
            "to": today.strftime("%d-%m-%Y"),
        }
    )

    if not data:
        return None

    records = data.get("data", {}).get("indexCloseOnlineRecords", [])

    if not records:
        return None

    # sort by date
    records.sort(key=lambda r: parse_date(
        r.get("EOD_TIMESTAMP") or r.get("HistoricalDate") or ""
    ))

    latest = closest_record(records, today)

    if not latest:
        return None

    latest_val = latest[1]

    result = {
        "index": index,
        "last": latest_val
    }

    for k, anchor in anchors.items():

        rec = closest_record(records, anchor)

        if rec:
            result[k] = pct(latest_val, rec[1])
        else:
            result[k] = None

    return result


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def run():

    print("🚀 Fetching NSE Sector Returns\n")

    nse = NSE()

    output = []

    for sector in SECTORS:

        try:

            print("Fetching:", sector)

            data = fetch_sector(nse, sector)

            if data:
                output.append(data)

                print(
                    f"1D:{data['1D']}% "
                    f"1W:{data['1W']}% "
                    f"1M:{data['1M']}% "
                    f"3M:{data['3M']}% "
                    f"1Y:{data['1Y']}%"
                )

            time.sleep(0.4)

        except Exception as e:
            print("Error:", sector, e)

    os.makedirs("data", exist_ok=True)

    with open("data/sector_returns.json", "w") as f:
        json.dump(output, f, indent=2)

    print("\n✅ Sector data saved to data/sector_returns.json\n")


if __name__ == "__main__":
    run()
