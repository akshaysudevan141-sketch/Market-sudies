#!/usr/bin/env python3
# scripts/scanner/indicators.py
# ─────────────────────────────────────────────────────────────────────────────
# Technical indicators: RSI, MACD, EMA, Volume Surge, ATR, Supertrend
# Inspired by PKScreener's signals.py
# ─────────────────────────────────────────────────────────────────────────────

import pandas as pd
import numpy as np

class Indicators:

    # ── RSI ───────────────────────────────────────────────────────────────────
    def rsi(self, df, period=14):
        """Compute RSI. Returns float (0-100) or None."""
        if len(df) < period + 1:
            return None
        delta  = df["close"].diff()
        gain   = delta.clip(lower=0)
        loss   = -delta.clip(upper=0)
        avg_g  = gain.ewm(com=period-1, min_periods=period).mean()
        avg_l  = loss.ewm(com=period-1, min_periods=period).mean()
        rs     = avg_g / avg_l.replace(0, np.nan)
        rsi    = 100 - (100 / (1 + rs))
        return round(float(rsi.iloc[-1]), 2) if not rsi.empty else None

    def rsi_signal(self, rsi_val):
        """Interpret RSI value."""
        if rsi_val is None:
            return "neutral", 0
        if rsi_val <= 30:
            return "bullish", 2    # Oversold → buy opportunity
        elif rsi_val <= 45:
            return "bullish", 1    # Mildly oversold
        elif rsi_val >= 70:
            return "bearish", 2    # Overbought
        elif rsi_val >= 55:
            return "bearish", 1    # Mildly overbought
        return "neutral", 0

    # ── MACD ──────────────────────────────────────────────────────────────────
    def macd(self, df, fast=12, slow=26, signal=9):
        """Compute MACD line, signal line, histogram."""
        if len(df) < slow + signal:
            return None, None, None
        c        = df["close"]
        ema_fast = c.ewm(span=fast, adjust=False).mean()
        ema_slow = c.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        sig_line  = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - sig_line
        return (round(float(macd_line.iloc[-1]), 4),
                round(float(sig_line.iloc[-1]), 4),
                round(float(histogram.iloc[-1]), 4))

    def macd_signal(self, macd_line, sig_line, hist):
        """Interpret MACD crossover."""
        if macd_line is None:
            return "neutral", 0
        if macd_line > sig_line and hist > 0:
            return "bullish", 2 if hist > 0 and macd_line > 0 else 1
        elif macd_line < sig_line and hist < 0:
            return "bearish", 2 if macd_line < 0 else 1
        return "neutral", 0

    # ── EMA ───────────────────────────────────────────────────────────────────
    def ema(self, df, period):
        """Compute EMA for given period. Returns float or None."""
        if len(df) < period:
            return None
        return round(float(df["close"].ewm(span=period, adjust=False).mean().iloc[-1]), 2)

    def ema_signal(self, df):
        """
        EMA crossover signal (20/50/200 EMA).
        Returns signal direction and strength.
        """
        ema20  = self.ema(df, 20)
        ema50  = self.ema(df, 50)
        ema200 = self.ema(df, 200)
        price  = float(df["close"].iloc[-1])

        score = 0
        details = {}

        if ema20 and ema50:
            details["ema20"]  = ema20
            details["ema50"]  = ema50
            if ema20 > ema50:
                score += 1   # Golden cross territory
            else:
                score -= 1   # Death cross territory

        if ema200:
            details["ema200"] = ema200
            if price > ema200:
                score += 1   # Price above 200 EMA → bullish
            else:
                score -= 1

        if ema20 and price > ema20:
            score += 1
        elif ema20:
            score -= 1

        direction = "bullish" if score > 0 else ("bearish" if score < 0 else "neutral")
        strength  = min(abs(score), 2)
        return direction, strength, details

    # ── Volume ────────────────────────────────────────────────────────────────
    def volume_analysis(self, df, ma_period=20):
        """
        Compare current volume to N-period average.
        Returns ratio and signal.
        """
        if len(df) < ma_period:
            return None, "neutral", 0

        vol_now = float(df["volume"].iloc[-1])
        vol_avg = float(df["volume"].tail(ma_period).mean())

        if vol_avg == 0:
            return None, "neutral", 0

        ratio = round(vol_now / vol_avg, 2)

        if ratio >= 3.0:
            return ratio, "bullish", 2   # Very high volume surge
        elif ratio >= 1.5:
            return ratio, "bullish", 1   # Volume above average
        elif ratio <= 0.5:
            return ratio, "bearish", 1   # Very low volume
        return ratio, "neutral", 0

    # ── ATR ───────────────────────────────────────────────────────────────────
    def atr(self, df, period=14):
        """Average True Range — measures volatility."""
        if len(df) < period + 1:
            return None
        h = df["high"]
        l = df["low"]
        c = df["close"]
        tr = pd.concat([
            h - l,
            (h - c.shift()).abs(),
            (l - c.shift()).abs()
        ], axis=1).max(axis=1)
        return round(float(tr.ewm(span=period, adjust=False).mean().iloc[-1]), 2)

    # ── Supertrend ────────────────────────────────────────────────────────────
    def supertrend(self, df, period=7, multiplier=3.0):
        """
        Supertrend indicator.
        Returns: "bullish" or "bearish" signal.
        """
        if len(df) < period + 5:
            return None, None

        atr_val = self.atr(df, period)
        if atr_val is None:
            return None, None

        hl2    = (df["high"] + df["low"]) / 2
        upper  = hl2 + (multiplier * atr_val)
        lower  = hl2 - (multiplier * atr_val)
        close  = df["close"]

        # Simplified supertrend
        trend = "bullish" if close.iloc[-1] > lower.iloc[-1] else "bearish"
        return trend, round(float(lower.iloc[-1] if trend == "bullish" else upper.iloc[-1]), 2)

    # ── Moving Average Trend ──────────────────────────────────────────────────
    def ma_trend(self, df):
        """
        Determine price trend using 50 & 200 SMA.
        Returns: "Strong Up", "Weak Up", "Flat", "Weak Down", "Strong Down"
        """
        if len(df) < 20:
            return "Unknown"
        
        sma20  = df["close"].tail(20).mean()
        price  = float(df["close"].iloc[-1])
        slope  = (df["close"].iloc[-1] - df["close"].iloc[-20]) / 20

        if len(df) >= 50:
            sma50 = df["close"].tail(50).mean()
        else:
            sma50 = sma20

        pct_above = (price - sma50) / sma50 * 100

        if slope > 0 and pct_above > 5:
            return "Strong Up"
        elif slope > 0 and pct_above > 0:
            return "Weak Up"
        elif slope < 0 and pct_above < -5:
            return "Strong Down"
        elif slope < 0:
            return "Weak Down"
        return "Flat"

    # ── 52-Week High/Low ──────────────────────────────────────────────────────
    def week52_position(self, df):
        """How close price is to 52-week high/low."""
        if len(df) < 2:
            return None, None, None
        high52 = float(df["high"].max())
        low52  = float(df["low"].min())
        curr   = float(df["close"].iloc[-1])
        pct_from_high = round((curr - high52) / high52 * 100, 2)
        pct_from_low  = round((curr - low52)  / low52  * 100, 2)
        return high52, low52, pct_from_high
