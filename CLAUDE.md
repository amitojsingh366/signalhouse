# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Algorithmic swing trading bot for TSX-listed stocks and CAD-hedged ETFs, executing through Interactive Brokers (IBKR) in a Canadian TFSA account. Targets 2-3 round-trips per week on a ~$1,000 CAD portfolio.

## Commands

```bash
# Setup (local dev)
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run the bot (requires IB Gateway running)
python -m trader.main
# or: trader

# Docker deployment (IB Gateway + bot)
cp .env.example .env        # fill in IBKR credentials
docker compose up -d         # start everything
docker compose logs -f trader  # watch bot logs

# Tests
pytest                     # all tests
pytest tests/test_risk.py  # single file
pytest -k "stop_loss"      # by name pattern

# Lint
ruff check src/ tests/     # check
ruff check --fix src/      # auto-fix

# Type check
mypy src/
```

## Architecture

```
src/trader/
├── main.py       # Entry point — scheduler loop, runs during market hours (ET)
├── config.py     # Loads settings.yaml + settings.local.yaml (secrets)
├── broker.py     # IBKR wrapper via ib_insync — connects, fetches data, places orders
├── signals.py    # Technical analysis: EMA, RSI, MACD, Bollinger Bands → BUY/SELL/HOLD
├── strategy.py   # Orchestrator — scans universe, checks exits, picks entries
├── risk.py       # Position sizing (ATR-based), stop losses, drawdown circuit breakers
├── backtest.py   # Replays historical bars through signal generator
└── notifier.py   # Discord webhook alerts for trades and daily status
```

**Data flow:** `main` runs a loop every 15 min during market hours → `strategy.scan_and_trade()` → for each symbol, `broker` fetches historical bars → `signals` computes indicators and generates BUY/SELL/HOLD → `risk` validates position sizing and stops → `broker` executes order → `notifier` sends Discord alert.

**Config:** `config/settings.yaml` has defaults. Create `config/settings.local.yaml` (gitignored) for secrets (IBKR account ID, Discord webhook URL). Local file merges over defaults. Environment variables `IBKR_HOST` and `DISCORD_WEBHOOK_URL` override config (used by Docker).

**Docker:** `docker-compose.yml` runs IB Gateway (`ghcr.io/gnzsnz/ib-gateway`) + the trader bot. IBKR credentials go in `.env` (gitignored). The trader container connects to `ib-gateway` hostname instead of localhost.

## Bot Features

### Discord Notifications (via webhook)
- **Trade alerts**: Sent on every BUY/SELL with symbol, quantity, price, dollar value, and signal reasons
- **Daily status**: Sent at 3:50 PM ET each trading day — portfolio value, cash, open positions with individual P&L %
- **Error alerts**: Sent when a scan fails or an order errors out
- **Halt alerts**: Sent if daily (8%) or total (20%) drawdown circuit breakers trigger
- **Startup/shutdown**: Sent when bot connects or stops

### Scheduling
- Scans every 15 minutes during market hours (9:30 AM – 4:00 PM ET), weekdays only
- Resets daily risk tracking at ~9:45 AM ET each morning
- Sends daily status at 3:50 PM ET
- Sleeps outside market hours (no CPU usage)

### Connection Resilience
- Retries IBKR connection up to 10 times with 15-second gaps on startup (IB Gateway takes time to boot)
- Strategy initialization tolerates read-only API mode gracefully
- Graceful shutdown on SIGINT/SIGTERM — notifies Discord before exiting

### Risk Safety Nets
- 5% hard stop loss per position (never moves down)
- 3% trailing stop (ratchets up as price rises)
- Max 7-day hold period — auto-exits stale positions
- Max 2 simultaneous positions
- Max 50% of portfolio in a single position
- 8% daily drawdown → halt trading for the day
- 20% total drawdown from peak → halt all trading

## Symbol Universe

The bot scans 43 securities (configured in `config/settings.yaml`). This list is static but can be edited in the config file. Symbols ending in `.TO` route to TSX; symbols ending in `.NE` route to CBOE Canada (CDRs).

### CAD-Hedged ETFs (7)
| Symbol | Name | Description |
|--------|------|-------------|
| XSP.TO | iShares S&P 500 CAD-Hedged | S&P 500 index |
| ZQQ.TO | BMO NASDAQ-100 CAD-Hedged | NASDAQ-100 index |
| ZSP.TO | BMO S&P 500 CAD-Hedged | S&P 500 index |
| HXS.TO | Horizons S&P 500 CAD-Hedged | S&P 500 index |
| TEC.TO | TD Global Technology Leaders | Global tech stocks |
| XQQ.TO | iShares NASDAQ-100 CAD-Hedged | NASDAQ-100 index |
| QQC-F.TO | Invesco NASDAQ-100 CAD-Hedged | NASDAQ-100 index |

### CDRs — CAD-Hedged US Stocks (10)
Trade on CBOE Canada. CAD-denominated, currency-hedged fractional exposure to US stocks.

| Symbol | Name | Sector |
|--------|------|--------|
| AAPL.NE | Apple | Technology |
| MSFT.NE | Microsoft | Technology |
| GOOG.NE | Alphabet | Technology |
| AMD.NE | AMD | Semiconductors |
| ASML.NE | ASML | Semiconductors |
| NVDA.NE | NVIDIA | Semiconductors |
| AMZN.NE | Amazon | Consumer Tech |
| META.NE | Meta | Technology |
| TSLA.NE | Tesla | Automotive/Tech |
| NFLX.NE | Netflix | Entertainment |

### Large-Cap TSX Stocks (26)
| Symbol | Name | Sector |
|--------|------|--------|
| RY.TO | Royal Bank of Canada | Financials |
| TD.TO | TD Bank | Financials |
| BMO.TO | Bank of Montreal | Financials |
| MFC.TO | Manulife Financial | Financials |
| IFC.TO | Intact Financial | Financials |
| BN.TO | Brookfield Corp | Financials |
| SHOP.TO | Shopify | Technology |
| CSU.TO | Constellation Software | Technology |
| GIB-A.TO | CGI Group | Technology |
| TRI.TO | Thomson Reuters | Technology |
| CNR.TO | CN Rail | Industrials |
| CP.TO | CP Rail | Industrials |
| WCN.TO | Waste Connections | Industrials |
| MG.TO | Magna International | Industrials |
| ENB.TO | Enbridge | Energy |
| SU.TO | Suncor Energy | Energy |
| NTR.TO | Nutrien | Materials |
| AEM.TO | Agnico Eagle Mines | Materials |
| ABX.TO | Barrick Gold | Materials |
| WFG.TO | West Fraser Timber | Materials |
| ATD.TO | Alimentation Couche-Tard | Consumer Staples |
| DOL.TO | Dollarama | Consumer Staples |
| SAP.TO | Saputo | Consumer Staples |
| L.TO | Loblaw Companies | Consumer Staples |
| QSR.TO | Restaurant Brands Intl | Consumer Discretionary |
| FTS.TO | Fortis | Utilities |
| CCL-B.TO | CCL Industries | Industrials |

## Documentation

- `docs/STRATEGY.md` — Full strategy explanation, signal scoring, position sizing, expected returns
- `docs/NEXT_STEPS.md` — Roadmap, deployment commands, phase plan for paper → live trading

## Deployment

- Server: `your-server` (Ubuntu ARM, your server)
- SSH: `ssh -i your-ssh-key ubuntu@your-server`
- Repo on server: `~/trader/`
- Currently paper trading on account DUP468689

## Key Constraints

- **Commission awareness:** IBKR charges ~$1 CAD minimum per trade. With small capital, every trade costs ~0.1% so high-frequency strategies are not viable.
- **Routing:** `.TO` symbols route to TSX via `Stock(symbol, "SMART", "CAD", primaryExchange="TSE")`. `.NE` symbols (CDRs) route to CBOE Canada via `Stock(symbol, "SMART", "CAD")` with no primaryExchange. Both handled by `broker.make_contract()`.
- **IBKR connection:** Requires IB Gateway or TWS running locally. Port 4002 = paper trading, 4001 = live. The bot uses `ib_insync` which needs `nest_asyncio` internally for async compatibility.
- **Risk hard limits:** Trading halts automatically at 8% daily drawdown or 20% total drawdown from peak. These are circuit breakers, not configurable without code change intent.
