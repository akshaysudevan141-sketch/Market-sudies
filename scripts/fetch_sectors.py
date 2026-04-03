#!/usr/bin/env python3
# scripts/fetch_sectors.py  — v3
# ─────────────────────────────────────────────────────────────────────────────
# ALL data from NSE directly. Zero third-party scrapers.
#
#   1D  = percentChange          ← NSE allIndices
#   1W  = (last-oneWeekAgoVal)   ← NSE allIndices
#   1M  = perChange30d           ← NSE allIndices
#   3M  = NSE indicesHistory API ← closest close to 90 calendar days ago
#   1Y  = perChange365d          ← NSE allIndices  (matches Investing.com ✓)
#
# WHY THIS MATCHES Investing.com / Screener.in:
#   - 1Y: NSE perChange365d is what every data vendor re-publishes
#   - 3M: NSE indicesHistory gives exact NSE closes → find closest to 90 days
#         Investing.com uses the same NSE closes, same 90-day anchor
#   - Previous script used niftyindices.com (complex POST, fragile sessions)
#     replaced with NSE's own GET endpoint (same session, simpler, reliable)
#
# CHANGED vs v1/v2:
#   - 3M now uses NSE indicesHistory instead of niftyindices.com POST
#   - Single NSE session handles both allIndices + indicesHistory
#   - Dropped requests dependency for 3M (urllib only)
# ─────────────────────────────────────────────────────────────────────────────

import urllib.request, urllib.parse, json, os, time
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

SECTORS = [
    { 'name': 'Auto',          'nse': 'NIFTY AUTO',             'hist': 'NIFTY AUTO'              },
    { 'name': 'Banking',       'nse': 'NIFTY BANK',             'hist': 'NIFTY BANK'              },
    { 'name': 'Commodities',   'nse': 'NIFTY COMMODITIES',      'hist': 'NIFTY COMMODITIES'       },
    { 'name': 'Cons Durables', 'nse': 'NIFTY CONSR DURBL',      'hist': 'NIFTY CONSR DURBL'       },
    { 'name': 'Consumption',   'nse': 'NIFTY CONSUMPTION',      'hist': 'NIFTY CONSUMPTION'       },
    { 'name': 'Defence',       'nse': 'NIFTY IND DEFENCE',      'hist': 'NIFTY IND DEFENCE'       },
    { 'name': 'Energy',        'nse': 'NIFTY ENERGY',           'hist': 'NIFTY ENERGY'            },
    { 'name': 'Finance',       'nse': 'NIFTY FIN SERVICE',      'hist': 'NIFTY FIN SERVICE'       },
    { 'name': 'FMCG',          'nse': 'NIFTY FMCG',             'hist': 'NIFTY FMCG'              },
    { 'name': 'Healthcare',    'nse': 'NIFTY HEALTHCARE INDEX',  'hist': 'NIFTY HEALTHCARE INDEX'  },
    { 'name': 'Infra',         'nse': 'NIFTY INFRASTRUCTURE',   'hist': 'NIFTY INFRASTRUCTURE'    },
    { 'name': 'IT',            'nse': 'NIFTY IT',               'hist': 'NIFTY IT'                },
    { 'name': 'Media',         'nse': 'NIFTY MEDIA',            'hist': 'NIFTY MEDIA'             },
    { 'name': 'Metal',         'nse': 'NIFTY METAL',            'hist': 'NIFTY METAL'             },
    { 'name': 'OilGas',        'nse': 'NIFTY OIL AND GAS',      'hist': 'NIFTY OIL AND GAS'       },
    { 'name': 'Pharma',        'nse': 'NIFTY PHARMA',           'hist': 'NIFTY PHARMA'            },
    { 'name': 'PSE',           'nse': 'NIFTY PSE',              'hist': 'NIFTY PSE'               },
    { 'name': 'PSUBank',       'nse': 'NIFTY PSU BANK',         'hist': 'NIFTY PSU BANK'          },
    { 'name': 'PVTBank',       'nse': 'NIFTY PVT BANK',         'hist': 'NIFTY PVT BANK'          },
    { 'name': 'Realty',        'nse': 'NIFTY REALTY',           'hist': 'NIFTY REALTY'            },
    { 'name': 'Service',       'nse': 'NIFTY SERV SECTOR',      'hist': 'NIFTY SERV SECTOR'       },
    { 'name': 'SmallCap',      'nse': 'NIFTY SMLCAP 100',       'hist': 'NIFTY SMLCAP 100'        },
]

NSE_HEADERS = {
    'User-Agent':      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122',
    'Accept':          'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer':         'https://www.nseindia.com/',
    'Connection':      'keep-alive',
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def safe_float(v):
    try:
        return float(str(v).replace(',', '')) if v not in (None, '', '-', 'NaN') else None
    except:
        return None

def pct(current, old):
    if not current or not old or old == 0: return None
    return round((current - old) / old * 100, 2)

def fmt(v):
    return 'N/A' if v is None else f"{'+'if v>=0 else ''}{v:.2f}%"


# ── NSE Session (cookies required for all NSE API calls) ─────────────────────
class NSESession:
    """Maintains a cookie session with NSE, required for all API endpoints."""

    def __init__(self):
        import http.cookiejar
        self.jar     = http.cookiejar.CookieJar()
        self.opener  = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )
        self._warmed = False

    def _warm(self):
        """Visit NSE homepage to get cookies (nsit, nseappid)."""
        if self._warmed:
            return
        req = urllib.request.Request('https://www.nseindia.com/', headers=NSE_HEADERS)
        try:
            self.opener.open(req, timeout=15)
            time.sleep(1.5)
            self._warmed = True
            print('   🍪 NSE session warmed up')
        except Exception as e:
            print(f'   ⚠️  Session warm failed: {e}')

    def get(self, url, params=None, retries=3):
        """GET an NSE API endpoint, returns parsed JSON or None."""
        self._warm()
        if params:
            url = url + '?' + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=NSE_HEADERS)
        for attempt in range(retries):
            try:
                import gzip
                with self.opener.open(req, timeout=20) as res:
                    raw = res.read()
                    # NSE sometimes gzip-encodes even without Accept-Encoding header
                    try:
                        raw = gzip.decompress(raw)
                    except:
                        pass
                    return json.loads(raw.decode('utf-8'))
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise e
        return None


# ── Step 1: NSE allIndices ────────────────────────────────────────────────────
def fetch_nse_all(session):
    data = session.get('https://www.nseindia.com/api/allIndices')
    return {
        (d.get('indexSymbol') or '').upper().strip(): d
        for d in data.get('data', [])
    }


# ── Step 2: NSE indicesHistory for 3M ────────────────────────────────────────
def fetch_3m_nse_history(sectors_data, session):
    """
    Use NSE's own indicesHistory endpoint to get the exact close price
    closest to 90 calendar days ago — the same method Investing.com uses.

    Endpoint: GET /api/historical/indicesHistory
    Params:   indexType=NIFTY IND DEFENCE
              from=03-01-2026   (DD-MM-YYYY)
              to=03-04-2026     (DD-MM-YYYY)

    Response: { "data": { "indexCloseOnlineRecords": [ { "EOD_CLOSE_INDEX_VAL": 7644.35,
                                                         "EOD_TIMESTAMP": "03-Jan-2026" } ] } }
    """
    today      = datetime.now()
    target_3m  = today - timedelta(days=90)   # 90 calendar days = industry standard
    # Fetch a 110-day window so we always have data around the target
    from_date  = (today - timedelta(days=110)).strftime('%d-%m-%Y')
    to_date    = today.strftime('%d-%m-%Y')

    print(f'\n📈 Fetching 3M via NSE indicesHistory (target: {target_3m.strftime("%d %b %Y")})...')

    for s in sectors_data:
        hist_name = next((x['hist'] for x in SECTORS if x['name'] == s['name']), None)
        if not hist_name or s.get('last') is None:
            continue

        try:
            data = session.get(
                'https://www.nseindia.com/api/historical/indicesHistory',
                params={
                    'indexType': hist_name,
                    'from':      from_date,
                    'to':        to_date,
                }
            )

            if not data:
                print(f'  ⚠️  {s["name"].ljust(16)} no response')
                continue

            # NSE returns records in indicesInfo list or indexCloseOnlineRecords
            records = (
                data.get('data', {}).get('indexCloseOnlineRecords') or
                data.get('data', {}).get('indicesInfo') or
                data.get('data', [])
            )

            if not records:
                print(f'  ⚠️  {s["name"].ljust(16)} empty records')
                continue

            # Parse each record and find closest to target_3m
            best_rec   = None
            best_dt    = None
            best_diff  = None

            for rec in records:
                # Field names vary between NSE endpoints
                close = safe_float(
                    rec.get('EOD_CLOSE_INDEX_VAL') or
                    rec.get('CLOSE') or
                    rec.get('close')
                )
                date_str = (
                    rec.get('EOD_TIMESTAMP') or
                    rec.get('HistoricalDate') or
                    rec.get('date') or ''
                ).strip()

                if close is None or not date_str:
                    continue

                # Parse date (NSE uses DD-Mon-YYYY or DD-MM-YYYY)
                dt = None
                for fmt_str in ('%d-%b-%Y', '%d-%m-%Y', '%Y-%m-%d', '%d %b %Y'):
                    try:
                        dt = datetime.strptime(date_str, fmt_str)
                        break
                    except:
                        pass
                if dt is None:
                    continue

                diff = abs((dt - target_3m).days)
                if best_diff is None or diff < best_diff:
                    best_diff = diff
                    best_rec  = close
                    best_dt   = dt

            if best_rec is None:
                print(f'  ⚠️  {s["name"].ljust(16)} could not find anchor date')
                continue

            s['r3m'] = pct(s['last'], best_rec)
            days_off = abs((best_dt - target_3m).days)
            flag     = '' if days_off <= 3 else f'  ⚠️ {days_off}d from target'
            print(
                f'  ✅ {s["name"].ljust(16)} 3M: {fmt(s["r3m"]).rjust(8)}'
                f'  (anchor: {best_dt.strftime("%d %b %Y")}  close={best_rec:,.2f}){flag}'
            )
            time.sleep(0.6)   # be polite to NSE

        except Exception as e:
            print(f'  ⚠️  {s["name"].ljust(16)} failed: {str(e)[:70]}')
            time.sleep(1)


# ── Step 3: RS Rank, RRG, Signal ─────────────────────────────────────────────
def calculate_signals(sectors):
    valid = sorted(
        [s for s in sectors if s.get('r1m') is not None],
        key=lambda s: s['r1m'], reverse=True
    )
    total = len(valid)
    for i, s in enumerate(valid):
        rank      = i + 1
        s['rsRank'] = rank
        pp        = rank / total
        mom       = ('rising'  if (s.get('r1w') or 0) >  0.5 else
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

    print('━' * 70)
    print(f'🔄 NSE Sector Rotation v3 — {day_name} {now_ist.strftime("%Y-%m-%d %H:%M")} IST')
    print('   1D/1W/1M/1Y → NSE allIndices  |  3M → NSE indicesHistory (90 cal days)')
    print('   All data from NSE directly — matches Investing.com / Screener.in')
    print('━' * 70 + '\n')

    session = NSESession()

    # Step 1: NSE allIndices
    print('📡 Fetching NSE allIndices...')
    try:
        index_map = fetch_nse_all(session)
        print(f'   ✅ Got {len(index_map)} indices\n')
    except Exception as e:
        print(f'   ❌ Failed: {e}')
        write_output([]); return

    # Step 2: Extract each sector's 1D/1W/1M/1Y
    sectors = []
    for s in SECTORS:
        nse_sym = s['nse'].upper().strip()
        found   = index_map.get(nse_sym)

        # Fuzzy match if exact not found
        if not found:
            for sym, idx in index_map.items():
                if nse_sym in sym or sym in nse_sym:
                    found = idx; break

        if found:
            current = safe_float(found.get('last'))
            wk1     = safe_float(found.get('oneWeekAgoVal'))
            r1d     = safe_float(found.get('percentChange'))
            r1w     = pct(current, wk1)
            r1m     = (safe_float(found.get('perChange30d')) or
                       pct(current, safe_float(found.get('oneMonthAgoVal'))))
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

    # Step 3: 3M from NSE indicesHistory (same session, same cookies)
    fetch_3m_nse_history(sectors, session)

    # Step 4: RS Rank, RRG, Signal
    sectors = calculate_signals(sectors)

    # Summary
    valid   = [s for s in sectors if s.get('r1d') is not None]
    ranked  = sorted([s for s in sectors if s.get('rsRank')], key=lambda x: x['rsRank'])
    with_3m = [s for s in sectors if s.get('r3m') is not None]

    print('\n' + '━' * 70)
    print(f'📊 {len(valid)}/{len(sectors)} sectors | 3M data: {len(with_3m)}/{len(sectors)}')
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
        '_source':     'NSE allIndices (1D/1W/1M/1Y) + NSE indicesHistory (3M = 90 cal days)',
        '_note':       '3M anchored to 90 calendar days ago using NSE indicesHistory endpoint',
        '_version':    'v3 — all data from NSE directly, no third-party scrapers',
        'sectors':     sectors
    }
    out_dir  = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
    out_path = os.path.join(out_dir, 'sector-returns.json')
    os.makedirs(out_dir, exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2)
    print(f'\n✅ Saved {len(sectors)} sectors → data/sector-returns.json')
    print('━' * 70)


if __name__ == '__main__':
    fetch_sectors()
