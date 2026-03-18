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


def bars_to_dataframe(bars: list[Any]) -> pd.DataFrame:
    """Convert ib_insync BarData list to a pandas DataFrame."""
    df = pd.DataFrame(
        {
            "date": [b.date for b in bars],
            "open": [b.open for b in bars],
            "high": [b.high for b in bars],
            "low": [b.low for b in bars],
            "close": [b.close for b in bars],
            "volume": [b.volume for b in bars],
        }
    )
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    return df


def compute_indicators(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Compute all technical indicators on a price DataFrame."""
    close = df["close"].values
    high = df["high"].values
    low = df["low"].values

    momentum = config["strategy"]["momentum"]
    mr = config["strategy"]["mean_reversion"]

    # Trend: EMAs
    df["ema_fast"] = talib.EMA(close, timeperiod=momentum["fast_period"])
    df["ema_slow"] = talib.EMA(close, timeperiod=momentum["slow_period"])

    # Momentum: RSI
    df["rsi"] = talib.RSI(close, timeperiod=momentum["rsi_period"])

    # Mean reversion: Bollinger Bands
    df["bb_upper"], df["bb_mid"], df["bb_lower"] = talib.BBANDS(
        close,
        timeperiod=mr["bb_period"],
        nbdevup=mr["bb_std"],
        nbdevdn=mr["bb_std"],
    )

    # MACD
    df["macd"], df["macd_signal"], df["macd_hist"] = talib.MACD(
        close, fastperiod=12, slowperiod=26, signalperiod=9
    )

    # ATR for volatility-based position sizing
    df["atr"] = talib.ATR(high, low, close, timeperiod=14)

    # Volume: moving average
    df["vol_ma"] = talib.SMA(df["volume"].values.astype(float), timeperiod=20)

    return df


def generate_signal(df: pd.DataFrame, config: dict) -> SignalResult:
    """Generate a trading signal from an indicator-enriched DataFrame.

    Uses a scoring system:
    - Momentum signals: EMA crossover, RSI extremes, MACD
    - Mean reversion signals: Bollinger Band touches
    - Volume confirmation

    Each factor contributes a score. Net positive = BUY, net negative = SELL.
    """
    if len(df) < 2:
        return SignalResult(
            symbol="", signal=Signal.HOLD, strength=0.0, reasons=["Insufficient data"]
        )

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    momentum = config["strategy"]["momentum"]

    score = 0.0
    reasons: list[str] = []

    # --- Momentum signals ---

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

    # --- Mean reversion signals ---

    # Bollinger Band touch
    if latest["close"] <= latest["bb_lower"]:
        score += 1.5
        reasons.append("Price at lower Bollinger Band (oversold)")
    elif latest["close"] >= latest["bb_upper"]:
        score -= 1.5
        reasons.append("Price at upper Bollinger Band (overbought)")

    # --- Volume confirmation ---
    if not np.isnan(latest["vol_ma"]) and latest["vol_ma"] > 0:
        vol_ratio = latest["volume"] / latest["vol_ma"]
        if vol_ratio > 1.5:
            # High volume confirms the direction of the signal
            if score > 0:
                score += 0.5
                reasons.append(f"High volume confirms ({vol_ratio:.1f}x avg)")
            elif score < 0:
                score -= 0.5
                reasons.append(f"High volume confirms ({vol_ratio:.1f}x avg)")

    # --- Convert score to signal ---
    max_possible = 6.0  # Approximate max score
    strength = min(abs(score) / max_possible, 1.0)

    if score >= 2.0:
        return SignalResult(symbol="", signal=Signal.BUY, strength=strength, reasons=reasons)
    elif score <= -2.0:
        return SignalResult(symbol="", signal=Signal.SELL, strength=strength, reasons=reasons)
    else:
        return SignalResult(symbol="", signal=Signal.HOLD, strength=strength, reasons=reasons)
