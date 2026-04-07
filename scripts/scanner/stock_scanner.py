#!/usr/bin/env python3
# scripts/scanner/stock_scanner.py
import json, os, sys, argparse
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config          import TIMEFRAMES, MASTER_STOCKS, FILTERS, SIGNAL_WEIGHTS
from data_fetcher    import fetch_multiple_stocks, get_market_status
from candle_patterns import CandlePatterns
from indicators      import Indicators
from price_action    import PriceAction

IST = timezone(timedelta(hours=5, minutes=30))

class StockScanner:
    def __init__(self):
        self.candle = CandlePatterns()
        self.ind    = Indicators()
        self.pa     = PriceAction()

    def analyze_stock(self, symbol, df, timeframe="1d"):
        result = {
            "symbol":      symbol,
            "indices":     MASTER_STOCKS.get(symbol, []),   # ← which indices it belongs to
            "timeframe":   timeframe,
            "ltp":         None, "change_pct": None,
            "volume":      None, "vol_ratio":  None,
            "rsi":         None, "macd":       None,
            "ema_trend":   None, "ma_trend":   None,
            "supertrend":  None, "support":    None,
            "resistance":  None, "breakout":   None,
            "patterns":    {"bullish":[],"bearish":[]},
            "vcp":         False, "momentum":  False,
            "near_52high": False, "signal":    "NEUTRAL",
            "confidence":  0,    "reasons":   [],
        }
        if df is None or len(df) < 5:
            return None
        try:
            result["ltp"]    = round(float(df["close"].iloc[-1]), 2)
            result["volume"] = int(df["volume"].iloc[-1])
            if len(df) >= 2:
                prev = float(df["close"].iloc[-2])
                curr = result["ltp"]
                result["change_pct"] = round((curr-prev)/prev*100, 2) if prev > 0 else 0
            if not (FILTERS["min_price"] <= result["ltp"] <= FILTERS["max_price"]):
                return None

            result["rsi"]  = self.ind.rsi(df)
            ml, sl, hist   = self.ind.macd(df)
            result["macd"] = {"macd":ml,"signal":sl,"histogram":hist}
            ed, es, edet   = self.ind.ema_signal(df)
            result["ema_trend"]  = {"direction":ed,"strength":es,**edet}
            result["ma_trend"]   = self.ind.ma_trend(df)
            std, stv       = self.ind.supertrend(df)
            result["supertrend"] = {"direction":std,"value":stv}
            vr, vd, vs     = self.ind.volume_analysis(df)
            result["vol_ratio"]  = vr
            result["patterns"]   = self.candle.detect_all(df)
            sr = self.pa.find_support_resistance(df)
            result["support"]    = sr["support"]
            result["resistance"] = sr["resistance"]
            result["breakout"]   = self.pa.detect_breakout(df)
            is_vcp, _      = self.pa.detect_vcp(df)
            result["vcp"]  = is_vcp
            is_mom, mp     = self.pa.is_momentum_gainer(df)
            result["momentum"]     = is_mom
            result["momentum_pct"] = mp
            nh, hp         = self.pa.near_52week_high(df)
            result["near_52high"]  = nh

            # ── Signal scoring ────────────────────────────────
            score = 0; reasons = []
            rd, rs = self.ind.rsi_signal(result["rsi"])
            if   rd == "bullish": score += SIGNAL_WEIGHTS["rsi"]*rs/2;  reasons.append(f"RSI {result['rsi']}")
            elif rd == "bearish": score -= SIGNAL_WEIGHTS["rsi"]*rs/2;  reasons.append(f"RSI {result['rsi']} overbought")
            md, ms = self.ind.macd_signal(ml, sl, hist)
            if   md == "bullish": score += SIGNAL_WEIGHTS["macd"]*ms/2; reasons.append("MACD bullish")
            elif md == "bearish": score -= SIGNAL_WEIGHTS["macd"]*ms/2; reasons.append("MACD bearish")
            if   ed == "bullish": score += SIGNAL_WEIGHTS["ema"]*es/2;  reasons.append(f"EMA {result['ma_trend']}")
            elif ed == "bearish": score -= SIGNAL_WEIGHTS["ema"]*es/2
            if   vd == "bullish": score += SIGNAL_WEIGHTS["volume"]*vs/2; reasons.append(f"Vol {vr}x avg")
            elif vd == "bearish": score -= SIGNAL_WEIGHTS["volume"]*0.5
            if result["patterns"]["bullish"]: score += SIGNAL_WEIGHTS["candle"];  reasons.append("Bullish: "+", ".join(result["patterns"]["bullish"]))
            if result["patterns"]["bearish"]: score -= SIGNAL_WEIGHTS["candle"];  reasons.append("Bearish: "+", ".join(result["patterns"]["bearish"]))
            if   std == "bullish": score += SIGNAL_WEIGHTS["price_action"]; reasons.append("Supertrend bullish")
            elif std == "bearish": score -= SIGNAL_WEIGHTS["price_action"]; reasons.append("Supertrend bearish")
            bo = result["breakout"]
            if   bo["type"] == "bullish_breakout":  score += SIGNAL_WEIGHTS["momentum"]*bo["strength"]; reasons.append(f"Breakout ↑ {bo.get('breakout_level')}")
            elif bo["type"] == "bearish_breakdown": score -= SIGNAL_WEIGHTS["momentum"]*bo["strength"]; reasons.append(f"Breakdown ↓ {bo.get('breakdown_level')}")
            if is_vcp: score += 10; reasons.append("VCP detected")
            if is_mom: score += 5;  reasons.append(f"Momentum +{mp}%")
            if nh:     score += 5;  reasons.append("Near 52W High")

            mx   = sum(SIGNAL_WEIGHTS.values())
            conf = min(100, max(0, round((score/mx)*100+50)))
            if   score >= 40: result["signal"] = "STRONG BUY"
            elif score >= 20: result["signal"] = "BUY"
            elif score <=-40: result["signal"] = "STRONG SELL"
            elif score <=-20: result["signal"] = "SELL"
            else:             result["signal"] = "NEUTRAL"
            result["score"]      = round(score, 2)
            result["confidence"] = conf
            result["reasons"]    = reasons
        except Exception as e:
            result["error"] = str(e)
        return result

    def run_scan(self, timeframes=None):
        """
        Scan ALL stocks in MASTER_STOCKS across ALL (or selected) timeframes.
        Each result includes which indices the stock belongs to.
        """
        if timeframes is None:
            timeframes = list(TIMEFRAMES.keys())  # ALL timeframes by default

        symbols   = list(MASTER_STOCKS.keys())
        mkt       = get_market_status()

        print("━" * 65)
        print(f"🔍 NSE Master Scanner — ALL {len(symbols)} STOCKS")
        print(f"📊 Timeframes : {', '.join(timeframes)}")
        print(f"🕐 Market     : {mkt['status']} ({mkt['time']})")
        print("━" * 65)

        all_results = {}
        summary     = {}

        for tf in timeframes:
            if tf not in TIMEFRAMES:
                continue
            cfg = TIMEFRAMES[tf]
            print(f"\n📌 Scanning [{cfg['label']}] — {len(symbols)} stocks...")

            stock_data = fetch_multiple_stocks(
                symbols,
                period=cfg["period"],
                interval=cfg["interval"]
            )

            tf_results = []
            for sym, df in stock_data.items():
                r = self.analyze_stock(sym, df, timeframe=tf)
                if r:
                    tf_results.append(r)

            tf_results.sort(key=lambda x: x.get("score", 0), reverse=True)
            all_results[tf] = tf_results

            sb  = [r for r in tf_results if r["signal"] == "STRONG BUY"]
            b   = [r for r in tf_results if r["signal"] == "BUY"]
            s   = [r for r in tf_results if r["signal"] == "SELL"]
            ss  = [r for r in tf_results if r["signal"] == "STRONG SELL"]
            wp  = [r for r in tf_results if r["patterns"]["bullish"] or r["patterns"]["bearish"]]

            summary[tf] = {
                "total_scanned": len(tf_results),
                "strong_buy":    len(sb),
                "buy":           len(b),
                "neutral":       len(tf_results)-len(sb)-len(b)-len(s)-len(ss),
                "sell":          len(s),
                "strong_sell":   len(ss),
                "with_pattern":  len(wp),
            }
            print(f"  ✅ {len(tf_results)} scanned | 🟢 {len(sb)} Strong Buy | 🔵 {len(b)} Buy | 📊 {len(wp)} patterns | 🔴 {len(s)+len(ss)} Sell")

        # Save results
        output = {
            "_updated_at": datetime.now(IST).isoformat(),
            "_market":     mkt,
            "_total_stocks": len(symbols),
            "_timeframes": timeframes,
            "summary":     summary,
            "results":     all_results,
        }
        op = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "data", "scanner-results.json"
        )
        os.makedirs(os.path.dirname(op), exist_ok=True)
        with open(op, "w") as f:
            json.dump(output, f, indent=2, default=str)

        print(f"\n✅ Saved → data/scanner-results.json")
        print("━" * 65)
        return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NSE Master Stock Scanner")
    parser.add_argument("--timeframes", nargs="+",
                        choices=["5m","15m","30m","1h","1d","1wk"],
                        default=None,
                        help="Timeframes to scan. Default = ALL")
    args = parser.parse_args()
    StockScanner().run_scan(timeframes=args.timeframes)
