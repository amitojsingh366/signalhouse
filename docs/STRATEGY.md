# Trading Strategy & Technical Documentation

## Overview

Automated swing trading bot targeting TSX-listed stocks and CAD-hedged ETFs in a Canadian TFSA account via Interactive Brokers. Designed for a ~$1,000 CAD portfolio, targeting 2-3 round-trip trades per week with 2-7 day holding periods.

## Strategy: Hybrid Momentum + Mean Reversion

The bot combines two complementary approaches into a single scoring system. Each 15-minute scan evaluates all 30 symbols and picks the highest-conviction entry.

### Signal Scoring System (-6 to +6)

Every scan computes a numerical score for each symbol. A score >= +2 triggers a BUY signal; <= -2 triggers SELL. The magnitude maps to a 0-1 "strength" value used to rank candidates and filter weak signals.

#### Momentum Signals (trend-following)

| Indicator | Condition | Score |
|-----------|-----------|-------|
| EMA Crossover | 10-day EMA crosses above 30-day EMA | +2.0 |
| EMA Crossover | 10-day EMA crosses below 30-day EMA | -2.0 |
| EMA Trend | Price above slow EMA (existing uptrend) | +0.5 |
| EMA Trend | Price below slow EMA (existing downtrend) | -0.5 |
| RSI (14-period) | RSI < 30 (oversold) | +1.5 |
| RSI (14-period) | RSI > 70 (overbought) | -1.5 |
| MACD Histogram | Histogram crosses above zero | +1.0 |
| MACD Histogram | Histogram crosses below zero | -1.0 |

#### Mean Reversion Signals (counter-trend)

| Indicator | Condition | Score |
|-----------|-----------|-------|
| Bollinger Band (20-period, 2 std) | Price at or below lower band | +1.5 |
| Bollinger Band (20-period, 2 std) | Price at or above upper band | -1.5 |

#### Volume Confirmation

| Condition | Effect |
|-----------|--------|
| Volume > 1.5x 20-day average | Amplifies existing score by +/-0.5 |

### Entry Rules

1. Signal score must be >= +2.0 (BUY)
2. Signal strength must be >= 0.4 (moderate conviction)
3. Must have fewer than 2 open positions (max_positions = 2)
4. No drawdown circuit breakers active
5. Must be during market hours (9:30 AM - 4:00 PM ET), weekdays only
6. Best candidate (highest strength) among all BUY signals is selected

### Exit Rules (checked in priority order)

1. **Hard stop loss**: Price drops 5% below entry price -> immediate sell
2. **Trailing stop**: 3% trailing stop from highest price since entry. Ratchets up as price rises, never moves down
3. **Max hold time**: Position held for 7+ days -> sell regardless
4. **Sell signal**: Technical signal score <= -2.0 with strength >= 0.3

### Position Sizing (ATR-Based)

- Risk 2% of portfolio per trade
- Stop distance = 2x ATR (14-period Average True Range)
- Shares = (portfolio * 2%) / (2 * ATR)
- Capped at 50% of portfolio in any single position
- Minimum 1 share if affordable

**Example**: $1,000 portfolio, stock at $50, ATR = $1.50
- Risk amount: $1,000 * 0.02 = $20
- Shares via ATR: $20 / (2 * $1.50) = 6 shares ($300 position)

## Risk Management

### Circuit Breakers (hard-coded safety limits)

| Rule | Threshold | Effect |
|------|-----------|--------|
| Daily drawdown | 8% loss from day's opening value | Halt all trading for the day |
| Total drawdown | 20% loss from peak portfolio value | Halt all trading until manual reset |

### Commission Awareness

IBKR charges ~$1 CAD minimum per trade. On a $1,000 portfolio:
- Round-trip cost: ~$2 (0.2% of portfolio)
- Break-even on a trade requires >0.2% price move
- This is why the bot uses swing trading (2-7 days) rather than day trading

## Symbol Universe (30 securities)

### CAD-Hedged ETFs (4)
XSP.TO, ZQQ.TO, ZSP.TO, HXS.TO — track US indices without currency risk

### Large-Cap TSX Stocks (26)
Banks (RY, TD, BMO), energy (ENB, SU), tech (SHOP, CSU), industrials (CNR, CP), and more. Selected for liquidity and swing-trading suitability.

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Language | Python 3.11 | Trading ecosystem compatibility |
| Broker API | `ib_insync` | Async wrapper for Interactive Brokers TWS/Gateway API |
| Technical Analysis | `TA-Lib` (C library + Python bindings) | EMA, RSI, MACD, Bollinger Bands, ATR computation |
| Data Processing | `pandas`, `numpy` | Price data manipulation and indicator DataFrames |
| Notifications | `aiohttp` + Discord webhooks | Real-time trade alerts and daily status |
| Configuration | `PyYAML` | Layered config (settings.yaml + settings.local.yaml) |
| Containerization | Docker + Docker Compose | IB Gateway + bot deployed as two-container stack |
| IB Gateway | `ghcr.io/gnzsnz/ib-gateway` | Headless IBKR gateway with IBC for auto-login |
| Testing | `pytest` | 12 unit tests covering signals and risk management |
| Linting | `ruff` | Fast Python linter and formatter |
| Type Checking | `mypy` | Static type analysis |

## Architecture

```
main.py (scheduler)
  -> strategy.scan_and_trade() every 15 min during market hours
    -> broker.get_historical_data() for each symbol (60 days of daily bars)
    -> signals.compute_indicators() + generate_signal() -> BUY/SELL/HOLD
    -> risk.calculate_position_size() -> how many shares
    -> broker.buy() or broker.sell() -> execute order
    -> notifier.trade_alert() -> Discord notification
```

## Deployment

Two Docker containers via `docker-compose.yml`:

1. **ib-gateway**: Runs IB Gateway with IBC for automated login. Exposes API on port 4002 (paper) or 4001 (live). VNC on port 5900 for visual monitoring.

2. **trader**: The bot itself. Uses `network_mode: service:ib-gateway` to share the gateway's network namespace (connects as localhost). Config mounted read-only from `./config/`.

Credentials in `.env` file (gitignored). Discord webhook URL in `config/settings.local.yaml` (gitignored).

## Expected Performance

### Realistic Estimates for $1,000 CAD Portfolio

**Important**: These are rough estimates based on typical swing trading performance. Actual results depend on market conditions. Past technical signals do not guarantee future returns.

#### Per-Trade Economics
- Average position: $300-$500 (30-50% of portfolio)
- Target gain per winning trade: 1.5-3% ($4.50-$15)
- Average loss per losing trade: 3-5% ($9-$25, capped by stop loss)
- Commission cost per round trip: ~$2

#### Weekly Projections (2-3 trades/week)

| Scenario | Win Rate | Avg Win | Avg Loss | Weekly P&L | Monthly |
|----------|----------|---------|----------|------------|---------|
| Conservative | 45% | +2% | -4% | -$1 to +$3 | -$4 to +$12 |
| Moderate | 55% | +2.5% | -3.5% | +$2 to +$8 | +$8 to +$32 |
| Optimistic | 60% | +3% | -3% | +$5 to +$12 | +$20 to +$48 |

#### Key Constraints on Returns
- **Small capital**: $1,000 limits position sizes. Commissions eat ~0.2% per round trip.
- **Swing trading frequency**: 2-3 trades/week, not day trading, so compounding is slow.
- **Stop losses cap downside**: 5% hard stop + 3% trailing stop prevent catastrophic single-trade losses.
- **Circuit breakers**: 8% daily / 20% total drawdown limits protect against extended losing streaks.

#### 6-Month Range (rough)
- **Bear case**: -$50 to -$100 (drawdown limits prevent worse)
- **Base case**: +$30 to +$80 (3-8% total return)
- **Bull case**: +$100 to +$200 (10-20% total return)

These numbers improve significantly with more capital (commission drag decreases as a percentage) and after strategy tuning via backtesting.
