#!/usr/bin/env python3
# scripts/fetch_sectors.py
# ─────────────────────────────────────────────────────────────────────────────
# 100% NSE data — accurate sector rotation calculations
#
#   1D  = percentChange                          ← NSE allIndices (direct, live)
#   1W  = (last - close_5td_ago) / close_5td_ago ← niftyindices.com historical
#   1M  = (last - close_1cal_month_ago)          ← niftyindices.com historical
#   3M  = (last - close_3cal_months_ago)         ← niftyindices.com historical
#   1Y  = (last - close_1cal_year_ago)           ← niftyindices.com historical
#
# Using calendar-month lookups (like Investing.com) instead of fixed trading
# day counts, so numbers match external references closely.
#
# RS Rank, RRG Quadrant, Signal — auto-calculated
# ─────────────────────────────────────────────────────────────────────────────

import urllib.request, json, os, time, requests
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta

IST = timezone(timedelta(hours=5, minutes=30))

SECTORS = [
    { 'name': 'Auto',          'nse': 'NIFTY AUTO',            'ni': 'NIFTY AUTO'               },
    { 'name': 'Banking',       'nse': 'NIFTY BANK',            'ni': 'NIFTY BANK'               },
    { 'name': 'Commodities',   'nse': 'NIFTY COMMODITIES',     'ni': 'NIFTY COMMODITIES'        },
    { 'name': 'Cons Durables', 'nse': 'NIFTY CONSR DURBL',     'ni': 'NIFTY CONSR DURBL'        },
    { 'name': 'Consumption',   'nse': 'NIFTY CONSUMPTION',     'ni': 'NIFTY CONSUMPTION'        },
    { 'name': 'Defence',       'nse': 'NIFTY IND DEFENCE',     'ni': 'NIFTY INDIA DEFENCE'      },
    { 'name': 'Energy',        'nse': 'NIFTY ENERGY',          'ni': 'NIFTY ENERGY'             },
    { 'name': 'Finance',       'nse': 'NIFTY FIN SERVICE',     'ni': 'NIFTY FIN SERVICE'        },
    { 'name': 'FMCG',          'nse': 'NIFTY FMCG',            'ni': 'NIFTY FMCG'               },
    { 'name': 'Healthcare',    'nse': 'NIFTY HEALTHCARE INDEX', 'ni': 'NIFTY HEALTHCARE'         },
    { 'name': 'Infra',         'nse': 'NIFTY INFRASTRUCTURE',  'ni': 'NIFTY INFRA'              },
    { 'name': 'IT',            'nse': 'NIFTY IT',              'ni': 'NIFTY IT'                 },
    { 'name': 'Media',         'nse': 'NIFTY MEDIA',           'ni': 'NIFTY MEDIA'              },
    { 'name': 'Metal',         'nse': 'NIFTY METAL',           'ni': 'NIFTY METAL'              },
    { 'name': 'OilGas',        'nse': 'NIFTY OIL AND GAS',     'ni': 'NIFTY OIL AND GAS'        },
    { 'name': 'Pharma',        'nse': 'NIFTY PHARMA',          'ni': 'NIFTY PHARMA'             },
    { 'name': 'PSE',           'nse': 'NIFTY PSE',             'ni': 'NIFTY PSE'                },
    { 'name': 'PSUBank',       'nse': 'NIFTY PSU BANK',        'ni': 'NIFTY PSU BANK'           },
    { 'name': 'PVTBank',       'nse': 'NIFTY PVT BANK',        'ni': 'NIFTY PVT BANK'           },
    { 'name': 'Realty',        'nse': 'NIFTY REALTY',          'ni': 'NIFTY REALTY'             },
    { 'name': 'Service',       'nse': 'NIFTY SERV SECTOR',     'ni': 'NIFTY SERV SECTOR'        },
    { 'name': 'SmallCap',      'nse': 'NIFTY SMLCAP 100',      'ni': 'NIFTY SMLCAP 100'         },
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

# ── Find closest available close on or before target_date in sorted hist ────
def find_close_on_or_before(hist, target_date):
    """
    hist: list of dicts with 'HistoricalDate' (str 'DD-Mon-YYYY') and 'CLOSE'
          sorted newest-first from niftyindices.com
    target_date: datetime object
    Returns float close or None
    """
    for row in reversed(hist):  # oldest first
        try:
            row_date = datetime.strptime(row['HistoricalDate'].strip(), '%d-%b-%Y')
        except:
            continue
        if row_date <= target_date:
            return safe_float(row['CLOSE']), row['HistoricalDate']
    return None, None

# ── Fetch NSE allIndices ──────────────────────────────────────────────────
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

# ── Fetch full historical and compute all timeframes from closes ─────────
def fetch_historical_all_timeframes(sectors_data):
    """
    Fetches ~400 calendar days of history from niftyindices.com for each
    sector, then derives 1W, 1M, 3M, 1Y from actual closing prices
    (calendar-month lookbacks, matching Investing.com methodology).
    """
    print('\n📈 Fetching historical closes from niftyindices.com (1W/1M/3M/1Y)...')
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120',
        })
        session.get('https://niftyindices.com/reports/historical-data', timeout=30)
        time.sleep(2)
    except Exception as e:
        print(f'  ⚠️  Session failed: {e}')
        return

    today = datetime.now(IST).replace(tzinfo=None)

    # Calendar-based lookback targets (same as Investing.com)
    targets = {
        '1w':  today - timedelta(days=7),
        '1m':  today - relativedelta(months=1),
        '3m':  today - relativedelta(months=3),
        '1y':  today - relativedelta(years=1),
    }

    # Fetch ~400 calendar days (covers 1Y + buffer)
    from_date = (today - timedelta(days=400)).strftime('%b %d %Y')
    to_date   = today.strftime('%b %d %Y')

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
            if len(hist) < 10:
                print(f'  ⚠️  {s["name"].ljust(16)} insufficient history ({len(hist)} rows)')
                time.sleep(1)
                continue

            # hist[0] = most recent trading day close (yesterday or today if after close)
            current_close = safe_float(hist[0]['CLOSE'])
            if not current_close:
                time.sleep(1)
                continue

            results = {}
            for period, target_dt in targets.items():
                close_val, close_date = find_close_on_or_before(hist, target_dt)
                results[period] = pct(current_close, close_val) if close_val else None

            s['r1w'] = results['1w']
            s['r1m'] = results['1m']
            s['r3m'] = results['3m']
            s['r1y'] = results['1y']

            print(
                f"  ✅ {s['name'].ljust(16)}"
                f"  1W:{fmt(s['r1w']).rjust(8)}"
                f"  1M:{fmt(s['r1m']).rjust(8)}"
                f"  3M:{fmt(s['r3m']).rjust(8)}"
                f"  1Y:{fmt(s['r1y']).rjust(8)}"
            )
            time.sleep(0.8)

        except Exception as e:
            print(f'  ⚠️  {s["name"].ljust(16)} failed: {str(e)[:60]}')
            time.sleep(1)

# ── RS Rank, RRG, Signal ──────────────────────────────────────────────────
def calculate_signals(sectors):
    valid = sorted([s for s in sectors if s.get('r1m') is not None],
                   key=lambda s: s['r1m'], reverse=True)
    total = len(valid)
    for i, s in enumerate(valid):
        rank = i + 1
        s['rsRank'] = rank
        pp  = rank / total
        mom = 'rising'  if (s.get('r1w') or 0) > 0.5  else \
              'falling' if (s.get('r1w') or 0) < -0.5 else 'flat'
        if   pp <= 0.25 and mom != 'falling': s['rrg']='Leading';   s['signal']='OVERWEIGHT'
        elif pp <= 0.25:                       s['rrg']='Weakening'; s['signal']='REDUCE'
        elif pp <= 0.55 and mom=='rising':     s['rrg']='Improving'; s['signal']='ACCUMULATE'
        elif pp <= 0.55:                       s['rrg']='Neutral';   s['signal']='HOLD'
        elif pp > 0.80:                        s['rrg']='Lagging';   s['signal']='EXIT'
        else:                                  s['rrg']='Weakening'; s['signal']='REDUCE'
    for s in sectors:
        if s.get('r1m') is None:
            s.update({'rsRank': None, 'rrg': None, 'signal': None})
    return sectors

# ── Main ──────────────────────────────────────────────────────────────────
def fetch_sectors():
    now_ist  = datetime.now(IST)
    day_name = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][now_ist.weekday()]

    print('━' * 65)
    print(f'🔄 NSE Sector Rotation — {day_name} {now_ist.strftime("%Y-%m-%d %H:%M")} IST')
    print('   1D   → NSE allIndices percentChange (live intraday)')
    print('   1W   → niftyindices close on/before (today - 7 days)')
    print('   1M   → niftyindices close on/before (today - 1 calendar month)')
    print('   3M   → niftyindices close on/before (today - 3 calendar months)')
    print('   1Y   → niftyindices close on/before (today - 1 calendar year)')
    print('   RS Rank / RRG / Signal → auto-calculated')
    print('━' * 65 + '\n')

    # Step 1: NSE allIndices — get live 1D and current price
    print('📡 Fetching NSE allIndices (live 1D + current price)...')
    try:
        index_map = fetch_nse_all()
        print(f'   ✅ Got {len(index_map)} indices\n')
    except Exception as e:
        print(f'   ❌ Failed: {e}')
        write_output([]); return

    # Step 2: Extract 1D and current price for each sector
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
            r1d     = safe_float(found.get('percentChange'))
            entry = {
                'name':     s['name'],
                'source':   'NSE+niftyindices',
                'last':     current,
                'lastDate': found.get('previousDay', now_ist.strftime('%d-%b-%Y')),
                # 1D from NSE live; rest filled by historical fetch below
                'r1d': r1d, 'r1w': None, 'r1m': None, 'r3m': None, 'r1y': None,
            }
            sectors.append(entry)
            print(f"  ✅ {s['name'].ljust(16)}  1D:{fmt(r1d).rjust(8)}  last={current}")
        else:
            print(f"  ⚠️  {s['name'].ljust(16)} NOT FOUND in NSE allIndices")
            sectors.append({'name':s['name'],'source':'NSE+niftyindices','last':None,'lastDate':None,
                            'r1d':None,'r1w':None,'r1m':None,'r3m':None,'r1y':None})

    # Step 3: 1W / 1M / 3M / 1Y from niftyindices historical closes
    fetch_historical_all_timeframes(sectors)

    # Step 4: RS Rank, RRG, Signal
    sectors = calculate_signals(sectors)

    # Summary
    valid   = [s for s in sectors if s.get('r1d') is not None]
    ranked  = sorted([s for s in sectors if s.get('rsRank')], key=lambda x: x['rsRank'])
    with_1m = [s for s in sectors if s.get('r1m') is not None]

    print('\n' + '━' * 65)
    print(f'📊 {len(valid)}/{len(sectors)} sectors | 1M+ data: {len(with_1m)}/{len(sectors)}')
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
        '_source':     'NSE allIndices (1D live) + niftyindices.com historical (1W/1M/3M/1Y)',
        '_note':       '1D=NSE percentChange | 1W/1M/3M/1Y=niftyindices calendar-lookback closes (matches Investing.com)',
        'sectors':     sectors
    }
    out_dir  = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
    out_path = os.path.join(out_dir, 'sector-returns.json')
    os.makedirs(out_dir, exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2)
    print(f'\n✅ Saved {len(sectors)} sectors → data/sector-returns.json')
    print('━' * 65)

if __name__ == '__main__':
    fetch_sectors()
