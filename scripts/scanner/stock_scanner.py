#!/usr/bin/env python3
# scripts/scanner/stock_scanner.py
# ─────────────────────────────────────────────────────────────────────────────
# Main scanner engine — inspired by PKScreener
# Scans NSE stocks across ANY timeframe with candlestick + price action signals
# ─────────────────────────────────────────────────────────────────────────────

import json
import os
import sys
import time
import argparse
from datetime import datetime, timezone, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config       import TIMEFRAMES, UNIVERSES, FILTERS, SIGNAL_WEIGHTS, DEFAULT_TIMEFRAME
from data_fetcher import fetch_stock_data, fetch_multiple_stocks, get_market_status
from candle_patterns import CandlePatterns
from indicators      import Indicators
from price_action    import PriceAction

IST = timezone(timedelta(hours=5, minutes=30))

class StockScanner:

    def __init__(self):
        self.candle  = CandlePatterns()
        self.ind     = Indicators()
        self.pa      = PriceAction()

    # ── Score a single stock ──────────────────────────────────────────────────
    def analyze_stock(self, symbol, df, timeframe="1d"):
        """
        Full analysis of one stock across all dimensions.
        Returns a result dict (like PKScreener's screeningDictionary).
        """
        result = {
            "symbol":     symbol,
            "timeframe":  timeframe,
            "ltp":        None,
            "change_pct": None,
            "volume":     None,
            "vol_ratio":  None,
            "rsi":        None,
            "macd":       None,
            "ema_trend":  None,
            "ma_trend":   None,
            "supertrend": None,
            "support":    None,
            "resistance": None,
            "breakout":   None,
            "patterns":   { "bullish": [], "bearish": [] },
            "vcp":        False,
            "momentum":   False,
            "near_52high":False,
            "signal":     "NEUTRAL",      # STRONG BUY / BUY / NEUTRAL / SELL / STRONG SELL
            "confidence": 0,
            "reasons":    [],
        }

        if df is None or len(df) < 5:
            return None

        try:
            # ── Basic Price Info ──────────────────────────────────────────────
            result["ltp"]    = round(float(df["close"].iloc[-1]), 2)
            result["volume"] = int(df["volume"].iloc[-1])

            if len(df) >= 2:
                prev = float(df["close"].iloc[-2])
                curr = result["ltp"]
                result["change_pct"] = round((curr - prev) / prev * 100, 2) if prev > 0 else 0

            # ── Price filter ──────────────────────────────────────────────────
            if not (FILTERS["min_price"] <= result["ltp"] <= FILTERS["max_price"]):
                return None

            # ── Indicators ────────────────────────────────────────────────────
            result["rsi"]  = self.ind.rsi(df)
            macd_l, sig_l, hist = self.ind.macd(df)
            result["macd"] = { "macd": macd_l, "signal": sig_l, "histogram": hist }

            ema_dir, ema_str, ema_det = self.ind.ema_signal(df)
            result["ema_trend"]  = { "direction": ema_dir, "strength": ema_str, **ema_det }
            result["ma_trend"]   = self.ind.ma_trend(df)

            st_dir, st_val = self.ind.supertrend(df)
            result["supertrend"] = { "direction": st_dir, "value": st_val }

            vol_ratio, vol_dir, vol_str = self.ind.volume_analysis(df)
            result["vol_ratio"] = vol_ratio

            high52, low52, pct_from_high = self.ind.week52_position(df)
            result["52w_high"] = high52
            result["52w_low"]  = low52

            # ── Candlestick Patterns ──────────────────────────────────────────
            result["patterns"] = self.candle.detect_all(df)

            # ── Price Action ──────────────────────────────────────────────────
            sr = self.pa.find_support_resistance(df)
            result["support"]    = sr["support"]
            result["resistance"] = sr["resistance"]

            breakout = self.pa.detect_breakout(df)
            result["breakout"] = breakout

            is_vcp, vcp_note = self.pa.detect_vcp(df)
            result["vcp"] = is_vcp

            is_mom, mom_pct = self.pa.is_momentum_gainer(df)
            result["momentum"]    = is_mom
            result["momentum_pct"] = mom_pct

            near_high, high_pct = self.pa.near_52week_high(df)
            result["near_52high"] = near_high

            # ── Signal Scoring (inspired by PKScreener signals.py) ────────────
            score   = 0
            reasons = []

            # RSI signal
            rsi_dir, rsi_str = self.ind.rsi_signal(result["rsi"])
            if rsi_dir == "bullish":
                score += SIGNAL_WEIGHTS["rsi"] * rsi_str / 2
                reasons.append(f"RSI {result['rsi']} (oversold)" if result['rsi'] <= 40 else f"RSI {result['rsi']}")
            elif rsi_dir == "bearish":
                score -= SIGNAL_WEIGHTS["rsi"] * rsi_str / 2
                reasons.append(f"RSI {result['rsi']} (overbought)")

            # MACD signal
            macd_dir, macd_str = self.ind.macd_signal(macd_l, sig_l, hist)
            if macd_dir == "bullish":
                score += SIGNAL_WEIGHTS["macd"] * macd_str / 2
                reasons.append("MACD bullish crossover")
            elif macd_dir == "bearish":
                score -= SIGNAL_WEIGHTS["macd"] * macd_str / 2
                reasons.append("MACD bearish crossover")

            # EMA signal
            if ema_dir == "bullish":
                score += SIGNAL_WEIGHTS["ema"] * ema_str / 2
                reasons.append(f"Price above EMA ({result['ma_trend']})")
            elif ema_dir == "bearish":
                score -= SIGNAL_WEIGHTS["ema"] * ema_str / 2
                reasons.append(f"Price below EMA ({result['ma_trend']})")

            # Volume signal
            if vol_dir == "bullish":
                score += SIGNAL_WEIGHTS["volume"] * vol_str / 2
                reasons.append(f"Volume surge {vol_ratio}x avg")
            elif vol_dir == "bearish":
                score -= SIGNAL_WEIGHTS["volume"] * 0.5
                reasons.append("Low volume")

            # Candlestick patterns
            if result["patterns"]["bullish"]:
                score += SIGNAL_WEIGHTS["candle"]
                reasons.append("Bullish: " + ", ".join(result["patterns"]["bullish"]))
            if result["patterns"]["bearish"]:
                score -= SIGNAL_WEIGHTS["candle"]
                reasons.append("Bearish: " + ", ".join(result["patterns"]["bearish"]))

            # Supertrend
            if st_dir == "bullish":
                score += SIGNAL_WEIGHTS["price_action"]
                reasons.append("Supertrend bullish")
            elif st_dir == "bearish":
                score -= SIGNAL_WEIGHTS["price_action"]
                reasons.append("Supertrend bearish")

            # Breakout
            if breakout["type"] == "bullish_breakout":
                score += SIGNAL_WEIGHTS["momentum"] * breakout["strength"]
                reasons.append(f"Breaking out above {breakout.get('breakout_level')}")
            elif breakout["type"] == "bearish_breakdown":
                score -= SIGNAL_WEIGHTS["momentum"] * breakout["strength"]
                reasons.append(f"Breaking down below {breakout.get('breakdown_level')}")

            # VCP Bonus
            if is_vcp:
                score += 10
                reasons.append("VCP detected")

            # Momentum Gainer bonus
            if is_mom:
                score += 5
                reasons.append(f"Momentum +{mom_pct}%")

            # Near 52-week High
            if near_high:
                score += 5
                reasons.append(f"Near 52W High ({pct_from_high}% away)")

            # ── Final Signal Label ────────────────────────────────────────────
            max_score = sum(SIGNAL_WEIGHTS.values())
            confidence = min(100, max(0, round((score / max_score) * 100 + 50)))

            if   score >= 40: result["signal"] = "STRONG BUY"
            elif score >= 20: result["signal"] = "BUY"
            elif score <= -40:result["signal"] = "STRONG SELL"
            elif score <= -20:result["signal"] = "SELL"
            else:             result["signal"] = "NEUTRAL"

            result["score"]      = round(score, 2)
            result["confidence"] = confidence
            result["reasons"]    = reasons

        except Exception as e:
            result["error"] = str(e)

        return result

    # ── Scan all stocks ───────────────────────────────────────────────────────
    def run_scan(self, universe="nifty50", timeframes=None, filters=None):
        """
        Run full scan across selected universe and timeframes.
        
        Args:
            universe   : "nifty50", "nifty100", "banknifty", "watchlist"
            timeframes : list of timeframe keys e.g. ["5m","15m","1d"] 
                         or None = scan ALL timeframes
            filters    : optional override of FILTERS
        
        Returns: scan results dict saved to data/scanner-results.json
        """
        if timeframes is None:
            timeframes = list(TIMEFRAMES.keys())   # ALL timeframes
        
        symbols   = UNIVERSES[universe]["symbols"]
        mkt_status = get_market_status()
        
        print("━" * 65)
        print(f"🔍 NSE Stock Scanner — {universe.upper()}")
        print(f"📊 Timeframes : {', '.join(timeframes)}")
        print(f"📈 Universe   : {UNIVERSES[universe]['label']} ({len(symbols)} stocks)")
        print(f"🕐 Market     : {mkt_status['status']} ({mkt_status['time']})")
        print("━" * 65)

        all_results  = {}
        scan_summary = {}

        for tf in timeframes:
            if tf not in TIMEFRAMES:
                print(f"  ⚠️  Unknown timeframe: {tf}, skipping")
                continue

            tf_config = TIMEFRAMES[tf]
            print(f"\n📌 Scanning [{tf_config['label']}]...")

            # Fetch data for all stocks
            stock_data = fetch_multiple_stocks(
                symbols,
                period=tf_config["period"],
                interval=tf_config["interval"]
            )

            tf_results = []
            for symbol, df in stock_data.items():
                res = self.analyze_stock(symbol, df, timeframe=tf)
                if res:
                    tf_results.append(res)

            # Sort by score descending
            tf_results.sort(key=lambda x: x.get("score", 0), reverse=True)
            all_results[tf] = tf_results

            # Summary stats
            strong_buy  = [r for r in tf_results if r["signal"] == "STRONG BUY"]
            buy         = [r for r in tf_results if r["signal"] == "BUY"]
            sell        = [r for r in tf_results if r["signal"] == "SELL"]
            strong_sell = [r for r in tf_results if r["signal"] == "STRONG SELL"]
            with_pattern= [r for r in tf_results if r["patterns"]["bullish"] or r["patterns"]["bearish"]]

            scan_summary[tf] = {
                "total_scanned": len(tf_results),
                "strong_buy":    len(strong_buy),
                "buy":           len(buy),
                "neutral":       len(tf_results) - len(strong_buy) - len(buy) - len(sell) - len(strong_sell),
                "sell":          len(sell),
                "strong_sell":   len(strong_sell),
                "with_pattern":  len(with_pattern),
            }

            print(f"  ✅ {len(tf_results)} scanned  |  "
                  f"🟢 {len(strong_buy)} Strong Buy  |  "
                  f"🔵 {len(buy)} Buy  |  "
                  f"📊 {len(with_pattern)} patterns  |  "
                  f"🔴 {len(sell)+len(strong_sell)} Sell")

        # ── Save results ──────────────────────────────────────────────────────
        output = {
            "_updated_at": datetime.now(IST).isoformat(),
            "_market":     mkt_status,
            "_universe":   universe,
            "_timeframes": timeframes,
            "summary":     scan_summary,
            "results":     all_results,
        }

        out_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "data", "scanner-results.json"
        )
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(output, f, indent=2, default=str)

        print(f"\n✅ Results saved → data/scanner-results.json")
        print("━" * 65)
        return output


# ── CLI Entry Point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NSE Stock Scanner")
    parser.add_argument("--universe",  default="nifty50",
                        choices=["nifty50","nifty100","banknifty","watchlist"],
                        help="Stock universe to scan")
    parser.add_argument("--timeframes", nargs="+",
                        choices=["5m","15m","30m","1h","1d","1wk"],
                        default=None,
                        help="Timeframes to scan (space separated). Default = ALL")
    args = parser.parse_args()

    scanner = StockScanner()
    scanner.run_scan(universe=args.universe, timeframes=args.timeframes)
