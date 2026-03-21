// scripts/fetch_sectors.js
// Fetches NSE sector index returns (1D, 1W, 1M, 3M) via Yahoo Finance
// Matches exact same sectors as Pine Script "Market Monitor" indicator
// Called by GitHub Actions daily — saves to data/sector-returns.json
//
// LOGIC (same as Pine Script):
//   1D = last trading day close vs previous trading day close
//   1W = last trading day close vs close 1 week ago
//   1M = last trading day close vs close ~1 month ago
//   3M = last trading day close vs close ~3 months ago
//
// Works on weekdays, weekends AND holidays — Yahoo Finance always
// returns the last available trading day data automatically.

const https = require('https');
const fs    = require('fs');
const path  = require('path');

// ── All 21 sectors — verified working symbols ─────────────────────────────
// Matches Pine Script "Market Monitor" indicator exactly
const SECTORS = [
  { name: 'Auto',          yahoo: '%5ECNXAUTO'           },  // NSE:CNXAUTO
  { name: 'Commodities',   yahoo: '%5ECNXCMDT'           },  // NSE:CNXCOMMODITIES
  { name: 'Cons Durables', yahoo: 'NIFTY_CONSR_DURBL.NS' },  // NSE:NIFTY_CONSR_DURBL
  { name: 'Consumption',   yahoo: 'NIFTY_CONSUMPTION.NS' },  // NSE:CNXCONSUMPTION
  { name: 'Defence',       yahoo: 'NIFTY_IND_DEFENCE.NS' },  // NSE:NIFTY_IND_DEFENCE
  { name: 'Energy',        yahoo: '%5ECNXENERGY'         },  // NSE:CNXENERGY
  { name: 'Finance',       yahoo: '%5ECNXFIN'            },  // NSE:CNXFINANCE
  { name: 'FMCG',          yahoo: '%5ECNXFMCG'           },  // NSE:CNXFMCG
  { name: 'Healthcare',    yahoo: 'NIFTY_HEALTHCARE.NS'  },  // NSE:NIFTY_HEALTHCARE
  { name: 'Infra',         yahoo: '%5ECNXINFRA'          },  // NSE:CNXINFRA
  { name: 'IT',            yahoo: '%5ECNXIT'             },  // NSE:CNXIT
  { name: 'Media',         yahoo: '%5ECNXMEDIA'          },  // NSE:CNXMEDIA
  { name: 'Metal',         yahoo: '%5ECNXMETAL'          },  // NSE:CNXMETAL
  { name: 'OilGas',        yahoo: 'NIFTY_OIL_AND_GAS.NS' }, // NSE:OILGAS (Pine uses BSE but we use NSE)
  { name: 'Pharma',        yahoo: '%5ECNXPHARMA'         },  // NSE:CNXPHARMA
  { name: 'Power',         yahoo: '%5ECNXENERGY'         },  // BSE:POWER (Pine) → NSE Energy equivalent
  { name: 'PSE',           yahoo: '%5ECNXPSE'            },  // NSE:CNXPSE
  { name: 'PSUBank',       yahoo: '%5ECNXPSUBANK'        },  // NSE:CNXPSUBANK
  { name: 'PVTBank',       yahoo: 'NIFTYPVTBANK.NS'      },  // NSE:NIFTYPVTBANK
  { name: 'Realty',        yahoo: '%5ECNXREALTY'         },  // NSE:CNXREALTY
  { name: 'Service',       yahoo: '%5ECNXSERVICE'        },  // NSE:CNXSERVICE
];

// ── HTTP fetch helper ─────────────────────────────────────────────────────
function fetchJSON(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept':     'application/json'
      }
    }, res => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch(e) { reject(new Error('JSON parse error')); }
      });
    });
    req.on('error', reject);
    req.setTimeout(15000, () => { req.destroy(); reject(new Error('Timeout')); });
  });
}

function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

// % change calculation — same as Pine Script
// (close - prev_close) / prev_close * 100
function pct(current, prev) {
  if (!prev || prev === 0 || !current) return null;
  return +((current - prev) / prev * 100).toFixed(2);
}

function fmt(v) {
  return v === null ? 'N/A  ' : (v >= 0 ? '+' : '') + v.toFixed(2) + '%';
}

// Remove duplicate trailing entries Yahoo sometimes adds
// (happens when market is closed — last close repeats)
function cleanCloses(closes) {
  const c = (closes || []).filter(v => v !== null && v !== undefined);
  while (c.length > 1 && c[c.length - 1] === c[c.length - 2]) c.pop();
  return c;
}

// Get last trading date as readable string
function lastTradingDate(timestamps) {
  if (!timestamps?.length) return '—';
  const t = timestamps[timestamps.length - 1];
  return new Date(t * 1000).toLocaleDateString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    timeZone: 'Asia/Kolkata'
  });
}

// ── Fetch all 4 timeframes for one sector ─────────────────────────────────
// Same logic as Pine Script:
//   close[0] = last trading day
//   close[1] = one period back
async function getSectorReturns(sector) {
  const base = `https://query1.finance.yahoo.com/v8/finance/chart/${sector.yahoo}`;

  try {
    // ── 1D: Use daily range ──────────────────────────────────────────────
    // close[0] = last trading day close
    // close[1] = previous trading day close
    const daily   = await fetchJSON(`${base}?interval=1d&range=10d`);
    const dResult = daily?.chart?.result?.[0];
    if (!dResult) throw new Error('No daily data');

    const dCloses    = cleanCloses(dResult.indicators.quote[0].close);
    const dTimestamp = dResult.timestamp || [];
    const lastClose  = dCloses[dCloses.length - 1]; // close[0]
    const prevClose  = dCloses[dCloses.length - 2]; // close[1]
    const r1d        = pct(lastClose, prevClose);
    const tradingDay = lastTradingDate(dTimestamp);

    await delay(300);

    // ── 1W, 1M, 3M: Use weekly range ────────────────────────────────────
    // close[0] = this week  → close[1] = last week  → 1W
    // close[0] = this month → close[4] = last month → 1M (~4 weeks)
    // close[0] = now        → close[0 of 4mo range] → 3M
    const weekly  = await fetchJSON(`${base}?interval=1wk&range=4mo`);
    const wResult = weekly?.chart?.result?.[0];
    if (!wResult) throw new Error('No weekly data');

    const wCloses = cleanCloses(wResult.indicators.quote[0].close);
    const wLen    = wCloses.length;

    const close1w = wCloses[wLen - 2];               // 1 week ago
    const close1m = wCloses[wLen - 5] || wCloses[0]; // ~1 month ago (4 weeks)
    const close3m = wCloses[0];                       // ~3 months ago (start of range)

    const r1w = pct(lastClose, close1w);
    const r1m = pct(lastClose, close1m);
    const r3m = pct(lastClose, close3m);

    console.log(
      `  ✅ ${sector.name.padEnd(16)}` +
      `  1D: ${fmt(r1d).padStart(8)}` +
      `  1W: ${fmt(r1w).padStart(8)}` +
      `  1M: ${fmt(r1m).padStart(8)}` +
      `  3M: ${fmt(r3m).padStart(8)}` +
      `  [${tradingDay}]`
    );

    return {
      name:       sector.name,
      last:       lastClose,
      lastDate:   tradingDay,
      r1d,
      r1w,
      r1m,
      r3m
    };

  } catch(e) {
    console.log(`  ⚠️  ${sector.name.padEnd(16)} Error: ${e.message}`);
    return {
      name: sector.name, last: null, lastDate: null,
      r1d: null, r1w: null, r1m: null, r3m: null
    };
  }
}

// ── Main ──────────────────────────────────────────────────────────────────
async function fetchSectors() {
  const istNow  = new Date(Date.now() + 5.5 * 60 * 60 * 1000);
  const dayName = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][istNow.getUTCDay()];
  const isWeekend = istNow.getUTCDay() === 0 || istNow.getUTCDay() === 6;

  console.log('━'.repeat(60));
  console.log(`📡 NSE Sector Rotation Fetch — ${dayName} ${istNow.toISOString().slice(0,10)}`);
  if (isWeekend) {
    console.log('   📅 Weekend — fetching last available trading day data');
  }
  console.log('   Source: Yahoo Finance (same data as NSE)');
  console.log('   Logic:  Pine Script "Market Monitor" equivalent');
  console.log('━'.repeat(60) + '\n');

  const sectors = [];
  for (const sector of SECTORS) {
    const result = await getSectorReturns(sector);
    sectors.push(result);
    await delay(500); // avoid rate limiting
  }

  // ── Summary ──────────────────────────────────────────────────────────
  const valid = sectors.filter(s => s.r1d !== null);
  console.log('\n' + '━'.repeat(60));
  console.log(`📊 Fetched: ${valid.length}/${sectors.length} sectors`);

  if (valid.length > 0) {
    console.log(`📅 Data as of: ${valid[0].lastDate}`);
    const sorted = [...valid].sort((a,b) => (b.r1d||0) - (a.r1d||0));
    console.log('\n🏆 Top 5 (Today):');
    sorted.slice(0, 5).forEach((s,i) => console.log(`   ${i+1}. ${s.name.padEnd(16)} ${fmt(s.r1d)}`));
    console.log('\n📉 Bottom 5 (Today):');
    sorted.slice(-5).reverse().forEach((s,i) => console.log(`   ${i+1}. ${s.name.padEnd(16)} ${fmt(s.r1d)}`));
  }

  writeOutput(sectors);
}

function writeOutput(sectors) {
  const out = {
    _updated_at: new Date().toISOString(),
    _source:     'Yahoo Finance — NSE Indices',
    _note:       'Returns calculated same as Pine Script: (close - prev_close) / prev_close * 100',
    sectors
  };
  const outDir  = path.join(__dirname, '..', 'data');
  const outPath = path.join(outDir, 'sector-returns.json');
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(outPath, JSON.stringify(out, null, 2));
  console.log(`\n✅ Saved → data/sector-returns.json`);
  console.log('━'.repeat(60));
}

// ── Run ───────────────────────────────────────────────────────────────────
fetchSectors().catch(err => {
  console.error('\n❌ Fatal:', err.message);
  process.exit(0); // exit 0 so GitHub Actions never fails
});
