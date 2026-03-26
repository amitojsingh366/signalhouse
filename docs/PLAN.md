# Trading Dashboard — Development Plan

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
│       ├── deps.py                   # Singleton service management
│       ├── routers/
│       │   ├── portfolio.py          # GET /api/portfolio/{holdings,pnl,snapshots}
│       │   ├── trades.py             # POST /api/trades/{buy,sell}, GET /api/trades/history
│       │   ├── signals.py            # GET /api/signals/{check,recommend,insights,price}
│       │   └── status.py             # GET /api/status, POST /api/upload/{parse,confirm}, GET /api/symbols
│       └── services/
│           ├── market_data.py        # yfinance wrapper, batch price fetching
│           ├── signals.py            # TA-Lib indicators (EMA, RSI, MACD, BB, ATR, volume)
│           ├── strategy.py           # Recommendation engine, caching, sell-to-fund
│           ├── portfolio.py          # DB-backed portfolio (async SQLAlchemy)
│           ├── risk.py               # Position sizing, stop losses, drawdown limits
│           ├── sentiment.py          # Analyst consensus, Fear & Greed, news headlines
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
    ├── PLAN.md                       # This file
    ├── STRATEGY.md                   # Signal scoring, sentiment, position sizing
    └── NEXT_STEPS.md                 # Roadmap
```

## Architecture

```
Internet → Cloudflare (SSL) → Caddy (:443) → web (:3000) for pages
                                             → api (:8000) for /api/*

Bot imports trader_api directly as a Python package (not HTTP).
Web communicates exclusively via REST API through Caddy reverse proxy.
Both share the same PostgreSQL database.
```

## Design System

| Role | Color | Token | Usage |
|------|-------|-------|-------|
| Positive / Primary action | Purple | `brand-400` (#a78bfa), `brand-500` (#8b5cf6) | Buy badges, positive P&L, success toasts, confirm buttons, CTAs |
| Negative / Error | Red | `red-400` (#f87171), `red-500` (#ef4444) | Sell badges, negative P&L, error toasts, delete buttons |
| Warning / Neutral | Amber | `amber-400` (#fbbf24) | Hold badges, warning toasts |
| Background | Black | `surface-950` (#09090b) | Page background |
| Cards | Zinc | `surface-900` (#18181b) | Glass cards with `bg-white/[0.03]` + border |
| Text | Zinc | `surface-50` (#fafafa) | Primary text |
| Muted text | Zinc | `slate-400`–`slate-500` | Labels, secondary info |

Loading states use content-shaped skeleton silhouettes (not spinners).
Charts use purple for positive trends, red for negative.
Sector exposure chart uses a purple gradient (brightest → dimmest by weight).

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


---

## Next Steps

- TBD

