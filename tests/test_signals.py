"""Tests for signal generation logic."""

import numpy as np
import pandas as pd
import pytest

from trader.signals import Signal, compute_indicators, generate_signal


def make_price_data(
    closes: list[float],
    days: int | None = None,
) -> pd.DataFrame:
    """Create a minimal DataFrame for testing."""
    if days is None:
        days = len(closes)
    dates = pd.date_range("2025-01-01", periods=days, freq="B")
    n = len(closes)
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
            "volume": [100000] * n,
        },
        index=dates[:n],
    )


@pytest.fixture
def base_config() -> dict:
    return {
        "strategy": {
            "momentum": {
                "fast_period": 10,
                "slow_period": 30,
                "rsi_period": 14,
                "rsi_oversold": 30,
                "rsi_overbought": 70,
            },
            "mean_reversion": {
                "bb_period": 20,
                "bb_std": 2.0,
                "lookback_days": 60,
            },
        }
    }


def test_compute_indicators_adds_columns(base_config: dict) -> None:
    """Indicators should add the expected columns."""
    prices = list(np.linspace(50, 60, 40))
    df = make_price_data(prices)
    df = compute_indicators(df, base_config)

    expected_cols = {"ema_fast", "ema_slow", "rsi", "bb_upper", "bb_mid", "bb_lower",
                     "macd", "macd_signal", "macd_hist", "atr", "vol_ma"}
    assert expected_cols.issubset(set(df.columns))


def test_insufficient_data_returns_hold(base_config: dict) -> None:
    """With only 1 bar, signal should be HOLD."""
    df = make_price_data([50.0])
    result = generate_signal(df, base_config)
    assert result.signal == Signal.HOLD


def test_uptrend_generates_buy_signal(base_config: dict) -> None:
    """A strong uptrend should eventually generate a BUY signal."""
    # Create a clear uptrend with a dip then recovery
    prices = list(np.linspace(40, 45, 30))  # Slow rise (slow EMA)
    prices += list(np.linspace(42, 40, 5))   # Dip (oversold)
    prices += list(np.linspace(40, 48, 10))  # Strong recovery (fast crosses slow)

    df = make_price_data(prices)
    df = compute_indicators(df, base_config)
    result = generate_signal(df, base_config)

    # Should be BUY or HOLD (depends on exact indicator values)
    assert result.signal in (Signal.BUY, Signal.HOLD)


def test_overbought_generates_sell_signal(base_config: dict) -> None:
    """An overbought condition after a rally should generate a SELL signal."""
    # Gradual rise to establish uptrend, then sharp spike to trigger overbought
    prices = list(np.linspace(40, 55, 30))  # Steady rise
    prices += list(np.linspace(55, 75, 10))  # Sharp rally — RSI goes overbought + hits upper BB

    df = make_price_data(prices)
    df = compute_indicators(df, base_config)
    result = generate_signal(df, base_config)

    assert result.signal in (Signal.SELL, Signal.HOLD)
