#!/usr/bin/env python3
# scripts/scanner/price_action.py
# ─────────────────────────────────────────────────────────────────────────────
# Price action analysis: Support/Resistance, Breakout, VCP, Consolidation
# ─────────────────────────────────────────────────────────────────────────────

import pandas as pd
import numpy as np

class PriceAction:

    # ── Support & Resistance ──────────────────────────────────────────────────
    def find_support_resistance(self, df, lookback=50, tolerance=0.02):
        """
        Find key support and resistance levels.
        Returns: { "support": float, "resistance": float }
        """
        if len(df) < 20:
            return {"support": None, "resistance": None}

        data   = df.tail(lookback)
        price  = float(df["close"].iloc[-1])
        highs  = data["high"].values
        lows   = data["low"].values

        # Find price clusters
        all_levels = np.concatenate([highs, lows])
        levels     = []
        for p in all_levels:
            near = [l for l in levels if abs(l - p) / p < tolerance]
            if near:
                idx = levels.index(near[0])
                levels[idx] = (levels[idx] + p) / 2
            else:
                levels.append(p)

        supports    = sorted([l for l in levels if l < price], reverse=True)
        resistances = sorted([l for l in levels if l > price])

        return {
            "support":    round(supports[0], 2)    if supports    else round(float(data["low"].min()), 2),
            "resistance": round(resistances[0], 2) if resistances else round(float(data["high"].max()), 2),
        }

    # ── Breakout Detection ────────────────────────────────────────────────────
    def detect_breakout(self, df, lookback=20):
        """
        Detect if stock is breaking out of a consolidation range.
        Returns: { "type": "bullish_breakout"/"bearish_breakdown"/None, "strength": 0-2 }
        """
        if len(df) < lookback + 2:
            return {"type": None, "strength": 0}

        hist       = df.tail(lookback + 1).iloc[:-1]  # Historical range
        curr_close = float(df["close"].iloc[-1])
        curr_vol   = float(df["volume"].iloc[-1])
        avg_vol    = float(df["volume"].tail(lookback).mean())

        range_high = float(hist["high"].max())
        range_low  = float(hist["low"].min())
        vol_ratio  = curr_vol / avg_vol if avg_vol > 0 else 1

        if curr_close > range_high * 1.005:
            strength = 2 if vol_ratio > 1.5 else 1
            return {"type": "bullish_breakout", "strength": strength,
                    "breakout_level": round(range_high, 2), "volume_ratio": round(vol_ratio, 2)}

        elif curr_close < range_low * 0.995:
            strength = 2 if vol_ratio > 1.5 else 1
            return {"type": "bearish_breakdown", "strength": strength,
                    "breakdown_level": round(range_low, 2), "volume_ratio": round(vol_ratio, 2)}

        return {"type": None, "strength": 0}

    # ── Consolidation ─────────────────────────────────────────────────────────
    def is_consolidating(self, df, lookback=15, pct_range=10.0):
        """
        Check if stock is in consolidation (tight trading range).
        Like PKScreener's consolidation scan.
        """
        if len(df) < lookback:
            return False, 0

        data   = df.tail(lookback)
        high   = float(data["high"].max())
        low    = float(data["low"].min())

        if low == 0:
            return False, 0

        range_pct = ((high - low) / low) * 100
        return range_pct <= pct_range, round(range_pct, 2)

    # ── VCP — Volatility Contraction Pattern (Mark Minervini) ─────────────────
    def detect_vcp(self, df):
        """
        Detect VCP — stock tightening into a breakout point.
        Pattern: Series of pullbacks getting smaller (Minervini style).
        """
        if len(df) < 60:
            return False, ""

        try:
            prices = df["close"].values
            # Split into 3 sections and check if volatility is contracting
            n = len(prices) // 3
            vol1 = np.std(prices[:n])         / np.mean(prices[:n])
            vol2 = np.std(prices[n:2*n])      / np.mean(prices[n:2*n])
            vol3 = np.std(prices[2*n:])       / np.mean(prices[2*n:])

            contracting = vol1 > vol2 > vol3

            # Price should be in uptrend overall
            uptrend = prices[-1] > prices[0]

            # Recent price above 50-period moving average
            ma50 = np.mean(prices[-50:]) if len(prices) >= 50 else np.mean(prices)
            above_ma = prices[-1] > ma50

            if contracting and uptrend and above_ma:
                return True, f"VCP (vol: {vol1:.3f}→{vol2:.3f}→{vol3:.3f})"
            return False, ""
        except:
            return False, ""

    # ── Momentum Gainer ───────────────────────────────────────────────────────
    def is_momentum_gainer(self, df, pct_threshold=2.0):
        """
        Check if today's candle shows strong momentum (like PKScreener's 'Momentum Gainer').
        """
        if len(df) < 2:
            return False, 0
        prev_close = float(df["close"].iloc[-2])
        curr_close = float(df["close"].iloc[-1])
        if prev_close == 0:
            return False, 0
        pct_change = ((curr_close - prev_close) / prev_close) * 100
        return pct_change >= pct_threshold, round(pct_change, 2)

    # ── Near 52-Week High ─────────────────────────────────────────────────────
    def near_52week_high(self, df, threshold_pct=3.0):
        """Check if price is near 52-week high (potential breakout)."""
        if len(df) < 10:
            return False, 0
        high52 = float(df["high"].max())
        curr   = float(df["close"].iloc[-1])
        pct    = ((high52 - curr) / high52) * 100
        return pct <= threshold_pct, round(pct, 2)
