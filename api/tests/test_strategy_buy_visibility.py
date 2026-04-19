from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from trader_api.services.risk import RiskManager
from trader_api.services.signals import Signal, SignalResult
from trader_api.services.strategy import Strategy


class DummySentiment:
    async def analyze(self, symbol: str):
        raise AssertionError(f"sentiment.analyze() should not be called for {symbol} in this test")


class DummyMarketData:
    def __init__(self, regime_df: pd.DataFrame) -> None:
        self._regime_df = regime_df

    async def get_historical_data(self, symbol: str, period: str = "60d"):
        if symbol == "REGIME.TO":
            return self._regime_df
        return None

    async def get_batch_prices(self, symbols: list[str]) -> dict[str, float]:
        return {symbol: 100.0 for symbol in symbols}


class DummyPortfolio:
    def __init__(self, holdings: dict[str, dict[str, float]], cash: float) -> None:
        self._holdings = holdings
        self._cash = cash

    async def get_holdings_dict(self) -> dict[str, dict[str, float]]:
        return self._holdings

    async def _get_meta(self):
        return SimpleNamespace(cash=self._cash)

    async def get_portfolio_value(self, live_prices: dict[str, float]) -> float:
        total = self._cash
        for symbol, holding in self._holdings.items():
            total += holding["quantity"] * live_prices.get(symbol, holding["avg_cost"])
        return total


def _config() -> dict:
    return {
        "strategy": {
            "symbols": ["BUY.TO", "SELL.TO"],
            "max_sector_pct": 0.4,
            "momentum": {
                "fast_period": 10,
                "slow_period": 30,
                "rsi_period": 14,
                "rsi_oversold": 30,
                "rsi_overbought": 70,
            },
            "mean_reversion": {"bb_period": 20, "bb_std": 2.0},
            "min_hold_days": 0,
            "max_hold_days": 7,
            "regime_filter_symbol": "REGIME.TO",
            "regime_filter_sma_days": 3,
            "regime_filter_period": "5d",
        },
        "risk": {
            "max_position_pct": 0.3,
            "max_positions": 5,
            "stop_loss_pct": 0.05,
            "trailing_stop_pct": 0.03,
            "take_profit_pct": 0.08,
            "max_daily_loss_pct": 0.08,
            "max_total_drawdown_pct": 0.2,
        },
    }


def _buy_signal() -> SignalResult:
    return SignalResult(
        symbol="BUY.TO",
        signal=Signal.BUY,
        strength=0.6,
        reasons=["Price: $100.00"],
        score=4.0,
        technical_score=3.5,
        sentiment_score=0.3,
        commodity_score=0.2,
    )


def _sell_signal() -> SignalResult:
    return SignalResult(
        symbol="SELL.TO",
        signal=Signal.SELL,
        strength=0.5,
        reasons=["Price: $95.00"],
        score=-3.5,
        technical_score=-3.0,
        sentiment_score=-0.4,
        commodity_score=-0.1,
    )


def _risk_off_regime_df() -> pd.DataFrame:
    return pd.DataFrame({"close": [100.0, 100.0, 90.0]})


@pytest.mark.asyncio
async def test_recommendations_keep_buy_signals_when_regime_blocks(monkeypatch: pytest.MonkeyPatch):
    strategy = Strategy(
        market_data=DummyMarketData(_risk_off_regime_df()),
        risk=RiskManager(_config()),
        portfolio=DummyPortfolio({"SELL.TO": {"quantity": 1.0, "avg_cost": 100.0}}, cash=500.0),
        config=_config(),
        sentiment=DummySentiment(),
    )

    async def fake_scan_universe():
        return [_buy_signal(), _sell_signal()]

    monkeypatch.setattr(strategy, "scan_universe", fake_scan_universe)

    recs = await strategy.get_top_recommendations(n=5)

    assert [sig.symbol for sig in recs["buys"]] == ["BUY.TO"]
    assert [sig.symbol for sig in recs["sells"]] == ["SELL.TO"]
    assert recs["funding"] == []
    assert "Regime filter risk-off" in recs["buy_block_reason"]


@pytest.mark.asyncio
async def test_action_plan_surfaces_non_actionable_buy_when_regime_blocks(
    monkeypatch: pytest.MonkeyPatch,
):
    strategy = Strategy(
        market_data=DummyMarketData(_risk_off_regime_df()),
        risk=RiskManager(_config()),
        portfolio=DummyPortfolio({}, cash=1000.0),
        config=_config(),
        sentiment=DummySentiment(),
    )

    async def fake_scan_universe():
        return [_buy_signal()]

    monkeypatch.setattr(strategy, "scan_universe", fake_scan_universe)

    plan = await strategy.get_action_plan()
    buy_actions = [action for action in plan["actions"] if action["type"] == "BUY"]

    assert len(buy_actions) == 1
    assert buy_actions[0]["symbol"] == "BUY.TO"
    assert buy_actions[0]["actionable"] is False
    assert "Regime filter risk-off" in buy_actions[0]["detail"]


@pytest.mark.asyncio
async def test_recommendations_keep_buy_signals_when_risk_halted(monkeypatch: pytest.MonkeyPatch):
    risk = RiskManager(_config())
    risk.halted = True
    risk.halt_reason = "Total drawdown limit hit: 20.1%"
    strategy = Strategy(
        market_data=DummyMarketData(pd.DataFrame({"close": [100.0, 101.0, 102.0]})),
        risk=risk,
        portfolio=DummyPortfolio({}, cash=1000.0),
        config=_config(),
        sentiment=DummySentiment(),
    )

    async def fake_scan_universe():
        return [_buy_signal()]

    monkeypatch.setattr(strategy, "scan_universe", fake_scan_universe)

    recs = await strategy.get_top_recommendations(n=5)

    assert [sig.symbol for sig in recs["buys"]] == ["BUY.TO"]
    assert "Risk halt active" in recs["buy_block_reason"]
