#!/usr/bin/env python3
# scripts/fetch_sectors.py
# ─────────────────────────────────────────────────────────────────────────────
# 100% NSE data — most accurate sector rotation calculations
#
#   1D  = percentChange                          ← NSE allIndices (direct)
#   1W  = (last - oneWeekAgoVal) / oneWeekAgoVal ← NSE allIndices (calculated)
#   1M  = perChange30d                           ← NSE allIndices (direct)
#   3M  = closest record to 90 calendar days ago ← niftyindices.com historical
#         (was: hist[63] which = Dec 30, skipping Jan 1-2 holiday bump)
#   1Y  = perChange365d                          ← NSE allIndices (direct)
#
# RS Rank, RRG Quadrant, Signal — auto-calculated
#
# FIX LOG:
#   v1 bug: used hist[63] (63 trading days) = Dec 30 for everyone, which
#           misses the Jan 1-3 holiday period and diverges from Screener/
#           market-standard "3M" which anchors to 90 calendar days ago.
#   v2 fix: find the record whose date is closest to (today - 90 days),
#           matching the industry-standard 3-month return definition.
# ─────────────────────────────────────────────────────────────────────────────

import urllib.request, json, os, time, requests
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

SECTORS = [
    { 'name': 'Auto',          'nse': 'NIFTY AUTO',             'ni': 'NIFTY AUTO'            },
    { 'name': 'Banking',       'nse': 'NIFTY BANK',             'ni': 'NIFTY BANK'            },
    { 'name': 'Commodities',   'nse': 'NIFTY COMMODITIES',      'ni': 'NIFTY COMMODITIES'     },
    { 'name': 'Cons Durables', 'nse': 'NIFTY CONSR DURBL',      'ni': 'NIFTY CONSR DURBL'     },
    { 'name': 'Consumption',   'nse': 'NIFTY CONSUMPTION',      'ni': 'NIFTY CONSUMPTION'     },
    { 'name': 'Defence',       'nse': 'NIFTY IND DEFENCE',      'ni': 'NIFTY INDIA DEFENCE'   },
    { 'name': 'Energy',        'nse': 'NIFTY ENERGY',           'ni': 'NIFTY ENERGY'          },
    { 'name': 'Finance',       'nse': 'NIFTY FIN SERVICE',      'ni': 'NIFTY FIN SERVICE'     },
    { 'name': 'FMCG',          'nse': 'NIFTY FMCG',             'ni': 'NIFTY FMCG'            },
    { 'name': 'Healthcare',    'nse': 'NIFTY HEALTHCARE INDEX',  'ni': 'NIFTY HEALTHCARE'      },
    { 'name': 'Infra',         'nse': 'NIFTY INFRASTRUCTURE',   'ni': 'NIFTY INFRA'           },
    { 'name': 'IT',            'nse': 'NIFTY IT',               'ni': 'NIFTY IT'              },
    { 'name': 'Media',         'nse': 'NIFTY MEDIA',            'ni': 'NIFTY MEDIA'           },
    { 'name': 'Metal',         'nse': 'NIFTY METAL',            'ni': 'NIFTY METAL'           },
    { 'name': 'OilGas',        'nse': 'NIFTY OIL AND GAS',      'ni': 'NIFTY OIL AND GAS'    },
    { 'name': 'Pharma',        'nse': 'NIFTY PHARMA',           'ni': 'NIFTY PHARMA'          },
    { 'name': 'PSE',           'nse': 'NIFTY PSE',              'ni': 'NIFTY PSE'             },
    { 'name': 'PSUBank',       'nse': 'NIFTY PSU BANK',         'ni': 'NIFTY PSU BANK'        },
    { 'name': 'PVTBank',       'nse': 'NIFTY PVT BANK',         'ni': 'NIFTY PVT BANK'        },
    { 'name': 'Realty',        'nse': 'NIFTY REALTY',           'ni': 'NIFTY REALTY'          },
    { 'name': 'Service',       'nse': 'NIFTY SERV SECTOR',      'ni': 'NIFTY SERV SECTOR'     },
    { 'name': 'SmallCap',      'nse': 'NIFTY SMLCAP 100',       'ni': 'NIFTY SMLCAP 100'      },
]

def safe_float(v):
    try:
        return float(str(v).replace(',','')) if v not in (None,'','-','NaN') else None
    except: return None

def pct(current, old):
    if not current or not old or old == 0: return None
    return round((current - old) / old * 100, 2)

def fmt(v):
    return 'N/A' if v is None else f"{'+'if v>=0 else ''}{v:.2f}%"


# ── Parse niftyindices date string ────────────────────────────────────────────
def parse_ni_date(date_str):
    """Parse dates like '30 Dec 2025' or '2025-12-30T00:00:00'."""
    for fmt_str in ('%d %b %Y', '%Y-%m-%dT%H:%M:%S', '%d-%b-%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(date_str.strip(), fmt_str)
        except:
            pass
    return None


# ── Find record closest to target date ───────────────────────────────────────
def find_closest_record(hist, target_date):
    """
    From a niftyindices history list (newest first), find the record whose
    date is closest to target_date. Returns (index, record, actual_date).
    """
    best_idx  = None
    best_rec  = None
    best_dt   = None
    best_diff = None

    for i, h in enumerate(hist):
        dt = parse_ni_date(h.get('HistoricalDate', ''))
        if dt is None:
            continue
        diff = abs((dt - target_date).days)
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best_idx  = i
            best_rec  = h
            best_dt   = dt

    return best_idx, best_rec, best_dt


# ── Fetch NSE allIndices ──────────────────────────────────────────────────────
def fetch_nse_all():
    req = urllib.request.Request(
        'https://www.nseindia.com/api/allIndices',
        headers={
            'User-Agent':      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120',
            'Accept':          'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer':         'https://www.nseindia.com/',
        }
    )
    with urllib.request.urlopen(req, timeout=15) as res:
        data = json.loads(res.read().decode('utf-8'))
    return {(d.get('indexSymbol') or '').upper().strip(): d for d in data.get('data', [])}


# ── Fetch 3M from niftyindices.com ───────────────────────────────────────────
def fetch_3m_niftyindices(sectors_data):
    """
    Fetch historical data and find the close price closest to 90 calendar days
    ago (industry-standard "3-month" return, matching Screener.in / Bloomberg).

    WHY 90 calendar days instead of 63 trading days:
      - 63 trading days from Apr 3 2026 = ~Dec 30 2025 (last day of 2025)
      - 90 calendar days from Apr 3 2026 = ~Jan 3 2026 (first trading day of Q1)
      - Screener.in, NSE, and most data vendors use calendar-day anchoring
      - The holiday gap between Dec 30 and Jan 2 causes a real price difference
        (e.g. Defence: Dec 30=7644 vs Jan 2=7787 → 1.9% gap → explains discrepancy)
    """
    print('\n📈 Fetching 3M from niftyindices.com (anchoring to 90 calendar days)...')

    today = datetime.now()
    target_3m = today - timedelta(days=90)   # ← KEY FIX: was implicit 63 trading days

    # Fetch enough history to cover 90 calendar days comfortably
    from_date = (today - timedelta(days=130)).strftime('%b %d %Y')
    to_date   = today.strftime('%b %d %Y')

    print(f'   Target date for 3M anchor: {target_3m.strftime("%d %b %Y")} (90 cal days ago)')

    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120',
        })
        session.get('https://niftyindices.com/reports/historical-data', timeout=30)
        time.sleep(2)
    except Exception as e:
        print(f'  ⚠️  Session init failed: {e}')
        return

    for s in sectors_data:
        ni_name = next((x['ni'] for x in SECTORS if x['name'] == s['name']), None)
        if not ni_name or s.get('last') is None:
            continue
        try:
            payload = json.dumps({'cinfo': json.dumps({
                'name':      ni_name,
                'startDate': from_date,
                'endDate':   to_date,
                'indexName': ni_name
            })})
            res = session.post(
                'https://niftyindices.com/Backpage.aspx/getHistoricaldatatabletoString',
                data=payload,
                headers={
                    'Content-Type':     'application/json; charset=UTF-8',
                    'Accept':           'application/json, text/javascript, */*; q=0.01',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Referer':          'https://niftyindices.com/reports/historical-data',
                },
                timeout=45
            )
            hist = json.loads(json.loads(res.text)['d'])
            if len(hist) < 5:
                print(f'  ⚠️  {s["name"].ljust(16)} too few records ({len(hist)})')
                continue

            current_close = safe_float(hist[0]['CLOSE'])

            # ── KEY FIX: find record closest to 90 calendar days ago ──────────
            idx, rec, actual_dt = find_closest_record(hist, target_3m)

            if rec is None:
                print(f'  ⚠️  {s["name"].ljust(16)} could not find 3M anchor date')
                continue

            close_3m = safe_float(rec['CLOSE'])
            s['r3m']  = pct(current_close, close_3m)

            days_diff = abs((actual_dt - target_3m).days)
            flag = '' if days_diff <= 3 else f' ⚠️ {days_diff}d off target'

            print(
                f'  ✅ {s["name"].ljust(16)} 3M: {fmt(s["r3m"]).rjust(8)}'
                f'  (anchor: {actual_dt.strftime("%d %b %Y")}  close={close_3m}){flag}'
            )
            time.sleep(0.8)

        except Exception as e:
            print(f'  ⚠️  {s["name"].ljust(16)} 3M failed: {str(e)[:60]}')
            time.sleep(1)


# ── RS Rank, RRG, Signal ──────────────────────────────────────────────────────
def calculate_signals(sectors):
    valid = sorted(
        [s for s in sectors if s.get('r1m') is not None],
        key=lambda s: s['r1m'], reverse=True
    )
    total = len(valid)
    for i, s in enumerate(valid):
        rank = i + 1
        s['rsRank'] = rank
        pp  = rank / total
        mom = ('rising'  if (s.get('r1w') or 0) >  0.5 else
               'falling' if (s.get('r1w') or 0) < -0.5 else 'flat')

        if   pp <= 0.25 and mom != 'falling': s['rrg'] = 'Leading';   s['signal'] = 'OVERWEIGHT'
        elif pp <= 0.25:                       s['rrg'] = 'Weakening'; s['signal'] = 'REDUCE'
        elif pp <= 0.55 and mom == 'rising':   s['rrg'] = 'Improving'; s['signal'] = 'ACCUMULATE'
        elif pp <= 0.55:                       s['rrg'] = 'Neutral';   s['signal'] = 'HOLD'
        elif pp > 0.80:                        s['rrg'] = 'Lagging';   s['signal'] = 'EXIT'
        else:                                  s['rrg'] = 'Weakening'; s['signal'] = 'REDUCE'

    for s in sectors:
        if s.get('r1m') is None:
            s.update({'rsRank': None, 'rrg': None, 'signal': None})

    return sectors


# ── Main ──────────────────────────────────────────────────────────────────────
def fetch_sectors():
    now_ist  = datetime.now(IST)
    day_name = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][now_ist.weekday()]

    print('━' * 68)
    print(f'🔄 NSE Sector Rotation — {day_name} {now_ist.strftime("%Y-%m-%d %H:%M")} IST')
    print('   1D / 1W / 1M / 1Y → NSE allIndices (direct)')
    print('   3M                → niftyindices.com (closest to 90 cal days ago) ← FIXED')
    print('   RS Rank / RRG / Signal → auto-calculated')
    print('━' * 68 + '\n')

    # Step 1: NSE allIndices
    print('📡 Fetching NSE allIndices...')
    try:
        index_map = fetch_nse_all()
        print(f'   ✅ Got {len(index_map)} indices\n')
    except Exception as e:
        print(f'   ❌ Failed: {e}')
        write_output([]); return

    # Step 2: Extract each sector
    sectors = []
    for s in SECTORS:
        nse_sym = s['nse'].upper().strip()
        found   = index_map.get(nse_sym)
        if not found:
            for sym, idx in index_map.items():
                if nse_sym in sym or sym in nse_sym:
                    found = idx; break

        if found:
            current = safe_float(found.get('last'))
            wk1     = safe_float(found.get('oneWeekAgoVal'))
            r1d     = safe_float(found.get('percentChange'))
            r1w     = pct(current, wk1)
            r1m     = safe_float(found.get('perChange30d')) or pct(current, safe_float(found.get('oneMonthAgoVal')))
            r1y     = safe_float(found.get('perChange365d'))

            entry = {
                'name':     s['name'],
                'source':   'NSE',
                'last':     current,
                'lastDate': found.get('previousDay', now_ist.strftime('%d-%b-%Y')),
                'r1d': r1d, 'r1w': r1w, 'r1m': r1m, 'r3m': None, 'r1y': r1y,
            }
            sectors.append(entry)
            print(f"  ✅ {s['name'].ljust(16)}  1D:{fmt(r1d).rjust(8)}  1W:{fmt(r1w).rjust(8)}  1M:{fmt(r1m).rjust(8)}  1Y:{fmt(r1y).rjust(8)}")
        else:
            print(f"  ⚠️  {s['name'].ljust(16)} NOT FOUND in NSE allIndices")
            sectors.append({
                'name': s['name'], 'source': 'NSE', 'last': None, 'lastDate': None,
                'r1d': None, 'r1w': None, 'r1m': None, 'r3m': None, 'r1y': None
            })

    # Step 3: 3M from niftyindices.com (FIXED: 90 calendar days anchor)
    fetch_3m_niftyindices(sectors)

    # Step 4: RS Rank, RRG, Signal
    sectors = calculate_signals(sectors)

    # Summary
    valid   = [s for s in sectors if s.get('r1d') is not None]
    ranked  = sorted([s for s in sectors if s.get('rsRank')], key=lambda x: x['rsRank'])
    with_3m = [s for s in sectors if s.get('r3m') is not None]

    print('\n' + '━' * 68)
    print(f'📊 {len(valid)}/{len(sectors)} sectors fetched | 3M data: {len(with_3m)}/{len(sectors)}')
    print(f'📅 As of: {now_ist.strftime("%d %b %Y %H:%M IST")}')
    if ranked:
        print('\n🏆 Top 5 (RS Rank by 1M):')
        for s in ranked[:5]:
            print(f"   #{s['rsRank']} {s['name'].ljust(16)} 1M:{fmt(s.get('r1m')).rjust(8)}  3M:{fmt(s.get('r3m')).rjust(8)}  {s.get('rrg')} → {s.get('signal')}")
        print('📉 Bottom 5:')
        for s in ranked[-5:]:
            print(f"   #{s['rsRank']} {s['name'].ljust(16)} 1M:{fmt(s.get('r1m')).rjust(8)}  3M:{fmt(s.get('r3m')).rjust(8)}  {s.get('rrg')} → {s.get('signal')}")

    write_output(sectors)


def write_output(sectors):
    out = {
        '_updated_at': datetime.now(timezone.utc).isoformat(),
        '_source':     'NSE allIndices (1D/1W/1M/1Y) + niftyindices.com (3M = 90 calendar days anchor)',
        '_note':       '1D=NSE percentChange | 1W=(last-1wkAgo)/1wkAgo | 1M=NSE perChange30d | 3M=niftyindices closest to 90 cal days | 1Y=NSE perChange365d',
        '_fix':        'v2: 3M now anchors to 90 calendar days (not 63 trading days) to match Screener.in / market standard',
        'sectors':     sectors
    }
    out_dir  = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
    out_path = os.path.join(out_dir, 'sector-returns.json')
    os.makedirs(out_dir, exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2)
    print(f'\n✅ Saved {len(sectors)} sectors → data/sector-returns.json')
    print('━' * 68)


if __name__ == '__main__':
    fetch_sectors()
