#!/usr/bin/env python3
# scripts/scanner/candle_patterns.py
# ─────────────────────────────────────────────────────────────────────────────
# Detects 20+ candlestick patterns using pandas_ta
# Inspired by PKScreener's CandlePatterns.py
# ─────────────────────────────────────────────────────────────────────────────

import pandas as pd
import numpy as np

class CandlePatterns:
    """
    Detects bullish and bearish candlestick patterns on OHLCV data.
    Works on any timeframe — 5m, 15m, 1h, 1d, 1wk.
    """

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"

    def detect_all(self, df):
        """
        Run all pattern detections on a DataFrame.
        
        Args:
            df: OHLCV DataFrame (any timeframe)
        
        Returns:
            dict: {
                "bullish": [ list of detected bullish pattern names ],
                "bearish": [ list of detected bearish pattern names ],
                "has_pattern": bool
            }
        """
        if df is None or len(df) < 4:
            return { "bullish": [], "bearish": [], "has_pattern": False }

        # Use last 5 candles for pattern detection (like PKScreener)
        data = df.tail(10).copy().reset_index(drop=True)
        o = data["open"]
        h = data["high"]
        l = data["low"]
        c = data["close"]

        bullish = []
        bearish = []

        # ── Single Candle Patterns ────────────────────────────────────────────

        # Doji — open ≈ close (indecision)
        if self._is_doji(o, h, l, c):
            if c.iloc[-1] > c.iloc[-2]:
                bullish.append("Doji")
            else:
                bearish.append("Doji")

        # Hammer — small body at top, long lower wick (bullish reversal)
        if self._is_hammer(o, h, l, c):
            bullish.append("Hammer")

        # Shooting Star — small body at bottom, long upper wick (bearish reversal)
        if self._is_shooting_star(o, h, l, c):
            bearish.append("Shooting Star")

        # Hanging Man — like hammer but in uptrend (bearish)
        if self._is_hanging_man(o, h, l, c, df):
            bearish.append("Hanging Man")

        # Dragonfly Doji — open=high=close (bullish reversal)
        if self._is_dragonfly_doji(o, h, l, c):
            bullish.append("Dragonfly Doji")

        # Gravestone Doji — open=low=close (bearish reversal)
        if self._is_gravestone_doji(o, h, l, c):
            bearish.append("Gravestone Doji")

        # Bullish Marubozu — strong full bullish candle, no wicks
        if self._is_bullish_marubozu(o, h, l, c):
            bullish.append("Bullish Marubozu")

        # Bearish Marubozu — strong full bearish candle, no wicks
        if self._is_bearish_marubozu(o, h, l, c):
            bearish.append("Bearish Marubozu")

        # ── Two Candle Patterns ───────────────────────────────────────────────

        # Bullish Engulfing — bearish candle then larger bullish candle
        if self._is_bullish_engulfing(o, c):
            bullish.append("Bullish Engulfing")

        # Bearish Engulfing — bullish candle then larger bearish candle
        if self._is_bearish_engulfing(o, c):
            bearish.append("Bearish Engulfing")

        # Bullish Harami — large bearish then small bullish inside
        if self._is_bullish_harami(o, c):
            bullish.append("Bullish Harami")

        # Bearish Harami — large bullish then small bearish inside
        if self._is_bearish_harami(o, c):
            bearish.append("Bearish Harami")

        # Piercing Line — bearish then bullish closing above midpoint
        if self._is_piercing_line(o, c):
            bullish.append("Piercing Line")

        # Dark Cloud Cover — bullish then bearish closing below midpoint
        if self._is_dark_cloud_cover(o, c):
            bearish.append("Dark Cloud Cover")

        # Tweezer Bottom — two candles with same low (bullish reversal)
        if self._is_tweezer_bottom(h, l, c):
            bullish.append("Tweezer Bottom")

        # Tweezer Top — two candles with same high (bearish reversal)
        if self._is_tweezer_top(h, l, c):
            bearish.append("Tweezer Top")

        # Inside Bar — current candle within previous candle range
        if self._is_inside_bar(h, l):
            if c.iloc[-1] > o.iloc[-1]:
                bullish.append("Inside Bar")
            else:
                bearish.append("Inside Bar")

        # ── Three Candle Patterns ─────────────────────────────────────────────

        # Morning Star — bearish, small doji, bullish (reversal)
        if self._is_morning_star(o, c):
            bullish.append("Morning Star")

        # Evening Star — bullish, small doji, bearish (reversal)
        if self._is_evening_star(o, c):
            bearish.append("Evening Star")

        # 3 White Soldiers — three consecutive bullish candles
        if self._is_three_white_soldiers(o, c):
            bullish.append("3 White Soldiers")

        # 3 Black Crows — three consecutive bearish candles
        if self._is_three_black_crows(o, c):
            bearish.append("3 Black Crows")

        # 3 Inside Up
        if self._is_three_inside_up(o, c):
            bullish.append("3 Inside Up")

        # 3 Inside Down
        if self._is_three_inside_down(o, c):
            bearish.append("3 Inside Down")

        # ── Chart Patterns ────────────────────────────────────────────────────
        if self._is_cup_and_handle(df):
            bullish.append("Cup and Handle")

        return {
            "bullish": bullish,
            "bearish": bearish,
            "has_pattern": len(bullish) > 0 or len(bearish) > 0
        }

    # ── Single Candle ─────────────────────────────────────────────────────────

    def _body_size(self, o, c, idx=-1):
        return abs(c.iloc[idx] - o.iloc[idx])

    def _candle_range(self, h, l, idx=-1):
        return h.iloc[idx] - l.iloc[idx]

    def _is_doji(self, o, h, l, c):
        body  = self._body_size(o, c)
        range_ = self._candle_range(h, l)
        return range_ > 0 and body / range_ < 0.1

    def _is_hammer(self, o, h, l, c):
        body       = self._body_size(o, c)
        range_     = self._candle_range(h, l)
        lower_wick = min(o.iloc[-1], c.iloc[-1]) - l.iloc[-1]
        upper_wick = h.iloc[-1] - max(o.iloc[-1], c.iloc[-1])
        return (range_ > 0 and body / range_ < 0.35
                and lower_wick >= 2 * body and upper_wick < body)

    def _is_shooting_star(self, o, h, l, c):
        body       = self._body_size(o, c)
        range_     = self._candle_range(h, l)
        upper_wick = h.iloc[-1] - max(o.iloc[-1], c.iloc[-1])
        lower_wick = min(o.iloc[-1], c.iloc[-1]) - l.iloc[-1]
        return (range_ > 0 and body / range_ < 0.35
                and upper_wick >= 2 * body and lower_wick < body)

    def _is_hanging_man(self, o, h, l, c, df):
        if len(df) < 6:
            return False
        in_uptrend = df["close"].iloc[-6] < df["close"].iloc[-2]
        return in_uptrend and self._is_hammer(o, h, l, c) and c.iloc[-1] < o.iloc[-1]

    def _is_dragonfly_doji(self, o, h, l, c):
        body       = self._body_size(o, c)
        lower_wick = min(o.iloc[-1], c.iloc[-1]) - l.iloc[-1]
        upper_wick = h.iloc[-1] - max(o.iloc[-1], c.iloc[-1])
        avg_price  = c.mean()
        return (body < avg_price * 0.002 and lower_wick > body * 2 and upper_wick < body)

    def _is_gravestone_doji(self, o, h, l, c):
        body       = self._body_size(o, c)
        upper_wick = h.iloc[-1] - max(o.iloc[-1], c.iloc[-1])
        lower_wick = min(o.iloc[-1], c.iloc[-1]) - l.iloc[-1]
        avg_price  = c.mean()
        return (body < avg_price * 0.002 and upper_wick > body * 2 and lower_wick < body)

    def _is_bullish_marubozu(self, o, h, l, c):
        body       = c.iloc[-1] - o.iloc[-1]
        upper_wick = h.iloc[-1] - c.iloc[-1]
        lower_wick = o.iloc[-1] - l.iloc[-1]
        return body > 0 and upper_wick < body * 0.05 and lower_wick < body * 0.05

    def _is_bearish_marubozu(self, o, h, l, c):
        body       = o.iloc[-1] - c.iloc[-1]
        upper_wick = h.iloc[-1] - o.iloc[-1]
        lower_wick = c.iloc[-1] - l.iloc[-1]
        return body > 0 and upper_wick < body * 0.05 and lower_wick < body * 0.05

    # ── Two Candle ────────────────────────────────────────────────────────────

    def _is_bullish_engulfing(self, o, c):
        prev_bearish = c.iloc[-2] < o.iloc[-2]
        curr_bullish = c.iloc[-1] > o.iloc[-1]
        engulfs      = o.iloc[-1] <= c.iloc[-2] and c.iloc[-1] >= o.iloc[-2]
        return prev_bearish and curr_bullish and engulfs

    def _is_bearish_engulfing(self, o, c):
        prev_bullish = c.iloc[-2] > o.iloc[-2]
        curr_bearish = c.iloc[-1] < o.iloc[-1]
        engulfs      = o.iloc[-1] >= c.iloc[-2] and c.iloc[-1] <= o.iloc[-2]
        return prev_bullish and curr_bearish and engulfs

    def _is_bullish_harami(self, o, c):
        prev_bearish = c.iloc[-2] < o.iloc[-2]
        curr_bullish = c.iloc[-1] > o.iloc[-1]
        inside = (o.iloc[-1] > c.iloc[-2] and c.iloc[-1] < o.iloc[-2])
        return prev_bearish and curr_bullish and inside

    def _is_bearish_harami(self, o, c):
        prev_bullish = c.iloc[-2] > o.iloc[-2]
        curr_bearish = c.iloc[-1] < o.iloc[-1]
        inside = (o.iloc[-1] < c.iloc[-2] and c.iloc[-1] > o.iloc[-2])
        return prev_bullish and curr_bearish and inside

    def _is_piercing_line(self, o, c):
        prev_bearish = c.iloc[-2] < o.iloc[-2]
        curr_bullish = c.iloc[-1] > o.iloc[-1]
        midpoint     = (o.iloc[-2] + c.iloc[-2]) / 2
        return (prev_bearish and curr_bullish
                and o.iloc[-1] < c.iloc[-2]
                and c.iloc[-1] > midpoint)

    def _is_dark_cloud_cover(self, o, c):
        prev_bullish = c.iloc[-2] > o.iloc[-2]
        curr_bearish = c.iloc[-1] < o.iloc[-1]
        midpoint     = (o.iloc[-2] + c.iloc[-2]) / 2
        return (prev_bullish and curr_bearish
                and o.iloc[-1] > c.iloc[-2]
                and c.iloc[-1] < midpoint)

    def _is_tweezer_bottom(self, h, l, c):
        tol = l.iloc[-1] * 0.002
        return (abs(l.iloc[-1] - l.iloc[-2]) < tol and c.iloc[-1] > c.iloc[-2])

    def _is_tweezer_top(self, h, l, c):
        tol = h.iloc[-1] * 0.002
        return (abs(h.iloc[-1] - h.iloc[-2]) < tol and c.iloc[-1] < c.iloc[-2])

    def _is_inside_bar(self, h, l):
        return h.iloc[-1] < h.iloc[-2] and l.iloc[-1] > l.iloc[-2]

    # ── Three Candle ──────────────────────────────────────────────────────────

    def _is_morning_star(self, o, c):
        first_bearish = c.iloc[-3] < o.iloc[-3]
        small_body    = abs(c.iloc[-2] - o.iloc[-2]) < abs(c.iloc[-3] - o.iloc[-3]) * 0.3
        last_bullish  = c.iloc[-1] > o.iloc[-1]
        recovers      = c.iloc[-1] > (o.iloc[-3] + c.iloc[-3]) / 2
        return first_bearish and small_body and last_bullish and recovers

    def _is_evening_star(self, o, c):
        first_bullish = c.iloc[-3] > o.iloc[-3]
        small_body    = abs(c.iloc[-2] - o.iloc[-2]) < abs(c.iloc[-3] - o.iloc[-3]) * 0.3
        last_bearish  = c.iloc[-1] < o.iloc[-1]
        drops         = c.iloc[-1] < (o.iloc[-3] + c.iloc[-3]) / 2
        return first_bullish and small_body and last_bearish and drops

    def _is_three_white_soldiers(self, o, c):
        return (c.iloc[-1] > o.iloc[-1] and c.iloc[-2] > o.iloc[-2] and c.iloc[-3] > o.iloc[-3]
                and c.iloc[-1] > c.iloc[-2] > c.iloc[-3]
                and o.iloc[-1] > o.iloc[-2] > o.iloc[-3])

    def _is_three_black_crows(self, o, c):
        return (c.iloc[-1] < o.iloc[-1] and c.iloc[-2] < o.iloc[-2] and c.iloc[-3] < o.iloc[-3]
                and c.iloc[-1] < c.iloc[-2] < c.iloc[-3]
                and o.iloc[-1] < o.iloc[-2] < o.iloc[-3])

    def _is_three_inside_up(self, o, c):
        first_bearish = c.iloc[-3] < o.iloc[-3]
        harami        = (c.iloc[-2] > o.iloc[-2]
                         and o.iloc[-2] > c.iloc[-3]
                         and c.iloc[-2] < o.iloc[-3])
        confirm       = c.iloc[-1] > o.iloc[-3]
        return first_bearish and harami and confirm

    def _is_three_inside_down(self, o, c):
        first_bullish = c.iloc[-3] > o.iloc[-3]
        harami        = (c.iloc[-2] < o.iloc[-2]
                         and o.iloc[-2] < c.iloc[-3]
                         and c.iloc[-2] > o.iloc[-3])
        confirm       = c.iloc[-1] < o.iloc[-3]
        return first_bullish and harami and confirm

    # ── Chart Pattern ─────────────────────────────────────────────────────────

    def _is_cup_and_handle(self, df):
        """Simplified cup and handle detection over last 60 candles."""
        if len(df) < 60:
            return False
        try:
            prices = df["close"].tail(60).values
            mid    = len(prices) // 2
            left_peak  = max(prices[:10])
            cup_bottom = min(prices[mid-5:mid+5])
            right_peak = max(prices[-20:-5])
            handle_low = min(prices[-5:])
            curr_price = prices[-1]
            # Cup: left peak and right peak are similar, bottom is significantly lower
            peaks_similar = abs(left_peak - right_peak) / left_peak < 0.05
            cup_depth     = (left_peak - cup_bottom) / left_peak > 0.10
            handle_dip    = (right_peak - handle_low) / right_peak < 0.08
            breakout      = curr_price > right_peak * 0.98
            return peaks_similar and cup_depth and handle_dip and breakout
        except:
            return False
