# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Trading recommendation and portfolio tracking system for TSX-listed stocks, CBOE Canada CDRs, and CAD-hedged ETFs. Provides buy/sell/swap signals via technical analysis + market sentiment, tracks holdings, and sends daily P&L summaries. Designed for a Canadian TFSA account with ~$2,000 CAD portfolio.

**3-component architecture:**
- **`api/`** — FastAPI REST API + all shared business logic + PostgreSQL database backend
- **`bot/`** — Discord bot that imports `trader_api` as a Python package dependency
- **`web/`** — Next.js web dashboard that communicates via the REST API

**This is NOT an auto-trading bot** — it provides recommendations and the user executes trades manually via their brokerage UI (Wealthsimple, IBKR, etc.), then reports them back via Discord slash commands, screenshot uploads, or the web dashboard.

## Commands

```bash
# API (local dev)
cd api && pip install -e ".[dev]"
uvicorn trader_api.main:app --reload

# Bot (local dev)
cd bot && pip install -e .
python -m trader_bot.main

# Web dashboard (local dev — uses Bun, not npm)
cd web && bun install
bun run dev            # http://localhost:3000

# Docker deployment (all 4 services)
cp .env.example .env        # fill in secrets
docker compose up -d         # postgres, api, bot, web
docker compose logs -f       # watch all logs

# Tests
pytest                     # all tests
pytest tests/test_risk.py  # single file

# Lint
ruff check api/src/ bot/src/ tests/
ruff check --fix api/src/ bot/src/

# Type check
mypy api/src/ bot/src/
```

## Architecture

```
api/src/trader_api/           # Shared business logic + REST API
├── app.py                    # FastAPI app with CORS, lifespan
├── main.py                   # Uvicorn entry point (port 8000)
├── config.py                 # Loads settings.yaml + settings.local.yaml
├── database.py               # SQLAlchemy async engine, Base, init_db(), get_db()
├── models.py                 # ORM: Holding, Trade, DailySnapshot, PortfolioMeta, SignalHistory
├── schemas.py                # Pydantic request/response models
├── deps.py                   # Singleton service management
├── routers/                  # REST API endpoints
│   ├── portfolio.py          # GET /api/portfolio/holdings, /pnl, /snapshots
│   ├── trades.py             # POST /api/trades/buy, /sell, GET /api/trades/history
│   ├── signals.py            # GET /api/signals/check/{symbol}, /recommend, /insights
│   └── status.py             # GET /api/status, POST /api/upload/parse, /confirm, GET /api/symbols
└── services/                 # Business logic (migrated from src/trader/)
    ├── market_data.py        # yfinance wrapper
    ├── signals.py            # TA-Lib signal generation
    ├── strategy.py           # Recommendation engine
    ├── portfolio.py          # DB-backed portfolio (async, replaces JSON)
    ├── risk.py               # Position sizing, stop losses, drawdown
    ├── sentiment.py          # Analyst consensus, Fear & Greed, news
    ├── vision.py             # Claude Sonnet vision (screenshot parsing)
    └── backtest.py           # Historical replay

bot/src/trader_bot/           # Discord bot (imports trader_api)
├── bot.py                    # TraderBot class with fresh-session-per-command pattern
├── main.py                   # Entry point: init DB, load config, start bot
└── cogs/                     # Discord.py cog extensions
    ├── trading.py            # /buy, /sell
    ├── portfolio.py          # /holdings, /pnl + dropdown edit
    ├── signals.py            # /recommend, /check + recheck button
    ├── upload.py             # /upload + screenshot parsing
    ├── status.py             # /status
    └── tasks.py              # Scheduled loops (scans, briefings, recaps)

web/                          # Next.js dashboard (Bun, App Router, Tailwind, Recharts)
├── app/                      # Pages (dashboard, portfolio, signals, trades, upload, status)
├── components/ui/            # Reusable components (stat cards, charts, tables, sidebar)
├── lib/api.ts                # API client with TypeScript types
└── lib/utils.ts              # Formatting helpers (currency, percent, cn)
```

### Data Flow

**Signal generation (every 15 min during market hours):**
`cogs/tasks.py` → `strategy.get_top_recommendations()` → for each of ~92 symbols:
1. `market_data` fetches 60 days of daily bars via yfinance
2. `signals.compute_indicators()` runs TA-Lib (EMA, RSI, MACD, Bollinger Bands, ATR)
3. `sentiment.analyze()` fetches analyst consensus + Fear & Greed + news headlines (cached)
4. `signals.generate_signal()` combines technical score + sentiment → BUY/SELL/HOLD + strength %
5. Strategy filters, ranks by strength, adds sector diversification context
6. Generates sell-to-fund suggestions when cash is low
7. Caches results for cross-command consistency (`_cached_recommendations`)
8. Bot posts top signals to Discord with recheck buttons

**Trade reporting:** User executes trades via brokerage → reports via Discord `/buy`/`/sell` or web dashboard trade form → `portfolio` updates holdings and P&L in PostgreSQL → `risk` manager tracks stops.

**Screenshot upload:** User sends brokerage screenshot via Discord `/upload` or web upload page → `vision.py` calls Claude Sonnet API → parsed holdings shown with Confirm/Edit/Cancel → `portfolio.sync_from_snapshot()`.

### Config

`config/settings.yaml` has defaults (symbol universe, risk params, schedule). Create `config/settings.local.yaml` (gitignored) for secrets. Environment variables override config:
- `DISCORD_BOT_TOKEN`, `DISCORD_CHANNEL_ID`, `DISCORD_GUILD_ID` — Discord credentials
- `ANTHROPIC_API_KEY` — for Claude vision screenshot parsing
- `DATABASE_URL` — PostgreSQL connection string
- `POSTGRES_PASSWORD` — used by docker-compose
- `NEXT_PUBLIC_API_URL` — API URL for web dashboard

### Docker

`docker-compose.yml` orchestrates 5 services:
- `postgres` — PostgreSQL 16 Alpine with healthcheck, persistent `pgdata` volume
- `api` — FastAPI on port 8000 (internal only), depends on postgres
- `bot` — Discord bot, depends on postgres
- `web` — Next.js on port 3000 (internal only), depends on api (uses Bun for builds)
- `caddy` — Reverse proxy serving `yourdomain.com` on ports 80/443, routes `/api/*` to api and everything else to web. SSL terminated by Cloudflare.

### Database (PostgreSQL, replaces JSON)

ORM models in `api/src/trader_api/models.py`:
- `Holding` — symbol, quantity, avg_cost, entry_date
- `Trade` — symbol, action, quantity, price, total, pnl, pnl_pct, timestamp
- `DailySnapshot` — date, portfolio_value, cash, positions_value
- `PortfolioMeta` — single row: cash, initial_capital, peak_value
- `SignalHistory` — symbol, signal, strength, score, reasons, timestamp

## Discord Slash Commands

| Command | Description |
|---------|-------------|
| `/buy <symbol> <quantity> <price>` | Record a buy trade |
| `/sell <symbol> <quantity> <price>` | Record a sell trade |
| `/upload <image>` | Parse screenshot of holdings via Claude vision |
| `/holdings` | View portfolio with live prices, per-holding advice, and edit dropdown |
| `/pnl` | Daily + total P&L breakdown with recent trades |
| `/recommend` | Universe scan → top buy/sell signals with sell-to-fund suggestions |
| `/check <symbol>` | Signal + sentiment for any symbol (autocompletes held positions) |
| `/status` | Bot uptime, portfolio summary, market hours |

## Web Dashboard Pages

| Page | Route | Description |
|------|-------|-------------|
| Dashboard | `/` | Portfolio value, equity curve chart, daily P&L, latest signals, CTAs |
| Portfolio | `/portfolio` | Holdings table with live prices, P&L, signal/advice per holding |
| Signals | `/signals` | Buy/sell recommendations, watchlist alerts, score breakdowns, symbol search |
| Trades | `/trades` | Buy/sell forms, trade history table |
| Upload | `/upload` | Screenshot dropzone, parsed holdings editor, confirm/cancel |
| Status | `/status` | Uptime, market status, symbols tracked, risk status |

## REST API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/portfolio/holdings` | Holdings with live prices and advice |
| GET | `/api/portfolio/pnl` | P&L breakdown |
| GET | `/api/portfolio/snapshots` | Daily snapshots for equity curve |
| POST | `/api/trades/buy` | Record a buy trade |
| POST | `/api/trades/sell` | Record a sell trade |
| GET | `/api/trades/history` | Trade history |
| GET | `/api/signals/check/{symbol}` | Signal + sentiment for a symbol |
| GET | `/api/signals/recommend` | Top buy/sell signals |
| GET | `/api/signals/insights` | Daily insights |
| GET | `/api/status` | System status |
| POST | `/api/upload/parse` | Parse screenshot via Claude vision |
| POST | `/api/upload/confirm` | Confirm parsed holdings |
| GET | `/api/symbols` | Full symbol universe |

## Signal System

### Technical Scoring (-6 to +6)

Six TA-Lib indicators produce a score. Score ≥ +2 → BUY, ≤ -2 → SELL.

- **EMA Crossover** (10/30): ±2.0 on cross, ±0.5 for trend alignment
- **RSI** (14-period): +1.5 if < 30 (oversold), -1.5 if > 70 (overbought)
- **MACD Histogram**: ±1.0 on zero-line cross
- **Bollinger Bands** (20-period, 2σ): ±1.5 at band touches
- **Volume**: ±0.5 if > 1.5× 20-day average (confirms direction)

### Sentiment Adjustment (±2.0)

Three sources added to technical score:
- **Analyst consensus** (yfinance): -1.0 to +1.0 based on Strong Buy/Buy/Hold/Sell counts. Cached 4h.
- **CNN Fear & Greed Index** (`fear-greed` lib): -0.5 to +0.5, contrarian (extreme fear = bullish). Cached 1h.
- **News headline sentiment** (yfinance): -0.5 to +0.5, keyword-based scoring. Cached 30min.

All fail silently to 0 — sentiment never blocks signal generation.

### Strength & Filtering

`strength = min(|score| / 8.0, 1.0)` — 0% to 100%. BUY signals need ≥ 35% strength to surface in scans. SELL signals need ≥ 30%. Non-held sell signals show as "Watchlist Alerts" instead of being hidden.

### Score Display

Every signal displays its total score (e.g. `-2.5/8`) next to the badge. Each factor shows its contribution (e.g. `[+1.5]`, `[-0.5]`) color-coded green/red in the web UI. Sentiment reasons also include score tags.

### Sector Cap Swap Exemption

Same-sector sell-to-fund swaps are exempt from the 40% sector cap penalty. Swapping within a sector doesn't increase exposure, so the buy signal keeps full strength.

### Recommendation Caching

`get_top_recommendations()` caches results. `get_holding_advice()` cross-references the cache so `/holdings` shows the same sell-to-fund SWAP suggestions as `/recommend`. Cache refreshes every 15 min (scheduled scan) and on `/recommend`.

## Portfolio Tracking

- User reports trades via Discord `/buy`/`/sell` or web dashboard trade form
- `/upload` (Discord) or web upload page parses brokerage screenshots using Claude Sonnet vision API
- Discord `/holdings` Edit button opens a dropdown select to pick which holding to edit
- Web portfolio page shows holdings table with click-to-expand advice detail
- Symbol resolution for bare tickers: `.TO` → `.NE` → US
- PostgreSQL persistence (holdings, trade history, daily snapshots) — shared between bot and web

## Scheduled Tasks

| Task | Time | Description |
|------|------|-------------|
| Market scan | Every 15 min (market hours) | Exit alerts + top buy/sell signals |
| Pre-market movers | 8:00 AM ET | US premarket moves for CDR counterparts |
| Morning briefing | 8:30 AM ET | Full portfolio analysis + market overview |
| Daily status | 3:50 PM ET | P&L summary, daily snapshot saved |
| Evening recap | 10:00 PM PT | Full portfolio analysis + market overview |

## Risk Safety Nets

- 5% hard stop loss per position (never moves down)
- 3% trailing stop (ratchets up from highest price)
- Max 7-day hold period — alerts to exit stale positions
- Max 2 simultaneous positions
- Max 50% of portfolio in a single position
- Max 40% of portfolio in a single sector
- 8% daily drawdown → halt recommendations
- 20% total drawdown from peak → halt recommendations

## Symbol Universe

~92 securities across 12 sectors (configured in `config/settings.yaml`). Symbols ending in `.TO` are TSX-listed; `.NE` are CDRs on CBOE Canada. CDR data falls back to US counterpart via yfinance when `.NE` data is unavailable.

## Market Data

- **Source:** yfinance (free, ~15 min delay — fine for daily-bar swing trading)
- `.TO` symbols work directly; `.NE` CDRs fall back to US ticker for data gaps
- Pre-market data from US tickers for CDR counterparts
- Batch price fetching via `yfinance.download()` for efficiency

## Documentation

- `docs/STRATEGY.md` — Full strategy explanation, signal scoring, sentiment system, position sizing
- `docs/NEXT_STEPS.md` — Roadmap and deployment notes
- `docs/PLAN.md` — Restructuring plan and progress checklist

## Deployment

- Server: `your-server` (Ubuntu ARM, your server)
- SSH: `ssh -i your-ssh-key ubuntu@your-server`
- Repo on server: `/home/ubuntu/trader/`
- Deploy: `git push` → SSH → `cd ~/trader && git pull origin main && docker compose up -d --build`
- Secrets in `.env` on server (not in git)

## Key Constraints

- **No auto-execution:** IBKR no longer allows Canadian securities via API. User trades manually.
- **Commission awareness:** With ~$2,000 capital, each round-trip costs ~0.1%. High-frequency strategies are not viable.
- **yfinance data:** ~15 min delayed, not real-time. Fine for daily-bar swing trading signals.
- **Sentiment limitations:** Analyst data updates infrequently, news scoring is keyword-based, Fear & Greed is market-wide. These are directional nudges.
- **CDR data gaps:** Some `.NE` symbols have spotty yfinance data. US fallback mitigates this.
- **Risk hard limits:** 8% daily drawdown or 20% total drawdown halts all recommendations.
- **Anthropic API:** Required for `/upload` screenshot parsing. Uses Claude Sonnet for vision.
- **Web uses Bun:** The web dashboard uses Bun (not npm/yarn) for package management and builds.
