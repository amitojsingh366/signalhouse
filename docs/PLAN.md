# Trading Dashboard — Development Plan

## Quick Start

This file is the primary context document for new Claude Code conversations. Read it first, then dive into specific files as needed.

**What this is:** A trading recommendation and portfolio tracking system for TSX stocks, CBOE Canada CDRs, and CAD-hedged ETFs. It provides buy/sell/swap signals — the user trades manually and reports back.

**3-component architecture:**
- `api/` — FastAPI REST API + all shared business logic + PostgreSQL
- `bot/` — Discord bot that imports `trader_api` as a Python package
- `web/` — Next.js web dashboard that communicates via REST API

**Deployed at:** `yourdomain.com` on `your-server` (Ubuntu ARM, your server)

---

## Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| **API** | FastAPI, SQLAlchemy (async), asyncpg | Python 3.11, port 8000 |
| **Bot** | discord.py ≥ 2.3 | Slash commands, persistent buttons |
| **Web** | Next.js 14, Bun, Tailwind CSS, Recharts | App Router, standalone Docker output |
| **DB** | PostgreSQL 16 | Shared by api + bot |
| **Market data** | yfinance | ~15 min delay, daily bars |
| **TA** | TA-Lib (C library + Python) | EMA, RSI, MACD, BB, ATR |
| **Sentiment** | yfinance + fear-greed lib | Analyst consensus, F&G, news |
| **Vision** | Anthropic Claude Sonnet | Brokerage screenshot parsing |
| **Proxy** | Caddy | SSL via Cloudflare, routes /api/* and /* |
| **Infra** | Docker Compose (5 services) | postgres, api, bot, web, caddy |

---

## Project Structure

```
trader/
├── api/                              # FastAPI REST API + all shared business logic
│   ├── Dockerfile                    # Python 3.11-slim + TA-Lib
│   ├── pyproject.toml
│   └── src/trader_api/
│       ├── app.py                    # FastAPI app, CORS, lifespan
│       ├── main.py                   # Uvicorn entry (port 8000)
│       ├── config.py                 # settings.yaml + settings.local.yaml loader
│       ├── database.py               # SQLAlchemy async engine, Base, init_db(), get_db()
│       ├── models.py                 # ORM: Holding, Trade, DailySnapshot, PortfolioMeta, SignalHistory
│       ├── schemas.py                # Pydantic request/response models
│       ├── deps.py                   # Singleton service management (DI pattern)
│       ├── routers/
│       │   ├── portfolio.py          # GET /api/portfolio/{holdings,pnl,snapshots}, PUT holding/cash, DELETE holding
│       │   ├── trades.py             # POST /api/trades/{buy,sell}, GET /api/trades/history
│       │   ├── signals.py            # GET /api/signals/{check,recommend,insights,price}
│       │   └── status.py             # GET /api/status, POST /api/upload/{parse,confirm}, GET /api/symbols
│       └── services/
│           ├── market_data.py        # yfinance wrapper, batch price fetching, CDR fallback
│           ├── signals.py            # TA-Lib indicators, score → BUY/SELL/HOLD conversion
│           ├── strategy.py           # Recommendation engine, caching, sell-to-fund, advice
│           ├── portfolio.py          # DB-backed portfolio (async SQLAlchemy CRUD)
│           ├── risk.py               # Position sizing (ATR), stop losses, drawdown circuit breakers
│           ├── sentiment.py          # Analyst consensus (4h cache), Fear & Greed (1h), news (30m)
│           ├── vision.py             # Claude Sonnet vision (screenshot parsing)
│           └── backtest.py           # Historical replay
│
├── bot/                              # Discord bot (imports trader_api as Python dependency)
│   ├── Dockerfile                    # Python 3.11-slim + TA-Lib, copies api/ + bot/
│   ├── pyproject.toml
│   └── src/trader_bot/
│       ├── bot.py                    # TraderBot class, fresh-session-per-command pattern
│       ├── main.py                   # Entry point: init DB, load config, start bot
│       └── cogs/
│           ├── trading.py            # /buy, /sell
│           ├── portfolio.py          # /holdings, /pnl + dropdown edit
│           ├── signals.py            # /recommend, /check + recheck button
│           ├── upload.py             # /upload + screenshot parsing
│           ├── status.py             # /status
│           └── tasks.py              # Scheduled loops (scans, briefings, recaps)
│
├── web/                              # Next.js dashboard (Bun, App Router, Tailwind, Recharts)
│   ├── Dockerfile                    # Multi-stage Node 20 Alpine, standalone output
│   ├── package.json                  # Bun lockfile
│   ├── tailwind.config.ts            # brand (purple), surface (zinc) color tokens
│   ├── next.config.js
│   ├── app/
│   │   ├── globals.css               # CSS vars, glass-card, badge-buy/sell/hold, skeleton
│   │   ├── layout.tsx                # Root layout with sidebar navigation
│   │   ├── page.tsx                  # Dashboard: stat cards, equity chart, sector exposure, CTAs, signals
│   │   ├── portfolio/page.tsx        # Holdings table, click-to-edit, cash edit, signal badges
│   │   ├── signals/page.tsx          # Recommendations, symbol search/check, signal cards
│   │   ├── trades/page.tsx           # Buy/sell form, trade history table
│   │   ├── upload/page.tsx           # Dropzone, Claude Vision parse, confirm/edit/cancel
│   │   └── status/page.tsx           # Uptime, market status, risk status, symbols tracked
│   ├── components/ui/
│   │   ├── data-table.tsx            # Generic sortable table
│   │   ├── equity-chart.tsx          # Area chart with date range buttons (1D–ALL)
│   │   ├── loading.tsx               # Skeleton components: Card, Table, Chart, Sector, Signals, Upload
│   │   ├── search-bar.tsx            # Symbol search dropdown with autocomplete
│   │   ├── sector-chart.tsx          # Horizontal bar chart, purple gradient, hover highlight
│   │   ├── sidebar.tsx               # Navigation sidebar with active state
│   │   ├── price-chart.tsx            # Symbol price area chart with range selector (1W–1Y)
│   │   ├── signal-badge.tsx          # BUY/SELL/HOLD badge component
│   │   ├── stat-card.tsx             # Summary stat card with change percentage
│   │   └── toast.tsx                 # Toast notification provider
│   └── lib/
│       ├── api.ts                    # API client, TypeScript types, localStorage cache with TTLs
│       └── utils.ts                  # formatCurrency, formatPercent, pnlColor, cn, signalBadgeClass
│
├── config/
│   ├── settings.yaml                 # Defaults: symbol universe (~92), risk params, schedules
│   └── settings.local.yaml           # Secrets (gitignored)
│
├── docker-compose.yml                # 5 services: postgres, api, bot, web, caddy
├── Caddyfile                         # Reverse proxy: /api/* → api:8000, /* → web:3000
├── .env.example                      # Required env vars template
├── CLAUDE.md                         # Full project docs for Claude Code
└── docs/
    ├── PLAN.md                       # This file — primary context for new conversations
    ├── STRATEGY.md                   # Signal scoring, sentiment, position sizing
    └── NEXT_STEPS.md                 # Roadmap (phases 1–4)
```

---

## Architecture

```
Internet → Cloudflare (SSL) → Caddy (:443) → web (:3000) for pages
                                             → api (:8000) for /api/*

Bot imports trader_api directly as a Python package (not HTTP).
Web communicates exclusively via REST API through Caddy reverse proxy.
Both share the same PostgreSQL database.
```

### Database Models (PostgreSQL)

| Model | Key Fields | Purpose |
|-------|-----------|---------|
| `Holding` | symbol (unique), quantity, avg_cost, entry_date | Current portfolio positions |
| `Trade` | symbol, action (BUY/SELL), quantity, price, total, pnl, pnl_pct | Trade audit trail |
| `DailySnapshot` | date (unique), portfolio_value, cash, positions_value | Equity curve data |
| `PortfolioMeta` | cash, initial_capital | Single-row portfolio state |
| `SignalHistory` | symbol, signal, strength, score, reasons | Signal audit trail |

### API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/portfolio/holdings` | Holdings with live prices, P&L, signal advice |
| GET | `/api/portfolio/pnl` | Daily & total P&L, cash, recent trades |
| GET | `/api/portfolio/snapshots` | Daily snapshots for equity curve |
| PUT | `/api/portfolio/holding` | Update holding quantity/avg_cost |
| DELETE | `/api/portfolio/holding/{symbol}` | Delete a holding |
| PUT | `/api/portfolio/cash` | Set cash balance |
| POST | `/api/trades/buy` | Record buy (updates holding, deducts cash) |
| POST | `/api/trades/sell` | Record sell (calculates P&L, adds cash) |
| GET | `/api/trades/history` | Last N trades |
| GET | `/api/signals/check/{symbol}` | Signal for one symbol |
| GET | `/api/signals/recommend` | Top N buy/sell signals + funding pairs |
| GET | `/api/signals/price/{symbol}` | Current market price |
| GET | `/api/signals/insights` | Daily insights (all holdings, movers, sectors) |
| GET | `/api/status` | System status, risk state |
| POST | `/api/upload/parse` | Parse screenshot via Claude vision |
| POST | `/api/upload/confirm` | Sync portfolio from parsed holdings |
| GET | `/api/symbols` | Full symbol universe |

### Service Layer

| Service | Class/Module | Key Responsibility |
|---------|-------------|-------------------|
| `portfolio.py` | `Portfolio(db)` | CRUD for holdings, trades, snapshots, cash tracking |
| `market_data.py` | `MarketData(config)` | yfinance data, batch prices, CDR→US fallback |
| `strategy.py` | `Strategy(...)` | Recommendations, advice, sell-to-fund, exit alerts |
| `signals.py` | `compute_indicators()`, `generate_signal()` | TA-Lib scoring → BUY/SELL/HOLD |
| `risk.py` | `RiskManager(config)` | Position sizing (ATR), stops, drawdown halts |
| `sentiment.py` | `SentimentAnalyzer(cdr_to_us)` | Analyst + F&G + news → ±2.0 score adjustment |
| `vision.py` | `parse_holdings_screenshot()` | Claude Sonnet vision for screenshot extraction |

### Signal Pipeline

```
For each of ~92 symbols:
  market_data (60d daily bars) → signals.compute_indicators() (TA-Lib)
  → sentiment.analyze() (analyst + F&G + news, cached)
  → signals.generate_signal() → technical_score + sentiment → BUY/SELL/HOLD + strength%
  → strategy filters (strength thresholds, sector caps) → recommendations
```

**Score range:** -8 to +8. BUY ≥ +2, SELL ≤ -2. Strength = min(|score|/8, 1.0).
**See `docs/STRATEGY.md` for full scoring details.**

### Dependency Injection (`deps.py`)

Singletons initialized at startup: `_config`, `_market_data`, `_risk`, `_sentiment`.
Session-scoped factories: `make_portfolio(db)`, `make_strategy(portfolio)`.

---

## Design System

| Role | Color | Token | Usage |
|------|-------|-------|-------|
| Primary action / CTA | Purple | `brand-400` (#a78bfa), `brand-500` (#8b5cf6) | Buy badges, confirm buttons, CTAs, links, sidebar active |
| Positive P&L / Success | Green | `emerald-400` (#34d399) | Profit numbers, success toasts, status "ok" indicators |
| Negative P&L / Error | Red | `red-400` (#f87171), `red-500` (#ef4444) | Loss numbers, sell badges, error toasts, delete buttons |
| Warning / Neutral | Amber | `amber-400` (#fbbf24) | Hold badges, warning toasts |
| Background | Black | `surface-950` (#09090b) | Page background |
| Cards | Zinc | `surface-900` (#18181b) | Glass cards with `bg-white/[0.03]` + border |
| Text | Zinc | `surface-50` (#fafafa) | Primary text |
| Muted text | Zinc | `slate-400`–`slate-500` | Labels, secondary info |

Loading states use content-shaped skeleton silhouettes (not spinners).
Charts use purple (brand color) for area/line fills regardless of trend direction.
Sector exposure chart uses a purple gradient (brightest → dimmest by weight).
P&L values use green/red (standard financial convention). CTAs and buy badges stay purple.

---

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
bun run build          # verify build passes

# Docker deployment (all 5 services)
docker compose up -d --build
docker compose logs -f

# Tests & lint
pytest
ruff check api/src/ bot/src/
mypy api/src/ bot/src/

# Deploy from local
git push
ssh -i your-ssh-key ubuntu@your-server \
  "cd ~/trader && git pull origin main && docker compose up -d --build"
```

---

## Completed Steps

- [x] **Step 1–3:** API package, bot package, Docker Compose — migrated from monolithic `src/trader/` to 3-package architecture with PostgreSQL replacing JSON file storage
- [x] **Step 4:** Next.js web dashboard — 6 pages (dashboard, portfolio, signals, trades, upload, status), shared UI components, API client with localStorage caching
- [x] **Step 5:** Configuration & environment updates (`.env.example`, `CLAUDE.md`, `NEXT_STEPS.md`)
- [x] **Step 6:** Testing & validation across all services
- [x] **Step 7:** Caddy reverse proxy, deployment to `your-server`, DNS via Cloudflare at `yourdomain.com`
- [x] **Step 8:** Web performance — localStorage cache layer, progressive loading, sector chart fix, search bar always visible
- [x] **Step 9:** Portfolio editing (CRUD endpoints), cash tracking (buy deducts/sell adds), dark theme overhaul, P&L fixes (exclude cash, include realized)
- [x] **Step 10:** Color consolidation (purple positive, red negative, amber warning), skeleton loading states, trade history chronological ordering, sector chart purple gradient with hover
- [x] **Step 11:** Dashboard polish — CTAs under stat cards, empty state cards for charts/signals, sector tooltip fix, section order: CTAs → signals → equity → sector
- [x] **Step 12:** Color scheme refinement — P&L green/red (standard financial), CTAs/buy badges stay purple, charts stay purple, success toasts and status indicators now emerald green
- [x] **Step 13:** Page header UX — Cmd+K global symbol search modal (navigates to signals page), refresh buttons on all data pages (dashboard, portfolio, signals, trades, status), search trigger button in page headers (dashboard, portfolio, trades, status)
- [x] **Step 14:** Price charts — API endpoint for OHLCV history, PriceChart component with range selector (1W–1Y), chart shown on signal check and expandable signal cards, portfolio symbol names link to signals page

---

## Next Steps

See `docs/NEXT_STEPS.md` for the full roadmap (Phase 1: Validate & Tune, Phase 2: Improve Strategy, Phase 3: Scale Up, Phase 4: Advanced Features).

- [x] **Step 15:** Same-sector swap exemption + watchlist alerts — sell-to-fund pairs within the same sector no longer penalize buy signal strength; non-held sell signals now show as "Watchlist Alerts" on signals page and dashboard instead of being silently filtered
- [x] **Step 16:** Signal badge tooltips, clickable dashboard signals — hover tooltips explain signals, dashboard signal cards link to signals page with symbol preloaded
- [x] **Step 17:** Score breakdown display — total score (e.g. -2.5/8) shown next to signal badges, per-factor scores ([+1.5], [-0.5]) on each reason line with green/red coloring, sentiment reasons include score tags, BUY scan threshold set to 35% (score 2.8 — needs ~3 agreeing indicators)
- [x] **Step 18:** Fix Fear & Greed — `fear-greed` library API changed (returns dict with `score`/`rating` instead of object with `.value`/`.description`), causing silent fallback to 50/Neutral. Fixed with dict detection. Actual F&G is 18 (Extreme Fear) = +0.5 contrarian buy boost now applied.
- [x] **Step 19:** Exit alerts on web + critical bug fixes — stop-loss/max-hold/sell-signal alerts now shown on signals page and dashboard (prioritized first above buy signals, red/amber severity styling); daily P&L fixed (was comparing against today's snapshot instead of previous day); equity chart fixed (snapshots now recorded on page load, not just by bot at 3:50 PM); bot DB connection pool exhaustion fixed (all 6 cogs + 5 scheduled tasks now close sessions via `portfolio.close()`)
- [x] **Step 20:** Clickable exit alerts — clicking an exit alert on signals page or dashboard opens the full signal check (score breakdown, reasons, price chart) for that symbol, same as a manual search
- TBD
