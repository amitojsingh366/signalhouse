"""Simple backtesting engine — replay historical data through the signal generator."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd

from trader_api.services.signals import Signal, compute_indicators, generate_signal

logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    symbol: str
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    quantity: int
    pnl: float
    pnl_pct: float
    hold_days: int
    exit_reason: str


@dataclass
class BacktestResult:
    initial_capital: float
    final_capital: float
    total_return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win_pct: float
    avg_loss_pct: float
    max_drawdown_pct: float
    trades: list[BacktestTrade]
    equity_curve: list[float]


@dataclass
class BacktestPosition:
    symbol: str
    entry_price: float
    entry_idx: int
    quantity: int
    highest_price: float
    stop_price: float


def run_backtest(
    symbol: str,
    df: pd.DataFrame,
    config: dict[str, Any],
    initial_capital: float = 1000.0,
) -> BacktestResult:
    risk = config["risk"]
    commission = 1.00

    df = compute_indicators(df, config)

    warmup = 35
    if len(df) <= warmup:
        return BacktestResult(
            initial_capital=initial_capital,
            final_capital=initial_capital,
            total_return_pct=0.0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            avg_win_pct=0.0,
            avg_loss_pct=0.0,
            max_drawdown_pct=0.0,
            trades=[],
            equity_curve=[initial_capital],
        )

    capital = initial_capital
    position: BacktestPosition | None = None
    trades: list[BacktestTrade] = []
    equity_curve: list[float] = []
    peak_capital = initial_capital

    for i in range(warmup, len(df)):
        window = df.iloc[: i + 1]
        current = df.iloc[i]
        price = current["close"]
        date_str = str(df.index[i])

        pos_value = position.quantity * price if position else 0
        equity = capital + pos_value
        equity_curve.append(equity)
        peak_capital = max(peak_capital, equity)

        if position is not None:
            exit_reason = ""

            if price > position.highest_price:
                position.highest_price = price
                new_stop = price * (1 - risk["trailing_stop_pct"])
                position.stop_price = max(position.stop_price, new_stop)

            if price <= position.stop_price:
                exit_reason = "Stop loss"
            elif (i - position.entry_idx) >= config["strategy"]["max_hold_days"]:
                exit_reason = "Max hold time"
            else:
                result = generate_signal(window, config)
                if result.signal == Signal.SELL and result.strength >= 0.3:
                    exit_reason = "Sell signal"

            if exit_reason:
                pnl = (price - position.entry_price) * position.quantity - 2 * commission
                pnl_pct = (price - position.entry_price) / position.entry_price * 100
                capital += position.quantity * price - commission
                trades.append(BacktestTrade(
                    symbol=symbol,
                    entry_date=str(df.index[position.entry_idx]),
                    entry_price=position.entry_price,
                    exit_date=date_str,
                    exit_price=price,
                    quantity=position.quantity,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    hold_days=i - position.entry_idx,
                    exit_reason=exit_reason,
                ))
                position = None

        elif position is None:
            result = generate_signal(window, config)
            if result.signal == Signal.BUY and result.strength >= 0.4:
                atr = current["atr"] if "atr" in current and not pd.isna(current["atr"]) else 0
                max_dollars = capital * risk["max_position_pct"]
                if atr > 0:
                    risk_amount = capital * 0.02
                    shares = int(risk_amount / (2 * atr))
                    shares = min(shares, int(max_dollars / price))
                else:
                    shares = int(max_dollars / price)
                shares = max(shares, 1)

                cost = shares * price + commission
                if cost <= capital:
                    capital -= cost
                    position = BacktestPosition(
                        symbol=symbol,
                        entry_price=price,
                        entry_idx=i,
                        quantity=shares,
                        highest_price=price,
                        stop_price=price * (1 - risk["stop_loss_pct"]),
                    )

    if position is not None:
        price = df["close"].iloc[-1]
        pnl = (price - position.entry_price) * position.quantity - 2 * commission
        capital += position.quantity * price - commission
        trades.append(BacktestTrade(
            symbol=symbol,
            entry_date=str(df.index[position.entry_idx]),
            entry_price=position.entry_price,
            exit_date=str(df.index[-1]),
            exit_price=price,
            quantity=position.quantity,
            pnl=pnl,
            pnl_pct=(price - position.entry_price) / position.entry_price * 100,
            hold_days=len(df) - 1 - position.entry_idx,
            exit_reason="End of backtest",
        ))

    final_capital = capital
    winning = [t for t in trades if t.pnl > 0]
    losing = [t for t in trades if t.pnl <= 0]

    max_dd = 0.0
    peak = equity_curve[0] if equity_curve else initial_capital
    for eq in equity_curve:
        peak = max(peak, eq)
        dd = (peak - eq) / peak
        max_dd = max(max_dd, dd)

    return BacktestResult(
        initial_capital=initial_capital,
        final_capital=final_capital,
        total_return_pct=(final_capital - initial_capital) / initial_capital * 100,
        total_trades=len(trades),
        winning_trades=len(winning),
        losing_trades=len(losing),
        win_rate=len(winning) / len(trades) * 100 if trades else 0,
        avg_win_pct=sum(t.pnl_pct for t in winning) / len(winning) if winning else 0,
        avg_loss_pct=sum(t.pnl_pct for t in losing) / len(losing) if losing else 0,
        max_drawdown_pct=max_dd * 100,
        trades=trades,
        equity_curve=equity_curve,
    )
