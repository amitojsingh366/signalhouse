"""Tests for the risk manager."""

import pytest

from trader.risk import RiskManager


@pytest.fixture
def config() -> dict:
    return {
        "risk": {
            "max_position_pct": 0.50,
            "max_positions": 2,
            "stop_loss_pct": 0.05,
            "trailing_stop_pct": 0.03,
            "max_daily_loss_pct": 0.08,
            "max_total_drawdown_pct": 0.20,
        },
        "strategy": {
            "max_hold_days": 7,
        },
    }


def test_position_sizing_basic(config: dict) -> None:
    rm = RiskManager(config)
    shares = rm.calculate_position_size(portfolio_value=1000, price=50, atr=1.0)
    # Risk 2% of $1000 = $20, stop at 2*ATR = $2, so $20/$2 = 10 shares
    # Max position: 50% of $1000 / $50 = 10 shares
    assert shares == 10


def test_position_sizing_caps_at_max(config: dict) -> None:
    rm = RiskManager(config)
    shares = rm.calculate_position_size(portfolio_value=1000, price=10, atr=0.1)
    # ATR-based: $20 / $0.2 = 100 shares
    # Max position: 50% of $1000 / $10 = 50 shares → capped
    assert shares == 50


def test_position_sizing_zero_price(config: dict) -> None:
    rm = RiskManager(config)
    assert rm.calculate_position_size(1000, 0, 1.0) == 0


def test_max_positions_enforced(config: dict) -> None:
    rm = RiskManager(config)
    rm.register_entry("A.TO", 50, 10)
    rm.register_entry("B.TO", 30, 20)
    assert not rm.can_open_position()


def test_stop_loss_triggers(config: dict) -> None:
    rm = RiskManager(config)
    rm.register_entry("RY.TO", 100, 10)
    # Price drops 6% — should trigger 5% stop
    result = rm.update_stops("RY.TO", 94.0)
    assert result is not None


def test_trailing_stop_ratchets_up(config: dict) -> None:
    rm = RiskManager(config)
    rm.register_entry("RY.TO", 100, 10)
    # Price goes up
    rm.update_stops("RY.TO", 110)
    trade = rm.open_trades["RY.TO"]
    # Trailing stop should be 110 * 0.97 = 106.7
    assert trade.stop_price == pytest.approx(106.7, abs=0.1)
    # Original 5% stop was 95 — trailing has moved it up


def test_daily_drawdown_halts_trading(config: dict) -> None:
    rm = RiskManager(config)
    rm.reset_daily(1000)
    # 9% loss exceeds 8% daily limit
    assert rm.check_drawdown(910) is True
    assert rm.halted


def test_total_drawdown_halts_trading(config: dict) -> None:
    rm = RiskManager(config)
    rm.peak_portfolio_value = 1000
    rm.daily_start_value = 850  # Already down but within daily limit
    # 21% total drawdown exceeds 20% limit
    assert rm.check_drawdown(790) is True
    assert rm.halted
