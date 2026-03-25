# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Discord-based trading recommendation and portfolio tracking bot for TSX-listed stocks and CAD-hedged ETFs. Provides buy/sell signals via technical analysis, tracks holdings reported by the user, and sends daily P&L summaries. Designed for a Canadian TFSA account with ~$1,000 CAD portfolio.

**This is NOT an auto-trading bot** — it provides recommendations and the user executes trades manually via their brokerage UI (Wealthsimple, IBKR, etc.), then reports them back to the bot via Discord slash commands or screenshot uploads.

## Commands

```bash
# Setup (local dev)
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run the bot (requires Discord bot token)
python -m trader.main
# or: trader

# Docker deployment
cp .env.example .env        # fill in Discord + Anthropic keys
docker compose up -d         # start bot
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
├── main.py           # Entry point — wires components, starts Discord bot
├── config.py         # Loads settings.yaml + settings.local.yaml (secrets)
├── bot.py            # Discord bot — slash commands, recheck buttons, scheduled tasks
├── market_data.py    # yfinance wrapper — fetches prices and historical data
├── portfolio.py      # JSON-backed portfolio tracking (holdings, trades, P&L)
├── signals.py        # Technical analysis: EMA, RSI, MACD, Bollinger Bands → BUY/SELL/HOLD
├── strategy.py       # Recommendation engine — scans universe, generates signals (no execution)
├── sentiment.py      # Market sentiment — analyst consensus, Fear & Greed, news headlines
├── risk.py           # Position sizing (ATR-based), stop losses, drawdown circuit breakers
├── vision.py         # Claude API vision — parses brokerage screenshots into holdings
└── backtest.py       # Replays historical bars through signal generator
```

**Data flow:** `bot.py` runs scheduled scans every 15 min during market hours → `strategy.scan_universe()` → for each symbol, `market_data` fetches historical bars via yfinance → `signals` computes indicators and generates BUY/SELL/HOLD → bot posts top signals to Discord with recheck buttons. User reports trades via `/buy` and `/sell` slash commands → `portfolio` tracks holdings and P&L.

**Config:** `config/settings.yaml` has defaults. Create `config/settings.local.yaml` (gitignored) for secrets (Discord bot token, channel ID, Anthropic API key). Local file merges over defaults. Environment variables `DISCORD_BOT_TOKEN`, `DISCORD_CHANNEL_ID`, `DISCORD_GUILD_ID`, and `ANTHROPIC_API_KEY` override config (used by Docker).

**Docker:** `docker-compose.yml` runs the bot as a single container. Credentials go in `.env` (gitignored). Portfolio data persists in `./data/` volume.

## Discord Slash Commands

| Command | Description |
|---------|-------------|
| `/buy <symbol> <quantity> <price>` | Record a buy trade |
| `/sell <symbol> <quantity> <price>` | Record a sell trade |
| `/upload <image>` | Parse screenshot of holdings via Claude vision |
| `/holdings` | View current portfolio with live prices and P&L |
| `/pnl` | Daily + total P&L breakdown |
| `/recommend` | Get current top buy/sell signals (on-demand) |
| `/check <symbol>` | Check signal + sentiment for any symbol (autocompletes held tokens) |
| `/status` | Bot uptime, portfolio summary |

## Bot Features

### Signal Recommendations
- Scans 92 symbols every 15 min during market hours
- Posts top BUY/SELL signals with strength % and reasons
- Every signal has a **Recheck** button — re-runs analysis on click
- Pre-market movers at 8:00 AM ET (US counterparts for CDRs)
- `/check` command for on-demand signal checks with autocomplete

### Market Sentiment (sentiment.py)
- **Analyst consensus** via yfinance: Strong Buy/Buy/Hold/Sell counts → score ±1.0
- **CNN Fear & Greed Index** via `fear-greed` lib: market-wide mood → contrarian modifier ±0.5
- **News headline sentiment**: keyword-based scoring of recent headlines → ±0.5
- All data cached (analyst 4h, Fear & Greed 1h, news 30min) to respect rate limits
- Failures silently default to neutral (0) — never blocks signal generation

### Portfolio Tracking
- User reports trades via `/buy` and `/sell` (supports fractional shares)
- `/upload` parses brokerage screenshots using Claude vision API
- `/holdings` has Edit button to modify holdings inline
- Symbol resolution: tries `.TO` → `.NE` → US for bare tickers
- JSON persistence at `data/portfolio.json`

### Daily Status (3:50 PM ET)
- Portfolio value, cash, each position with P&L %
- Daily and total P&L tracking
- Snapshots saved for historical comparison

### Exit Alerts
- Warns when holdings hit stop loss (5% hard, 3% trailing)
- Warns when max hold time exceeded (7 days)
- Warns when sell signal generated for a held position

### Risk Safety Nets
- 5% hard stop loss per position (never moves down)
- 3% trailing stop (ratchets up as price rises)
- Max 7-day hold period — alerts to exit stale positions
- Max 2 simultaneous positions
- Max 50% of portfolio in a single position
- 8% daily drawdown → halt alerts
- 20% total drawdown from peak → halt alerts

## Symbol Universe

The bot scans ~43 securities (configured in `config/settings.yaml`). Symbols ending in `.TO` are TSX-listed; symbols ending in `.NE` are CDRs on CBOE Canada.

### Market Data
- **Source:** yfinance (free, ~15 min delay — fine for swing trading on daily bars)
- `.TO` symbols work directly in yfinance
- `.NE` CDR symbols: tried as-is first, fall back to US counterpart for data gaps
- Pre-market data fetched from US tickers for CDR counterparts

## Documentation

- `docs/STRATEGY.md` — Full strategy explanation, signal scoring, position sizing
- `docs/NEXT_STEPS.md` — Roadmap and deployment notes

## Deployment

- Server: `your-server` (Ubuntu ARM, your server)
- SSH: `ssh -i your-ssh-key ubuntu@your-server`
- Repo on server: `/home/ubuntu/trader/`
- Deploy: `git push` → SSH → `cd ~/trader && git pull origin main && docker compose up -d --build`
- Secrets in `.env` on server (not in git)

## Key Constraints

- **No auto-execution:** IBKR no longer allows Canadian securities via API. User trades manually.
- **Commission awareness:** IBKR/Wealthsimple charge commissions. With small capital, every trade costs ~0.1% so high-frequency strategies are not viable.
- **yfinance data:** ~15 min delayed, not real-time. Fine for daily-bar swing trading signals.
- **Risk hard limits:** Alerts halt at 8% daily drawdown or 20% total drawdown from peak.
- **Anthropic API:** Required for `/upload` screenshot parsing. Uses Claude Sonnet for vision.
