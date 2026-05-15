from datetime import UTC, datetime

from trader_api.models import Trade
from trader_api.services.portfolio import Portfolio


def test_accidental_buy_can_be_replayed_as_sell() -> None:
    timestamp = datetime(2026, 5, 15, 14, 30, tzinfo=UTC)
    trade = Trade(
        id=1,
        symbol="SHOP.TO",
        action="BUY",
        quantity=10,
        price=25,
        total=250,
        timestamp=timestamp,
    )
    holdings = {
        "SHOP.TO": {
            "symbol": "SHOP.TO",
            "quantity": 20.0,
            "avg_cost": 22.5,
            "entry_date": timestamp,
        }
    }

    baseline_cash = Portfolio._reverse_trade(holdings, 750.0, trade)

    assert baseline_cash == 1000.0
    assert holdings["SHOP.TO"]["quantity"] == 10.0
    assert holdings["SHOP.TO"]["avg_cost"] == 20.0

    trade.action = "SELL"
    replayed_cash = Portfolio._apply_trade(holdings, baseline_cash, trade)

    assert replayed_cash == 1250.0
    assert "SHOP.TO" not in holdings
    assert trade.pnl == 50.0
    assert trade.pnl_pct == 25.0


def test_accidental_buy_delete_restores_pre_trade_state() -> None:
    timestamp = datetime(2026, 5, 15, 14, 30, tzinfo=UTC)
    trade = Trade(
        id=1,
        symbol="SHOP.TO",
        action="BUY",
        quantity=10,
        price=25,
        total=250,
        timestamp=timestamp,
    )
    holdings = {
        "SHOP.TO": {
            "symbol": "SHOP.TO",
            "quantity": 20.0,
            "avg_cost": 22.5,
            "entry_date": timestamp,
        }
    }

    baseline_cash = Portfolio._reverse_trade(holdings, 750.0, trade)

    assert baseline_cash == 1000.0
    assert holdings["SHOP.TO"]["quantity"] == 10.0
    assert holdings["SHOP.TO"]["avg_cost"] == 20.0


def test_accidental_sell_can_be_replayed_as_buy() -> None:
    timestamp = datetime(2026, 5, 15, 14, 30, tzinfo=UTC)
    trade = Trade(
        id=1,
        symbol="SHOP.TO",
        action="SELL",
        quantity=10,
        price=25,
        total=250,
        pnl=50,
        pnl_pct=25,
        timestamp=timestamp,
    )
    holdings = {}

    baseline_cash = Portfolio._reverse_trade(holdings, 1250.0, trade)

    assert baseline_cash == 1000.0
    assert holdings["SHOP.TO"]["quantity"] == 10.0
    assert holdings["SHOP.TO"]["avg_cost"] == 20.0

    trade.action = "BUY"
    replayed_cash = Portfolio._apply_trade(holdings, baseline_cash, trade)

    assert replayed_cash == 750.0
    assert holdings["SHOP.TO"]["quantity"] == 20.0
    assert holdings["SHOP.TO"]["avg_cost"] == 22.5
    assert trade.pnl is None
    assert trade.pnl_pct is None


def test_accidental_sell_delete_restores_pre_trade_state() -> None:
    timestamp = datetime(2026, 5, 15, 14, 30, tzinfo=UTC)
    trade = Trade(
        id=1,
        symbol="SHOP.TO",
        action="SELL",
        quantity=10,
        price=25,
        total=250,
        pnl=50,
        pnl_pct=25,
        timestamp=timestamp,
    )
    holdings = {}

    baseline_cash = Portfolio._reverse_trade(holdings, 1250.0, trade)

    assert baseline_cash == 1000.0
    assert holdings["SHOP.TO"]["quantity"] == 10.0
    assert holdings["SHOP.TO"]["avg_cost"] == 20.0
