"""Technical analysis signal generation using TA-Lib indicators."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd
import talib


class Signal(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class SignalResult:
    symbol: str
    signal: Signal
    strength: float  # 0.0 to 1.0, higher = stronger conviction
    reasons: list[str]


def compute_indicators(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Compute all technical indicators on a price DataFrame."""
    close = df["close"].values
    high = df["high"].values
    low = df["low"].values

    momentum = config["strategy"]["momentum"]
    mr = config["strategy"]["mean_reversion"]

    df["ema_fast"] = talib.EMA(close, timeperiod=momentum["fast_period"])
    df["ema_slow"] = talib.EMA(close, timeperiod=momentum["slow_period"])
    df["rsi"] = talib.RSI(close, timeperiod=momentum["rsi_period"])
    df["bb_upper"], df["bb_mid"], df["bb_lower"] = talib.BBANDS(
        close,
        timeperiod=mr["bb_period"],
        nbdevup=mr["bb_std"],
        nbdevdn=mr["bb_std"],
    )
    df["macd"], df["macd_signal"], df["macd_hist"] = talib.MACD(
        close, fastperiod=12, slowperiod=26, signalperiod=9
    )
    df["atr"] = talib.ATR(high, low, close, timeperiod=14)
    df["vol_ma"] = talib.SMA(df["volume"].values.astype(float), timeperiod=20)

    return df


def generate_signal(
    df: pd.DataFrame, config: dict, sentiment_score: float = 0.0
) -> SignalResult:
    """Generate a trading signal from an indicator-enriched DataFrame."""
    if len(df) < 2:
        return SignalResult(
            symbol="", signal=Signal.HOLD, strength=0.0, reasons=["Insufficient data"]
        )

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    momentum = config["strategy"]["momentum"]

    score = 0.0
    reasons: list[str] = []

    # EMA crossover
    if latest["ema_fast"] > latest["ema_slow"] and prev["ema_fast"] <= prev["ema_slow"]:
        score += 2.0
        reasons.append("EMA bullish crossover")
    elif latest["ema_fast"] < latest["ema_slow"] and prev["ema_fast"] >= prev["ema_slow"]:
        score -= 2.0
        reasons.append("EMA bearish crossover")
    elif latest["ema_fast"] > latest["ema_slow"]:
        score += 0.5
        reasons.append("Price above slow EMA (uptrend)")
    elif latest["ema_fast"] < latest["ema_slow"]:
        score -= 0.5
        reasons.append("Price below slow EMA (downtrend)")

    # RSI
    rsi = latest["rsi"]
    if not np.isnan(rsi):
        if rsi < momentum["rsi_oversold"]:
            score += 1.5
            reasons.append(f"RSI oversold ({rsi:.1f})")
        elif rsi > momentum["rsi_overbought"]:
            score -= 1.5
            reasons.append(f"RSI overbought ({rsi:.1f})")

    # MACD histogram direction
    if not np.isnan(latest["macd_hist"]):
        if latest["macd_hist"] > 0 and prev["macd_hist"] <= 0:
            score += 1.0
            reasons.append("MACD histogram turned positive")
        elif latest["macd_hist"] < 0 and prev["macd_hist"] >= 0:
            score -= 1.0
            reasons.append("MACD histogram turned negative")

    # Bollinger Band touch
    if latest["close"] <= latest["bb_lower"]:
        score += 1.5
        reasons.append("Price at lower Bollinger Band (oversold)")
    elif latest["close"] >= latest["bb_upper"]:
        score -= 1.5
        reasons.append("Price at upper Bollinger Band (overbought)")

    # Volume confirmation
    if not np.isnan(latest["vol_ma"]) and latest["vol_ma"] > 0:
        vol_ratio = latest["volume"] / latest["vol_ma"]
        if vol_ratio > 1.5:
            if score > 0:
                score += 0.5
                reasons.append(f"High volume confirms ({vol_ratio:.1f}x avg)")
            elif score < 0:
                score -= 0.5
                reasons.append(f"High volume confirms ({vol_ratio:.1f}x avg)")

    # Sentiment
    if abs(sentiment_score) > 0.01:
        score += sentiment_score

    # Convert score to signal
    max_possible = 8.0
    strength = min(abs(score) / max_possible, 1.0)

    if score >= 2.0:
        return SignalResult(symbol="", signal=Signal.BUY, strength=strength, reasons=reasons)
    elif score <= -2.0:
        return SignalResult(symbol="", signal=Signal.SELL, strength=strength, reasons=reasons)
    else:
        return SignalResult(symbol="", signal=Signal.HOLD, strength=strength, reasons=reasons)
