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

## Key Constraints

- **Commission awareness:** IBKR charges ~$1 CAD minimum per trade. With small capital, every trade costs ~0.1% so high-frequency strategies are not viable.
- **TSX routing:** All contracts use `Stock(symbol, "SMART", "CAD", primaryExchange="TSE")`. Symbols in config use `.TO` suffix (e.g., `RY.TO`) which gets stripped in `broker.make_tsx_contract()`.
- **IBKR connection:** Requires IB Gateway or TWS running locally. Port 4002 = paper trading, 4001 = live. The bot uses `ib_insync` which needs `nest_asyncio` internally for async compatibility.
- **Risk hard limits:** Trading halts automatically at 8% daily drawdown or 20% total drawdown from peak. These are circuit breakers, not configurable without code change intent.
