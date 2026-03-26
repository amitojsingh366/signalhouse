# Restructuring Plan: 3-Component Architecture

## Overall Checklist

- [x] Step 1: API Package (`api/`)
- [x] Step 2: Bot Package (`bot/`)
- [x] Step 3: Docker Compose & Dockerfiles
- [x] Step 4: Next.js Web Dashboard (`web/`)
  - [x] 4.1 Scaffold Next.js project (package.json, tsconfig, tailwind, next.config, globals.css)
  - [x] 4.2 API client library (`lib/api.ts`)
  - [x] 4.3 Shared UI components (stat cards, charts, data tables, nav sidebar, loading skeletons, toasts)
  - [x] 4.4 Root layout with sidebar navigation (`app/layout.tsx`)
  - [x] 4.5 Dashboard overview page (`app/page.tsx`) — portfolio value, equity curve, latest signals, CTAs
  - [x] 4.6 Portfolio page (`app/portfolio/page.tsx`) — holdings table, live prices, advice, edit dropdown
  - [x] 4.7 Signals page (`app/signals/page.tsx`) — recommendations, sector exposure, symbol search
  - [x] 4.8 Trades page (`app/trades/page.tsx`) — trade history, buy/sell forms
  - [x] 4.9 Upload page (`app/upload/page.tsx`) — screenshot upload, confirm/edit flow
  - [x] 4.10 Status page (`app/status/page.tsx`) — uptime, market hours, system info
- [x] Step 5: Configuration & Environment Updates
  - [x] 5.1 Update `.env.example`
  - [x] 5.2 Update `CLAUDE.md`
  - [x] 5.3 Update `docs/NEXT_STEPS.md`
- [x] Step 6: Testing & Validation
- [x] Step 7: Caddy Reverse Proxy & Deployment
  - [x] 7.1 Add Caddy service with auto-HTTPS, routes `/api/*` → FastAPI, `/*` → Next.js
  - [x] 7.2 Internal-only ports for postgres/api/web, Caddy exposes 80+443
  - [x] 7.3 Deploy all 5 services to `your-server`, DNS via Cloudflare
  - [x] 7.4 Fix `NEXT_PUBLIC_API_URL` — empty string for relative URLs through Caddy
  - [x] 7.5 Open port 443 in iptables, verify website + API at `yourdomain.com`
- [ ] Step 8: Web Performance & UX Improvements
  - [x] 8.1 Fix sector exposure NaN bug (API returns nested dict `{value, pct, symbols}`, chart treats value as number)
  - [x] 8.2 Add localStorage caching layer to API client for instant page loads
  - [x] 8.3 Dashboard: progressive loading — stat cards render from cache instantly, charts/signals load async
  - [x] 8.4 Move sector exposure chart from Signals page to Dashboard
  - [x] 8.5 Signals: always-visible search bar above async-loading signal cards
  - [ ] 8.6 Deploy to server

---

## Overview

Restructure the Discord trading bot from a single-package Python app (`src/trader/`) into a 3-component architecture:

- **`api/`** — FastAPI REST API + all shared business logic + PostgreSQL database backend
- **`bot/`** — Discord bot that imports directly from the `api` package (Python imports, not HTTP)
- **`web/`** — Next.js web dashboard that communicates exclusively over the REST API

All components are containerized via Docker Compose (postgres, api, bot, web).

## Technologies

| Component | Stack |
|-----------|-------|
| API | FastAPI, SQLAlchemy async + asyncpg, PostgreSQL 16, Pydantic v2 |
| Bot | discord.py, imports `trader_api` as a Python package dependency |
| Web | Next.js (App Router), Tailwind CSS, Recharts, Lucide icons, Bun (package manager) |
| Infra | Docker Compose, 5 services: postgres, api, bot, web, caddy |

## Web Dashboard Design Guidelines

### Visual Style
- Clean, minimalist design approach
- Cohesive color scheme with 2-3 primary colors and appropriate accent colors
- Ample white space for a sleek, uncluttered look
- Modern typography with clear hierarchy (headings, subheadings, body text)

### Layout and Structure
- Intuitive, user-friendly navigation system
- Responsive layout that adapts seamlessly to different screen sizes
- Grid-based layout for consistent alignment and spacing

### UI Elements
- Custom icons that align with the overall visual style
- Visually appealing and interactive buttons, forms, and other UI components
- Subtle animations and transitions for a polished feel

### UX Considerations
- Clear visual feedback for user actions
- Optimized user flow to minimize steps for key tasks
- Intuitive gestures and interactions for mobile users

### Branding
- Incorporate the app's logo and brand identity seamlessly
- Maintain consistency with the brand's visual language across all screens

### Accessibility
- High-contrast color combinations for text and backgrounds
- All interactive elements easily tappable on mobile devices
- Alt text for images and icons

### Current Trends
- Incorporate glassmorphism or neumorphism where appropriate
- Subtle gradients or textures to add depth and interest

### Special features

The web dashboard must support the same features as the Discord bot:

| Discord Command | Web Equivalent |
|----------------|----------------|
| `/buy`, `/sell` | Trade recording form |
| `/holdings` | Portfolio holdings page with live prices and per-holding advice |
| `/pnl` | P&L page with equity curve chart (daily snapshots) |
| `/recommend` | Signals/recommendations page with sector exposure |
| `/check <symbol>` | Symbol detail page with signal + sentiment |
| `/upload` | Screenshot upload page with confirm/edit flow |
| `/status` | Status page (uptime, market hours, portfolio summary) |
| Scheduled scans/briefings | Dashboard overview with latest signals |

- the home page for the dashboard should have a good visualization of the user's assets and their PnL over a period (they should be able to choose from 1d, 3d, 7d, 1M, 3M, 1Y, 5Y)
- the `/recommend` command should be mapped to a whole new page but a preview/most recent signals for the user should be given at the home page too
- there should be search bar at the top which will work like the `/check` command letting them get insights on the token and if they hold the token, sell swap, buy more etc. this page should also have the standard insidgts on the token such as a price graph like the one on the dashboard. selling/buying should also be possible on this page
- the editing funtionality of holdings along with uploading a screenshot to extract the holdings from it should be in its own page
- there should be CTAs on home page for major tasks like selling/buying/editing holdings


---

## Completed Steps

### Step 1: API Package (`api/`)

Created the full `api/src/trader_api/` package — all shared business logic lives here. Both the bot and web dashboard depend on this.

**Files created:**

#### Core
- `api/src/trader_api/__init__.py` — Package init
- `api/src/trader_api/config.py` — Loads `config/settings.yaml` + `settings.local.yaml`, env var overrides (same as original `trader.config`)
- `api/src/trader_api/database.py` — SQLAlchemy async engine, `Base`, `init_db()`, `get_db()` dependency, `async_session` factory. Uses `DATABASE_URL` env var (default: `postgresql+asyncpg://trader:trader@localhost:5432/trader`)
- `api/src/trader_api/models.py` — SQLAlchemy ORM models: `Holding`, `Trade`, `DailySnapshot`, `PortfolioMeta`, `SignalHistory`
- `api/src/trader_api/schemas.py` — Pydantic request/response models for all API endpoints
- `api/src/trader_api/deps.py` — Singleton service management (`init_services()`, `make_strategy()`, `make_portfolio()`)
- `api/src/trader_api/app.py` — FastAPI app with CORS, lifespan handler that inits DB + services + syncs risk manager at startup
- `api/src/trader_api/main.py` — Uvicorn entry point on port 8000
- `api/pyproject.toml` — Package config with all dependencies

#### Services (migrated from `src/trader/`)
- `api/src/trader_api/services/__init__.py`
- `api/src/trader_api/services/market_data.py` — yfinance wrapper (from original `trader.market_data`)
- `api/src/trader_api/services/signals.py` — TA-Lib signal generation (from original `trader.signals`)
- `api/src/trader_api/services/risk.py` — Risk manager (from original `trader.risk`)
- `api/src/trader_api/services/sentiment.py` — Sentiment analyzer (from original `trader.sentiment`)
- `api/src/trader_api/services/vision.py` — Claude Sonnet vision (from original `trader.vision`)
- `api/src/trader_api/services/backtest.py` — Backtesting (from original `trader.backtest`)
- `api/src/trader_api/services/portfolio.py` — **Major rewrite**: fully DB-backed using SQLAlchemy async, replaces JSON file storage. Same method interface but all methods are now `async` and use `AsyncSession`. Uses `PortfolioMeta` single-row table for cash/initial_capital instead of JSON top-level fields.
- `api/src/trader_api/services/strategy.py` — Adapted to use async portfolio methods

#### Routers (REST API endpoints)
- `api/src/trader_api/routers/__init__.py`
- `api/src/trader_api/routers/portfolio.py` — `GET /api/portfolio/holdings`, `/pnl`, `/snapshots`
- `api/src/trader_api/routers/trades.py` — `POST /api/trades/buy`, `/sell`, `GET /api/trades/history`
- `api/src/trader_api/routers/signals.py` — `GET /api/signals/check/{symbol}`, `/recommend`, `/insights`
- `api/src/trader_api/routers/status.py` — `GET /api/status`, `POST /api/upload/parse`, `/confirm`, `GET /api/symbols`

#### Database Models (PostgreSQL, replaces JSON)
- `Holding` — symbol, quantity, avg_cost, entry_date
- `Trade` — symbol, action, quantity, price, total, pnl, pnl_pct, timestamp
- `DailySnapshot` — date, portfolio_value, cash, positions_value
- `PortfolioMeta` — single row: cash, initial_capital, peak_value
- `SignalHistory` — symbol, signal, strength, score, reasons, timestamp

**How:** Each original `src/trader/*.py` service file was copied to `api/src/trader_api/services/` with import paths updated from `trader.*` to `trader_api.*`. The portfolio module was fully rewritten to use SQLAlchemy async instead of JSON file I/O. FastAPI routers were written to expose each service operation as REST endpoints.

---

### Step 2: Bot Package (`bot/`)

Created the `bot/src/trader_bot/` package — the Discord bot that imports `trader_api` as a Python dependency.

**Files created:**

#### Core
- `bot/src/trader_bot/__init__.py` — Package init
- `bot/src/trader_bot/bot.py` — `TraderBot` class with `db_session_factory` parameter. Key methods:
  - `get_fresh_portfolio()` — creates a `Portfolio` with a fresh DB session per command
  - `get_fresh_strategy()` — creates a `Strategy` with a fresh portfolio (avoids stale sessions)
  - `is_market_hours()` — helper function
- `bot/src/trader_bot/main.py` — Entry point: inits DB via `init_db()`, loads config, creates services, syncs risk manager from DB holdings, starts bot
- `bot/pyproject.toml` — Depends on `trader-api` and `discord.py`

#### Cogs (migrated from `src/trader/cogs/`)
- `bot/src/trader_bot/cogs/__init__.py` — `EXTENSIONS` list pointing to `trader_bot.cogs.*`
- `bot/src/trader_bot/cogs/trading.py` — `/buy`, `/sell` commands
- `bot/src/trader_bot/cogs/portfolio.py` — `/holdings`, `/pnl` commands + dropdown edit views
- `bot/src/trader_bot/cogs/signals.py` — `/recommend`, `/check` commands + persistent recheck button
- `bot/src/trader_bot/cogs/upload.py` — `/upload` command + screenshot parsing + confirm/edit views
- `bot/src/trader_bot/cogs/status.py` — `/status` command
- `bot/src/trader_bot/cogs/tasks.py` — Scheduled loops (scans, daily status, briefings, recaps)

**How:** Each cog was adapted from the original `src/trader/cogs/` with these changes:
1. Imports changed from `trader.*` to `trader_api.services.*` and `trader_bot.*`
2. Instead of using `self.bot.portfolio` directly (which held a single long-lived session), cogs now call `self.bot.get_fresh_portfolio()` and `self.bot.get_fresh_strategy()` to get fresh DB sessions per command/task
3. Views and modals store a reference to `bot: TraderBot` instead of `portfolio: Portfolio` + `risk: RiskManager`, so they can create fresh sessions when the user clicks buttons
4. Properties like `portfolio.cash` and `portfolio.holdings` (which were sync in the JSON version) are now accessed via async methods like `portfolio.get_holdings_dict()` and `portfolio._get_meta()`

---

### Step 3: Docker Compose & Dockerfiles

**Files created:**
- `api/Dockerfile` — Python 3.11-slim with TA-Lib, installs api package, runs uvicorn on port 8000
- `bot/Dockerfile` — Python 3.11-slim with TA-Lib, installs api package first (dependency), then bot package. Build context is repo root so it can `COPY api/` and `COPY bot/`
- `web/Dockerfile` — Multi-stage Node 20 Alpine build (deps → build → runner with standalone output)
- `docker-compose.yml` — Orchestrates 4 services:
  - `postgres` — PostgreSQL 16 Alpine with healthcheck, persistent `pgdata` volume
  - `api` — Depends on postgres healthy, gets `DATABASE_URL` + `ANTHROPIC_API_KEY`, exposes port 8000
  - `bot` — Depends on postgres healthy, gets `DATABASE_URL` + all Discord/Anthropic env vars
  - `web` — Depends on api, gets `NEXT_PUBLIC_API_URL`, exposes port 3000

**How:** The original single `Dockerfile` and `docker-compose.yml` were replaced. The bot Dockerfile has its build context set to the repo root (`.`) so it can copy both `api/` and `bot/` directories. The api Dockerfile's context is `./api`. The web Dockerfile uses the standard Next.js standalone multi-stage pattern.

---

## Remaining Steps

### Step 4: Next.js Web Dashboard (`web/`)

Scaffold a Next.js app with App Router, shadcn/ui, and Tailwind CSS. Directory structure already created:

```
web/
├── app/
│   ├── layout.tsx          # Root layout with sidebar navigation
│   ├── page.tsx            # Dashboard overview (latest signals, portfolio summary)
│   ├── portfolio/page.tsx  # Holdings table with live prices, per-holding advice
│   ├── signals/page.tsx    # Recommendations, sector exposure, check symbol
│   ├── trades/page.tsx     # Trade history table, buy/sell forms
│   ├── upload/page.tsx     # Screenshot upload with confirm/edit flow
│   └── status/page.tsx     # Bot status, market hours, system info
├── components/
│   └── ui/                 # shadcn/ui components
├── lib/
│   └── api.ts              # API client (fetch wrapper for /api/* endpoints)
├── public/
├── tailwind.config.ts
├── next.config.js
├── package.json
├── tsconfig.json
└── Dockerfile
```

**Pages to implement:**

1. **Dashboard Overview** (`/`) — Portfolio value card, daily P&L, equity curve chart (from snapshots endpoint), latest signals summary, market status indicator
2. **Portfolio** (`/portfolio`) — Holdings table with columns: symbol, quantity, avg cost, current price, P&L %, action/advice. Edit holdings modal. Cash display.
3. **Signals** (`/signals`) — Top buy/sell recommendations, sector exposure bar chart, symbol search/check with signal detail cards
4. **Trades** (`/trades`) — Trade history table (filterable by symbol/action/date), buy/sell trade recording forms
5. **Upload** (`/upload`) — Image upload dropzone, parsed holdings preview table, confirm/edit/cancel flow
6. **Status** (`/status`) — Uptime, symbols tracked, holdings count, market hours, scan interval

**API client:** All pages fetch data from the FastAPI REST API at `NEXT_PUBLIC_API_URL`. Key endpoints:
- `GET /api/portfolio/holdings` — Holdings with live prices
- `GET /api/portfolio/pnl` — P&L breakdown
- `GET /api/portfolio/snapshots` — Daily snapshots for equity curve
- `POST /api/trades/buy`, `POST /api/trades/sell` — Record trades
- `GET /api/trades/history` — Trade history
- `GET /api/signals/recommend` — Top signals
- `GET /api/signals/check/{symbol}` — Single symbol analysis
- `GET /api/signals/insights` — Daily insights
- `GET /api/status` — Bot/system status
- `POST /api/upload/parse` — Parse screenshot
- `POST /api/upload/confirm` — Confirm parsed holdings
- `GET /api/symbols` — Full symbol universe for autocomplete

**UI components needed:** Data tables, charts (equity curve, sector exposure), forms (trade entry), file upload dropzone, signal cards, stat cards, navigation sidebar, loading skeletons, toast notifications.

**Design:** Follow the design guidelines listed above — glassmorphism/neumorphism accents, 2-3 primary colors, grid layout, subtle animations, high contrast, responsive.

### Step 5: Configuration & Environment Updates

- Update `.env.example` with new variables (`POSTGRES_PASSWORD`, `DATABASE_URL`, `NEXT_PUBLIC_API_URL`)
- Update `CLAUDE.md` to reflect the new 3-component architecture, new commands, new directory structure
- Update `docs/NEXT_STEPS.md` to mark the database backend phase as complete

### Step 6: Testing & Validation

- Verify all 4 Docker services start and connect correctly
- Test API endpoints return correct data
- Test bot commands work with PostgreSQL backend
- Test web dashboard pages load and display data
- Test trade recording flows end-to-end (web → API → DB, bot → DB)
- Verify data consistency between bot and web (both see same holdings/trades)

### Step 7: Caddy Reverse Proxy & Deployment

**Files created/modified:**
- `Caddyfile` — `yourdomain.com` with auto-HTTPS, routes `/api/*` → `api:8000`, `/*` → `web:3000`
- `docker-compose.yml` — Added `caddy` service (ports 80+443), postgres/api/web internal-only (`expose`)
- `web/Dockerfile` — Fixed empty `public/` dir, `NEXT_PUBLIC_API_URL` uses relative URLs through Caddy

**Architecture:**
```
Internet → Cloudflare (SSL) → Caddy (:443 auto-HTTPS) → web (:3000) for pages
                                                       → api (:8000) for /api/*
```

**Deployment:** `git push` → SSH → `git pull && docker compose up -d --build` on `your-server`. All 5 services running. DNS `yourdomain.com` via Cloudflare proxied A record.
